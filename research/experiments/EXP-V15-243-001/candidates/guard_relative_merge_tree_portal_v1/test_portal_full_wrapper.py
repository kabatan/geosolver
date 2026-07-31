from __future__ import annotations

import os
from pathlib import Path
import unittest

import portal_full_wrapper


class PortalFullWrapperTests(unittest.TestCase):
    def test_only_search_worker_is_rebound(self):
        root = Path("/home/kabatan/work/solver-experiment-runtime/solver")
        control = portal_full_wrapper.configure(frozen_root=root, enable_portal=False)
        base = control.CHAMPION.BASE
        original = {
            "SEARCH_ADAPTER": base.SEARCH_ADAPTER,
            "SEARCH_CANDIDATE": base.SEARCH_CANDIDATE,
            "SEARCH_ARM": base.SEARCH_ARM,
            "EXPECTED_SEARCH_CANDIDATE_SHA256": base.EXPECTED_SEARCH_CANDIDATE_SHA256,
        }
        configured = portal_full_wrapper.configure(frozen_root=root, enable_portal=True)
        rebound = configured.CHAMPION.BASE
        self.assertEqual(
            rebound.SEARCH_WORKER, portal_full_wrapper.PORTAL_SEARCH_WORKER
        )
        for name, expected in original.items():
            self.assertEqual(getattr(rebound, name), expected)

    def test_cpu14_only(self):
        self.assertEqual(os.sched_getaffinity(0), {14})


if __name__ == "__main__":
    unittest.main()
