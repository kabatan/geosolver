from __future__ import annotations

import os
from pathlib import Path
import unittest

import collect_full_wrapper


class FullWrapperTests(unittest.TestCase):
    def test_only_search_worker_is_rebound(self):
        root = Path("/home/kabatan/work/solver-experiment-runtime/solver")
        control = collect_full_wrapper.configure(frozen_root=root, enable_collect=False)
        base = control.CHAMPION.BASE
        original = {
            "SEARCH_WORKER": base.SEARCH_WORKER,
            "SEARCH_ADAPTER": base.SEARCH_ADAPTER,
            "SEARCH_CANDIDATE": base.SEARCH_CANDIDATE,
            "SEARCH_ARM": base.SEARCH_ARM,
            "EXPECTED_SEARCH_CANDIDATE_SHA256": base.EXPECTED_SEARCH_CANDIDATE_SHA256,
        }
        configured = collect_full_wrapper.configure(frozen_root=root, enable_collect=True)
        rebound = configured.CHAMPION.BASE
        self.assertEqual(rebound.SEARCH_WORKER, collect_full_wrapper.COLLECT_SEARCH_WORKER)
        for name in (
            "SEARCH_ADAPTER",
            "SEARCH_CANDIDATE",
            "SEARCH_ARM",
            "EXPECTED_SEARCH_CANDIDATE_SHA256",
        ):
            self.assertEqual(getattr(rebound, name), original[name])

    def test_cpu14_only(self):
        self.assertEqual(os.sched_getaffinity(0), {14})


if __name__ == "__main__":
    unittest.main()
