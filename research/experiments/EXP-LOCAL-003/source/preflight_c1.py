"""No-output formal launcher preflight for EXP-LOCAL-003 C1."""

from __future__ import annotations

import os
import sys
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = SOURCE_ROOT.parents[3]
PYTHON_SOURCE = REPOSITORY_ROOT / "python" / "src"
_BLOCKED_ENVIRONMENT_PREFIXES = (
    "COVERAGE_",
    "COV_CORE_",
    "PYTEST_",
    "PYTHON",
    "DD_",
    "OTEL_",
    "NEW_RELIC_",
    "SENTRY_",
    "PYDEVD_",
)


def _verify_preimport_hygiene() -> None:
    if (
        sys.flags.isolated != 1
        or sys.flags.ignore_environment != 1
        or sys.flags.no_user_site != 1
        or sys.flags.safe_path is not True
        or sys.flags.dont_write_bytecode != 1
        or sys.flags.no_site != 1
        or sys.flags.optimize != 0
        or "site" in sys.modules
    ):
        raise RuntimeError("C1 preflight requires exact `python -I -B -S`")
    blocked = sorted(
        name
        for name in os.environ
        if name.upper().startswith(_BLOCKED_ENVIRONMENT_PREFIXES)
    )
    if blocked:
        raise RuntimeError(f"C1 preflight has injection environment: {blocked}")
    if any("site-packages" in value.casefold() for value in sys.path):
        raise RuntimeError("site-packages was active before the C1 preflight")
    expected = Path(__file__).resolve(strict=True)
    main_file = getattr(sys.modules.get("__main__"), "__file__", None)
    if (
        Path(sys.argv[0]).resolve(strict=True) != expected
        or not isinstance(main_file, str)
        or Path(main_file).resolve(strict=True) != expected
        or Path.cwd().resolve(strict=True) != REPOSITORY_ROOT.resolve(strict=True)
    ):
        raise RuntimeError("C1 preflight must execute directly at repository root")
    for root in (SOURCE_ROOT, PYTHON_SOURCE):
        for current, directories, files in os.walk(root, followlinks=False):
            if "__pycache__" in directories or any(
                name.casefold().endswith((".pyc", ".pyo")) for name in files
            ):
                raise RuntimeError(f"stale project bytecode exists under {current}")


def _activate_formal_import_paths() -> None:
    executable = Path(sys.executable).resolve(strict=True)
    venv = (REPOSITORY_ROOT / "python" / ".venv").resolve(strict=True)
    if executable.parent.parent != venv or executable.name.casefold() != "python.exe":
        raise RuntimeError("C1 preflight is not using the fixed project venv")
    site_packages = venv / "Lib" / "site-packages"
    if not site_packages.is_dir():
        raise RuntimeError("fixed project venv site-packages is unavailable")
    for path in reversed((SOURCE_ROOT, PYTHON_SOURCE, site_packages)):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))


if __name__ == "__main__":
    _verify_preimport_hygiene()
    _activate_formal_import_paths()
else:
    for path in (PYTHON_SOURCE, SOURCE_ROOT):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))

import materialize_development as materializer  # noqa: E402


def main() -> int:
    if len(sys.argv) != 1:
        raise materializer.MaterializationError("C1 preflight accepts no options")
    materializer.preflight()
    print("EXP-LOCAL-003 C1 preflight passed; no attempt was claimed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
