"""Identify competing GPU processes and apply the recorded operational policy.

Admission still uses the exclusive guard. Live observation can be configured to
record contention without interrupting work; legacy mode signals only our own
launcher, whose cleanup terminates only the process group it created.
"""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import threading
import xml.etree.ElementTree as ET

import campaign as c


PROC_ROOT = Path('/proc')
# Exactly campaign.inventory's existing list plus resume's existing Settings UI.
# Never infer permission from a process name, browser family or small VRAM use.
DESKTOP_EXECUTABLES = frozenset({
    '/home/kabatan/.local/opt/codex-desktop-linux/codex-app/ChatGPT',
    '/usr/lib/claude-desktop/claude-desktop',
    '/usr/bin/nautilus', '/usr/bin/ptyxis',
    '/home/kabatan/.config/discord/app-1.0.159/Discord',
    '/usr/bin/gnome-control-center',
})
OBSERVE_ONLY = 'observe_only_user_notifies'
INTERRUPT = 'interrupt_own_launcher'


def stat_fields(pid):
    # comm can contain spaces and parentheses: split after its last ')'.
    return (PROC_ROOT / str(pid) / 'stat').read_text().rsplit(')', 1)[1].split()


def belongs_to(pid, ancestor):
    seen = set()
    while pid > 1 and pid not in seen:
        if pid == ancestor:
            return True
        seen.add(pid)
        try:
            pid = int(stat_fields(pid)[1])
        except (OSError, ValueError, IndexError):
            return False
    return False


def process_identity(pid):
    """Capture stable /proc identity; retain explicit gone/unknown evidence."""
    row = dict(pid=pid, identity_capture_time=c.stamp(), identity_status='unknown',
               executable=None, command=None, cmdline=None,
               cmdline_sha256=None, starttime_ticks=None)
    proc = PROC_ROOT / str(pid)
    try:
        row['starttime_ticks'] = int(stat_fields(pid)[19])
        row['executable'] = os.readlink(proc / 'exe')
        cmdline = (proc / 'cmdline').read_bytes()
        row['cmdline_sha256'] = hashlib.sha256(cmdline).hexdigest()
        row['cmdline'] = cmdline.decode(errors='replace').rstrip('\0').split('\0') if cmdline else []
        row['command'] = shlex.join(row['cmdline'])
        if (int(stat_fields(pid)[19]) != row['starttime_ticks']
                or os.readlink(proc / 'exe') != row['executable']
                or (proc / 'cmdline').read_bytes() != cmdline):
            row['identity_error'] = 'Process identity changed during capture'
        elif not cmdline:
            row['identity_error'] = 'Empty process command line'
        else:
            row['identity_status'] = 'verified'
    except (FileNotFoundError, ProcessLookupError) as exc:
        row['identity_status'] = 'gone' if not proc.exists() else 'unknown'
        row['identity_error'] = repr(exc)
    except (OSError, ValueError, IndexError) as exc:
        row['identity_error'] = repr(exc)
    return row


def snapshot(guard_pid=None):
    """Shared launch/live classifier, including resident and query-only compute."""
    captured_at = c.stamp()
    xml = ET.fromstring(subprocess.check_output(
        ['nvidia-smi', '-q', '-x'], text=True, timeout=10))
    compute = subprocess.check_output(
        ['nvidia-smi', '--query-compute-apps=pid', '--format=csv,noheader,nounits'],
        text=True, timeout=10)
    compute_pids = {int(line.strip()) for line in compute.splitlines() if line.strip().isdigit()}
    entries = {}
    for entry in xml.findall('.//process_info'):
        pid = int(entry.findtext('pid'))
        kind = entry.findtext('type', '')
        if 'C' in kind or pid in compute_pids:
            entries.setdefault(pid, []).append(dict(
                gpu_type=kind, used_memory=entry.findtext('used_memory'),
                gpu_process_name=entry.findtext('process_name')))
    for pid in compute_pids:
        entries.setdefault(pid, [])
    desktop, competing, processes = [], [], []
    for pid, observations in sorted(entries.items()):
        row = process_identity(pid)
        kinds = {entry['gpu_type'] for entry in observations}
        kind = next(iter(kinds)) if len(kinds) == 1 else 'unknown'
        row.update(gpu_type=kind, xml_type=kind, gpu_observations=observations,
                   used_memory=observations[0]['used_memory'] if len(observations) == 1 else None,
                   gpu_snapshot_time=captured_at)
        if guard_pid is not None and belongs_to(pid, guard_pid):
            row['classification'] = 'owned_process'
        elif (kind == 'C+G' and row['identity_status'] == 'verified'
              and row['executable'] in DESKTOP_EXECUTABLES):
            row['classification'] = 'verified_existing_desktop_allowlist'
            desktop.append(row)
        else:
            # Even a vanished PID remains occupied for this snapshot. The next
            # observation can establish absence; a failed identity read cannot.
            row['classification'] = 'competing_or_unidentified_compute'
            competing.append(row)
        processes.append(row)
    return dict(captured_at=captured_at, desktop_inventory=desktop,
                competing_processes=competing, processes=processes)


