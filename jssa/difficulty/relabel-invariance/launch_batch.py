"""Keep one nohup batch alive in its tool session; never aggregate batches.

stage2.start supplies all immutable-schedule and no-rerun guards. The supervisor
waits only for that one detached batch, so closing the short launch command does
not prematurely destroy the sandbox's child process namespace. Use nohup and
an asynchronous exec session; inspect the existing receipts while it runs.
"""
from __future__ import annotations

import argparse
import os

import stage2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch", type=int)
    args = parser.parse_args()
    if not 0 <= args.batch < 210:
        raise ValueError("batch is outside the locked schedule")
    stage2.start(args.batch)
    pid, status = os.wait()
    receipt = stage2.read(stage2.paths(args.batch)[2])
    print({"supervised_pid": pid, "wait_status": status, "state": receipt.get("state")}, flush=True)
    if status != 0 or receipt.get("state") != "complete":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
