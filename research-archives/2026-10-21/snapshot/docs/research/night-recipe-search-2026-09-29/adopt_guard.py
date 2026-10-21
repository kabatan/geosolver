"""Restore supervision of one live campaign guard without repeating its job."""
import argparse
import fcntl
import os
from pathlib import Path
import signal
import sys
import time

import resume
import campaign as c
import gpu_priority


def process(pid):
    try:
        fields = (Path('/proc') / str(pid) / 'stat').read_text().rsplit(')', 1)[1].split()
        return fields[0], int(fields[2]), int(fields[19])
    except FileNotFoundError:
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--guard-pid', type=int, required=True)
    ap.add_argument('--job', required=True)
    ap.add_argument('--old-launcher', type=int, required=True)
    args = ap.parse_args()
    with (c.RUN / 'adopt-guard.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert not (Path('/proc') / str(args.old_launcher)).exists(), 'Original launcher still exists'
        active = c.read(c.RUN / 'active-process.json')
        assert active.get('owned_by') == 'night_recipe_search_20260929'
        assert active['pid'] == active['pgid'] == args.guard_pid and active['job'] == args.job
        identity = process(args.guard_pid)
        assert identity and identity[0] != 'Z' and identity[1] == args.guard_pid
        argv = (Path('/proc') / str(args.guard_pid) / 'cmdline').read_bytes().decode().split('\0')
        assert str(c.GPU) in argv and 'night20260929-' + args.job in argv
        c.verify_manifest()

        def alive():
            state = process(args.guard_pid)
            if state is None or state[0] == 'Z':
                return False
            assert state[1:] == identity[1:], 'Guard identity changed'
            return True

        def terminate(signum, frame):
            raise SystemExit(128 + signum)

        signal.signal(signal.SIGTERM, terminate)
        signal.signal(signal.SIGHUP, terminate)
        c.write(c.RUN / 'adoption.json', dict(time=c.stamp(), job=args.job,
                guard_pid=args.guard_pid, supervisor_pid=os.getpid(),
                old_launcher_pid=args.old_launcher, status='monitoring_existing_attempt'))
        continuation = c.read(c.RUN / 'continuation.json')
        continuation.update(launcher_pid=os.getpid(), launcher_script='adopt_guard.py then resume initial',
                            updated_utc=c.stamp(), recovery='Supervising existing S512 main attempt after launcher exit 143; no duplicated generation.')
        c.write(c.RUN / 'continuation.json', continuation)
        try:
            with gpu_priority.watch(args.job):
                while alive():
                    time.sleep(1)
        except BaseException as exc:
            if alive():
                os.killpg(args.guard_pid, signal.SIGTERM)
                for _ in range(100):
                    if not alive():
                        break
                    time.sleep(0.1)
                if alive():
                    os.killpg(args.guard_pid, signal.SIGKILL)
            c.status(state='interrupted', job=args.job, error=repr(exc), adopted_guard=True)
            c.write(c.RUN / 'active-process.json', dict(active=False, last_job=args.job, interrupted=True))
            raise
        guard_receipt = c.SHARED / ('night20260929-' + args.job) / 'receipt.json'
        receipt = c.read(guard_receipt)
        assert receipt['status'] == 'complete' and receipt['returncode'] == 0, 'Adopted job did not complete; preserve and investigate'
        output = c.RUN / 'outputs' / args.job.removeprefix('eval-')
        result = c.read(output / 'receipt.json')
        assert result['status'] == 'complete', 'Generation receipt incomplete'
        for filename, digest in receipt['inputs'].items():
            assert c.sha(filename) == digest, ('Input changed', filename)
        c.write(c.RUN / 'adoption.json', dict(time=c.stamp(), job=args.job,
                guard_pid=args.guard_pid, supervisor_pid=os.getpid(),
                old_launcher_pid=args.old_launcher, status='existing_attempt_completed',
                guard_receipt_sha256=c.sha(guard_receipt), output_receipt_sha256=c.sha(output / 'receipt.json')))
        c.write(c.RUN / 'active-process.json', dict(active=False, last_job=args.job))
        c.status(state='job_complete', job=args.job, adopted_guard=True, returncode=0)
        sys.argv = ['resume.py', 'initial']
        c.main()


if __name__ == '__main__':
    main()
