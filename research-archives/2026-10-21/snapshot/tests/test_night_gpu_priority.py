"""CPU-only operational GPU monitor tests: all NVIDIA/proc/signals are mocked."""
import ast
import contextlib
import hashlib
import importlib.util
import json
from pathlib import Path
import signal
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parents[1] / 'docs/research/night-recipe-search-2026-09-29'
sys.path.insert(0, str(HERE))
import campaign as campaign
import gpu_priority as monitor


class LoopEvent:
    def __init__(self, count):
        self.remaining = count
        self.stopped = False

    def wait(self, timeout):
        if self.stopped or self.remaining <= 0:
            return True
        self.remaining -= 1
        return False

    def is_set(self):
        return self.stopped

    def set(self):
        self.stopped = True


class InlineThread:
    def __init__(self, target, **kwargs):
        self.target = target

    def start(self):
        self.target()

    def join(self, timeout=None):
        pass


class GPUIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.proc = self.root / 'proc'
        self.proc.mkdir()
        self.run = self.root / 'runtime'
        self.run.mkdir()
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(monitor, 'PROC_ROOT', self.proc))
        self.stack.enter_context(mock.patch.object(campaign, 'RUN', self.run))

    def process(self, pid, executable='/usr/bin/python3', ppid=1, start=12345, args=None):
        proc = self.proc / str(pid)
        proc.mkdir(exist_ok=True)
        fields = ['S', str(ppid)] + ['0'] * 17 + [str(start)] + ['0'] * 10
        (proc / 'stat').write_text(f'{pid} (name with ) parentheses) ' + ' '.join(fields))
        exe = proc / 'exe'
        if exe.is_symlink():
            exe.unlink()
        exe.symlink_to(executable)
        (proc / 'cmdline').write_bytes(b'\0'.join(x.encode() for x in (args or [executable])) + b'\0')
        return proc

    def capture(self, rows, guard=None, query_pids=None):
        xml = '<nvidia_smi_log><gpu><processes>' + ''.join(
            f'<process_info><pid>{pid}</pid><type>{kind}</type><used_memory>{memory}</used_memory><process_name>xml-name</process_name></process_info>'
            for pid, kind, memory in rows) + '</processes></gpu></nvidia_smi_log>'
        query = '\n'.join(map(str, query_pids if query_pids is not None else [p for p,k,m in rows if 'C' in k]))
        def smi(command, **kwargs):
            return xml if '-x' in command else query
        with mock.patch.object(monitor.subprocess, 'check_output', side_effect=smi):
            return monitor.snapshot(guard)

    def test_allowlist_is_exact_frozen_campaign_plus_settings(self):
        tree = ast.parse((HERE / 'campaign.py').read_text())
        inventory = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == 'inventory')
        assignment = next(x for x in inventory.body if isinstance(x, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'allowed' for t in x.targets))
        self.assertEqual(monitor.DESKTOP_EXECUTABLES, ast.literal_eval(assignment.value) | {'/usr/bin/gnome-control-center'})

    def test_new_desktop_pid_is_dynamically_exempt_and_has_identity(self):
        for pid, exe in enumerate(sorted(monitor.DESKTOP_EXECUTABLES), 100):
            self.process(pid, exe)
        rows = [(pid, 'C+G', '95 MiB') for pid in range(100, 106)]
        result = self.capture(rows)
        self.assertEqual(result['competing_processes'], [])
        self.assertEqual(len(result['desktop_inventory']), 6)
        for row in result['desktop_inventory']:
            self.assertEqual(row['identity_status'], 'verified')
            self.assertEqual(row['starttime_ticks'], 12345)
            self.assertTrue(row['identity_capture_time'])
            self.assertEqual(row['cmdline_sha256'], hashlib.sha256((self.proc / str(row['pid']) / 'cmdline').read_bytes()).hexdigest())

    def test_unknown_tiny_memory_and_comfyui_still_compete(self):
        self.process(201, '/opt/browser/chrome')
        self.process(202, '/opt/comfy/venv/bin/python', args=['python', 'ComfyUI/main.py'])
        result = self.capture([(201, 'C+G', '1 MiB'), (202, 'C', '1 MiB')])
        self.assertEqual([r['pid'] for r in result['competing_processes']], [201, 202])
        self.assertEqual(result['desktop_inventory'], [])

    def test_known_executable_pure_compute_is_not_exempt(self):
        self.process(203, '/usr/bin/ptyxis')
        self.assertEqual(self.capture([(203, 'C', '0 MiB')])['competing_processes'][0]['pid'], 203)

    def test_owned_child_compute_is_exempt(self):
        self.process(300)
        self.process(301, ppid=300)
        self.process(302, ppid=301)
        result = self.capture([(302, 'C', '28000 MiB')], guard=300)
        self.assertEqual(result['competing_processes'], [])
        self.assertEqual(result['processes'][0]['classification'], 'owned_process')

    def test_reused_desktop_pid_with_different_executable_is_retained(self):
        self.process(204, '/usr/bin/ptyxis', start=10)
        previous = self.capture([(204, 'C+G', '20 MiB')])
        campaign.write(self.run / 'desktop-inventory.json', previous)
        self.process(204, '/opt/unknown', start=20)
        result = self.capture([(204, 'C+G', '1 MiB')])
        self.assertEqual(result['desktop_inventory'], [])
        self.assertEqual(result['competing_processes'][0]['executable'], '/opt/unknown')
        self.assertEqual(result['competing_processes'][0]['starttime_ticks'], 20)

    def test_gone_and_query_only_processes_remain_explicit(self):
        self.process(206, '/usr/bin/ptyxis')
        result = self.capture([(205, 'C', '2 MiB')], query_pids=[205, 206])
        self.assertEqual([r['pid'] for r in result['competing_processes']], [205, 206])
        self.assertEqual(result['competing_processes'][0]['identity_status'], 'gone')
        self.assertIsNone(result['competing_processes'][0]['executable'])
        self.assertEqual(result['competing_processes'][1]['gpu_type'], 'unknown')

    def test_identity_changes_during_capture_are_not_exempt(self):
        self.process(207, '/usr/bin/ptyxis')
        with mock.patch.object(monitor.os, 'readlink', side_effect=['/usr/bin/ptyxis', '/opt/unknown']):
            result = self.capture([(207, 'C+G', '1 MiB')])
        self.assertEqual(result['competing_processes'][0]['identity_status'], 'unknown')

    def live(self, snapshots, mode=monitor.OBSERVE_ONLY):
        label, guard = 'cpu-test', 400
        self.process(guard, args=['python', str(campaign.GPU), '--label', 'night20260929-' + label])
        campaign.write(self.run / 'active-process.json', dict(pid=guard, pgid=guard, job=label, owned_by='night_recipe_search_20260929'))
        if mode is not None:
            campaign.write(self.run / 'gpu-priority-policy.json', dict(mode=mode))
        with mock.patch.object(monitor.threading, 'Event', return_value=LoopEvent(len(snapshots))), \
             mock.patch.object(monitor.threading, 'Thread', InlineThread), \
             mock.patch.object(monitor.os, 'getpgid', return_value=guard), \
             mock.patch.object(monitor.os, 'kill') as kill, \
             mock.patch.object(monitor, 'snapshot', side_effect=snapshots):
            with monitor.watch(label):
                pass
        path = self.run / 'priority-events' / (label + '.jsonl')
        events = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
        return kill, events

    def test_observe_only_logs_metadata_changes_and_never_signals(self):
        self.process(208, '/opt/compute', args=['/opt/compute', '--job', 'example'])
        observed = self.capture([(208, 'C+G', '3 MiB')])
        gone = dict(observed, competing_processes=[])
        kill, events = self.live([observed, observed, gone, gone])
        kill.assert_not_called()
        self.assertEqual(len(events), 2)
        row = events[0]['competing_processes'][0]
        self.assertEqual(row['executable'], '/opt/compute')
        self.assertEqual(row['command'], '/opt/compute --job example')
        self.assertEqual(row['used_memory'], '3 MiB')
        self.assertEqual(row['gpu_type'], 'C+G')
        self.assertEqual(row['starttime_ticks'], 12345)
        self.assertEqual(events[0]['reason'], 'external_gpu_compute_observed')
        self.assertEqual(events[1]['reason'], 'external_gpu_compute_cleared')
        self.assertTrue(events[0]['policy']['sha256'])

    def test_observe_only_monitor_errors_are_logged_without_signals_or_spam(self):
        kill, events = self.live([RuntimeError('nvidia query failed'), RuntimeError('nvidia query failed')])
        kill.assert_not_called()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['reason'], 'gpu_priority_monitor_error')

    def test_absent_policy_preserves_signal_only_to_own_launcher(self):
        self.process(209, '/opt/compute')
        observed = self.capture([(209, 'C', '5 MiB')])
        kill, events = self.live([observed], mode=None)
        kill.assert_called_once_with(monitor.os.getpid(), signal.SIGINT)
        self.assertEqual(events[0]['reason'], 'external_gpu_compute_appeared')
        self.assertEqual(events[0]['competing_pids'], [209])
        self.assertEqual(events[0]['competing_processes'][0]['executable'], '/opt/compute')

    def test_legacy_monitor_error_fails_closed_only_to_own_launcher(self):
        kill, events = self.live([RuntimeError('nvidia query failed')], mode=None)
        kill.assert_called_once_with(monitor.os.getpid(), signal.SIGINT)
        self.assertEqual(events[0]['reason'], 'gpu_priority_monitor_error')

    def test_wait_admission_requires_60_continuous_seconds_and_shares_snapshot(self):
        saved = campaign.inventory, campaign.run_gpu, campaign.deadline
        try:
            spec = importlib.util.spec_from_file_location('resume_cpu_test', HERE / 'resume.py')
            resume = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(resume)
        finally:
            campaign.inventory, campaign.run_gpu, campaign.deadline = saved
        self.process(210, '/opt/compute')
        busy = self.capture([(210, 'C', '4 MiB')])
        free = dict(captured_at='cpu-test', desktop_inventory=[], competing_processes=[], processes=[])
        tick = [0]
        observed_ticks = []
        def scan():
            observed_ticks.append(tick[0])
            return busy if tick[0] == 30 else free
        def sleep(seconds):
            tick[0] += seconds
        with mock.patch.object(campaign, 'deadline', return_value=None), \
             mock.patch.object(monitor, 'snapshot', side_effect=scan), \
             mock.patch.object(monitor, 'watch', return_value=contextlib.nullcontext()), \
             mock.patch.object(resume.time, 'monotonic', side_effect=lambda: tick[0]), \
             mock.patch.object(resume.time, 'time', side_effect=lambda: tick[0]), \
             mock.patch.object(resume.time, 'sleep', side_effect=sleep), \
             mock.patch.object(resume.timing, 'begin_wait'), \
             mock.patch.object(resume.timing, 'end_wait'), \
             mock.patch.object(resume.timing, 'snapshot', return_value={'deadline_utc': None, 'credited_wait_seconds': 0, 'policy': 'test'}), \
             mock.patch.object(campaign, 'status') as status, \
             mock.patch.object(resume, 'run_without_deadline') as runner:
            resume.wait_and_run('cpu-admission', [], [])
        self.assertEqual(observed_ticks, list(range(0, 106, 15)))
        self.assertEqual(tick[0], 105)  # New uninterrupted free interval began at 45.
        runner.assert_called_once_with('cpu-admission', [], [])
        waiting = next(x.kwargs for x in status.call_args_list if x.kwargs['state'] == 'waiting_for_gpu')
        self.assertEqual(waiting['competing_processes'][0]['pid'], 210)
        self.assertEqual(campaign.read(self.run / 'desktop-inventory.json'), free)


if __name__ == '__main__':
    unittest.main()
