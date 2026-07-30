"""Hash-bound full-v15 wrapper for the adaptive 64->600 hybrid."""

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
    "search_worker.py": "a19339445c55542bd849c861dc179c6a225c60d2c12e49c90e3f338c80356ce6",
    "search_adapter.py": "4b386e3706df0e2dc3cf0b14df4ca8e7427316ab3c17fb690983ba897657f4ea",
    "candidate.py": "9a449d370a2a87dea50bf3aa9cd0a3cc3d1484491e48829fd89cbdd1c82b7972",
}
SEARCH_ARM = "progressive_adaptive_hybrid_64_600"


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
    name = "geotarget_progressive_adaptive_hybrid_frozen_finalist_v15"
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
            raise SystemExit(f"adaptive hybrid dependency is unavailable: {path}")
        if _sha256(path) != EXPECTED_LOCAL_SHA256[name]:
            raise SystemExit(f"adaptive hybrid SHA-256 mismatch: {name}")


def configure(*, frozen_root: Path, python: Path):
    """Return frozen full authority with only the declared search seam rebound."""

    _verify_local_search_binding()
    base = _load_frozen(frozen_root)
    if not python.is_file():
        raise SystemExit(f"experiment Python is unavailable: {python}")
    base.PYTHON = python.absolute()
    base.SEARCH_WORKER = SEARCH_WORKER
    base.SEARCH_ADAPTER = SEARCH_ADAPTER
    base.SEARCH_CANDIDATE = SEARCH_CANDIDATE
    base.SEARCH_ARM = SEARCH_ARM
    base.EXPECTED_SEARCH_CANDIDATE_SHA256 = EXPECTED_LOCAL_SHA256["candidate.py"]
    return base


def main() -> None:
    frozen_root = Path(
        os.environ.get("GEOTARGET_FROZEN_SOLVER_ROOT", str(DEFAULT_FROZEN_ROOT))
    ).resolve()
    python = Path(
        os.environ.get("GEOTARGET_EXPERIMENT_PYTHON", sys.executable)
    ).absolute()
    configure(frozen_root=frozen_root, python=python).main()


__all__ = [
    "EXPECTED_FROZEN_WORKER_SHA256",
    "EXPECTED_LOCAL_SHA256",
    "FROZEN_WORKER_RELATIVE",
    "SEARCH_ARM",
    "configure",
    "main",
]
