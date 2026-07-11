"""Static invariants shared by every non-candidate formal Python entry point."""

from __future__ import annotations

import unittest
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parent
FORMAL_ENTRYPOINTS = (
    "capture_environment_lock.py",
    "seal_main_stage.py",
    "freeze_preimplementation.py",
    "preflight_c1.py",
    "launch_c1.py",
    "launch_c2_equivalence.py",
    "launch_execution_lock.py",
    "launch_locked.py",
    "assess_stage.py",
    "verify_final_authorization.py",
)
PREIMPORT_WRAPPERS = (
    ("capture_environment_lock.py", "import materialize_development as contract"),
    ("freeze_preimplementation.py", "import materialize_development as contract"),
    ("preflight_c1.py", "import materialize_development as materializer"),
    ("seal_main_stage.py", "import materialize_development as materialization"),
)


class FormalPythonBoundaryTests(unittest.TestCase):
    def test_every_entrypoint_closes_site_environment_and_bytecode_surfaces(
        self,
    ) -> None:
        required_fragments = (
            "sys.flags.no_site",
            "sys.flags.safe_path",
            "sys.flags.optimize",
            "-I -B -S",
            "_BLOCKED_ENVIRONMENT_PREFIXES",
            '"COVERAGE_"',
            '"COV_CORE_"',
            '"PYTEST_"',
            '"PYTHON"',
            '"DD_"',
            '"OTEL_"',
            '"NEW_RELIC_"',
            '"SENTRY_"',
            '"PYDEVD_"',
            '"site" in sys.modules',
            '"site-packages"',
            "sys.executable",
            "os.walk",
            '".pyc"',
            '".pyo"',
        )
        for filename in FORMAL_ENTRYPOINTS:
            with self.subTest(entrypoint=filename):
                payload = (SOURCE_ROOT / filename).read_text(encoding="utf-8")
                for fragment in required_fragments:
                    self.assertIn(fragment, payload)
                self.assertNotIn("Path(sys.prefix)", payload)
                self.assertNotIn("\nimport site", payload)

    def test_c0_wrappers_validate_before_their_first_project_import(self) -> None:
        guard = 'if __name__ == "__main__":\n    _verify_preimport_hygiene()'
        for filename, project_import in PREIMPORT_WRAPPERS:
            with self.subTest(entrypoint=filename):
                payload = (SOURCE_ROOT / filename).read_text(encoding="utf-8")
                self.assertLess(payload.index(guard), payload.index(project_import))


if __name__ == "__main__":
    unittest.main()
