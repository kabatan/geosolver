from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
BASELINE = Path(
    "/home/kabatan/work/solver-experiment-runtime/solver/research/experiments/"
    "EXP-V15-243-001/champion_v0/search_worker.py"
)
PORTAL = HERE / "portal_search_worker.py"
ARM = (
    "precision_isolated_retained_then_strict_nearroot_restart_"
    "direct_broyden_ruiz_tr_lm"
)


class GeneratedPortalWorkerTests(unittest.TestCase):
    def test_local_gate_unknown_is_exact_baseline_search_continuation(self):
        document = {
            "task": "solve",
            "variables": {"names": ["x"]},
            "construction": [],
            "constraints": [{"def": "x", "value": 0}],
            "guards": ["Bound(x, (-1, 1), inclusive=False)"],
            "bounds": [[-2.0, 2.0]],
            "answer": "x",
            "post_process": "",
        }
        payload = json.dumps(
            document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
        digest = hashlib.sha256(payload).hexdigest()
        environment = dict(os.environ)
        for name in (
            "OMP_NUM_THREADS",
            "OMP_THREAD_LIMIT",
            "OPENBLAS_NUM_THREADS",
            "MKL_NUM_THREADS",
            "NUMEXPR_NUM_THREADS",
        ):
            environment[name] = "1"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "generated.json"
            source.write_bytes(payload)
            results = {}
            for label, worker in (("baseline", BASELINE), ("portal", PORTAL)):
                output = root / f"{label}.json"
                completed = subprocess.run(
                    [
                        sys.executable,
                        str(worker),
                        "--case",
                        str(source),
                        "--case-sha256",
                        digest,
                        "--arm",
                        ARM,
                        "--seconds",
                        "4",
                        "--starts",
                        "4",
                        "--callbacks-per-start",
                        "16",
                        "--aggregate-callback-cap",
                        "64",
                        "--seed",
                        "0",
                        "--output",
                        str(output),
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    env=environment,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                results[label] = json.loads(output.read_text(encoding="utf-8"))
            for result in results.values():
                result.pop("elapsed_wall_seconds", None)
            self.assertEqual(results["portal"], results["baseline"])
            sidecar = json.loads(
                (root / "portal.json.guard-merge-portal.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                sidecar["runtime"]["mode"], "UNKNOWN_FULL_BASELINE_FALLBACK"
            )
            self.assertFalse(sidecar["runtime"]["portal_activated"])
            self.assertFalse(sidecar["individual_observations_emitted"])

    def test_cpu14_only(self):
        self.assertEqual(os.sched_getaffinity(0), {14})


if __name__ == "__main__":
    unittest.main()
