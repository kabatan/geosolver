"""Hash-bound full-v15 wrapper for progressive search profiles.

Only the discovery worker seam is replaced.  The frozen finalist owns source
replay, provisional clustering, HP scheduling, restoration, canonical target
authority, exact descriptor deduplication, and the final result schema.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
DEFAULT_FROZEN_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver")
FROZEN_WORKER_RELATIVE = Path(
    "research/experiments/EXP-REAL61-008/finalist_numeric_worker_v15/worker.py"
)
EXPECTED_FROZEN_WORKER_SHA256 = (
    "330e52c75b98d3c58a1422cec415b5a53673ebafb7e90789a271df34a308309d"
)
SEARCH_WORKER = HERE / "search_worker.py"
SEARCH_ADAPTER = HERE / "search_adapter.py"
SEARCH_CANDIDATE = HERE / "candidate.py"
EXPECTED_LOCAL_SHA256 = {
    "search_worker.py": "c60752971a5e7bd95d8e4b73151123457961874f191cb0ead877bb08de812332",
    "search_adapter.py": "244c6125ce7a51d03368bc514ab5f99f1e3e0dffa989a678c70fe0ffc5e30d94",
    "candidate.py": "931d1a338e068306c5ad9515f8f111a65df94961d32054a72688775830f53c4d",
}
ARM_BY_PROFILE = {
    "64-192-600": "progressive_local_budget_64_192_600",
    "96-300-600": "progressive_local_budget_96_300_600",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_frozen(root: Path):
    path = root / FROZEN_WORKER_RELATIVE
    if not path.is_file():
        raise SystemExit(f"frozen finalist v15 worker is unavailable: {path}")
    if _sha256(path) != EXPECTED_FROZEN_WORKER_SHA256:
        raise SystemExit("frozen finalist v15 worker SHA-256 mismatch")
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    name = "geotarget_progressive_local_budget_frozen_finalist_v15"
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise SystemExit(f"cannot import frozen finalist v15 worker: {path}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _verify_local_search_binding() -> None:
    paths = {
        "search_worker.py": SEARCH_WORKER,
        "search_adapter.py": SEARCH_ADAPTER,
        "candidate.py": SEARCH_CANDIDATE,
    }
    for name, path in paths.items():
        if not path.is_file():
            raise SystemExit(f"progressive search dependency is unavailable: {path}")
        if _sha256(path) != EXPECTED_LOCAL_SHA256[name]:
            raise SystemExit(f"progressive search dependency SHA-256 mismatch: {name}")


def configure(profile: str, *, frozen_root: Path, python: Path):
    """Return the frozen module with only its declared search seam rebound."""

    try:
        search_arm = ARM_BY_PROFILE[profile]
    except KeyError as error:
        raise SystemExit(f"unknown progressive profile: {profile!r}") from error
    _verify_local_search_binding()
    base = _load_frozen(frozen_root)
    if not python.is_file():
        raise SystemExit(f"experiment Python is unavailable: {python}")

    # Preserve the venv entrypoint rather than resolving its symlink.  No HP,
    # replay, authority, descriptor, timing, or result-schema hook is replaced.
    base.PYTHON = python.absolute()
    base.SEARCH_WORKER = SEARCH_WORKER
    base.SEARCH_ADAPTER = SEARCH_ADAPTER
    base.SEARCH_CANDIDATE = SEARCH_CANDIDATE
    base.SEARCH_ARM = search_arm
    base.EXPECTED_SEARCH_CANDIDATE_SHA256 = EXPECTED_LOCAL_SHA256["candidate.py"]
    return base


def main(profile: str) -> None:
    frozen_root = Path(
        os.environ.get("GEOTARGET_FROZEN_SOLVER_ROOT", str(DEFAULT_FROZEN_ROOT))
    ).resolve()
    python = Path(
        os.environ.get("GEOTARGET_EXPERIMENT_PYTHON", sys.executable)
    ).absolute()
    base = configure(profile, frozen_root=frozen_root, python=python)
    base.main()


__all__ = [
    "ARM_BY_PROFILE",
    "EXPECTED_FROZEN_WORKER_SHA256",
    "EXPECTED_LOCAL_SHA256",
    "FROZEN_WORKER_RELATIVE",
    "configure",
    "main",
]