def competitors(guard_pid):
    """Compatibility helper for callers that only need PID numbers."""
    return [row['pid'] for row in snapshot(guard_pid)['competing_processes']]


def load_policy():
    path = c.RUN / 'gpu-priority-policy.json'
    if not path.exists():
        return dict(mode=INTERRUPT, source='legacy_default_policy_absent')
    policy = c.read(path)
    if policy.get('mode') not in {INTERRUPT, OBSERVE_ONLY}:
        raise ValueError('Unknown GPU priority policy mode')
    return dict(policy, source=str(path), sha256=c.sha(path))


def event_key(receipt):
    """Ignore timestamps and memory fluctuations to avoid repeated log spam."""
    rows = receipt.get('competing_processes', [])
    return (receipt['reason'], receipt.get('error'), tuple(
        (r['pid'], r['executable'], r['starttime_ticks'], r['cmdline_sha256'],
         r['gpu_type'], r['identity_status']) for r in rows))


def record_event(label, receipt):
    directory = c.RUN / 'priority-events'
    c.write(directory / (label + '.json'), receipt)
    with (directory / (label + '.jsonl')).open('a') as out:
        out.write(json.dumps(receipt, ensure_ascii=False) + '\n')


@contextlib.contextmanager
def watch(label):
    stop = threading.Event()
    launcher_pid = os.getpid()
    policy = load_policy()
    observe_only = policy['mode'] == OBSERVE_ONLY

    def observe():
        previous = None
        while not stop.wait(2):
            try:
                active = c.read(c.RUN / 'active-process.json')
                if active.get('job') != label or active.get('owned_by') != 'night_recipe_search_20260929':
                    continue
                guard_pid = active['pid']
                proc = PROC_ROOT / str(guard_pid)
                if not proc.exists():
                    continue
                args = (proc / 'cmdline').read_bytes().decode().split('\0')
                if str(c.GPU) not in args or 'night20260929-' + label not in args:
                    continue
                if os.getpgid(guard_pid) != guard_pid or active['pgid'] != guard_pid:
                    raise RuntimeError('Campaign guard process-group identity changed')
                observed = snapshot(guard_pid)
                competing = observed['competing_processes']
                if not competing and (not observe_only or previous is None):
                    continue
                reason = ('external_gpu_compute_observed' if competing else 'external_gpu_compute_cleared') if observe_only else 'external_gpu_compute_appeared'
                receipt = dict(time=c.stamp(), job=label, reason=reason,
                               competing_pids=sorted({row['pid'] for row in competing}),
                               competing_processes=competing, gpu_snapshot_time=observed['captured_at'],
                               owned_guard_pid=guard_pid, policy=policy,
                               action=('Observe only; no signal; await user notice or actual job failure'
                                       if observe_only else 'SIGINT only to own launcher; original campaign cleans up its owned process group'))
            except Exception as exc:
                receipt = dict(time=c.stamp(), job=label, reason='gpu_priority_monitor_error', error=repr(exc),
                               policy=policy,
                               action='Observe only; no signal' if observe_only else 'Fail closed: interrupt only own launcher')
            if stop.is_set():
                return
            key = event_key(receipt)
            if key != previous:
                record_event(label, receipt)
                previous = key
            if not observe_only:
                os.kill(launcher_pid, signal.SIGINT)
                return

    thread = threading.Thread(target=observe, name='campaign-gpu-priority', daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=22)
