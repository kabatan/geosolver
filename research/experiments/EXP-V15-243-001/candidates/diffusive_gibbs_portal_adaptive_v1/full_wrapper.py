"""Exact common-control authority with only DiGS discovery rebound."""

from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
DEFAULT_FROZEN_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver")
UPSTREAM_PATH = HERE.parent / "progressive_adaptive_hybrid_v1" / "full_wrapper.py"
UPSTREAM_SHA256 = "4c4640a3bce5719d66f577c0093eabe93916476e319b8a595003a16f73dfb9b4"
SEARCH_WORKER = HERE / "search_worker.py"
SEARCH_ADAPTER = HERE / "search_adapter.py"
SEARCH_CANDIDATE = HERE.parent / "progressive_adaptive_hybrid_v1" / "candidate.py"
EXPECTED_LOCAL_SHA256 = {
    "search_worker.py": "5bec02c7c20a0e2d8dc786f2b8a877eda02040a3876d55db3299911da6bd193d",
    "search_adapter.py": "fcf30837f3f89272c73a7e439b84f7ac3d3f284f534cb2fa7f041532f2ee823c",
    "candidate.py": "9a449d370a2a87dea50bf3aa9cd0a3cc3d1484491e48829fd89cbdd1c82b7972",
}
SEARCH_ARM = "progressive_adaptive_hybrid_64_600_plus_digs_portal"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_upstream():
    if _sha256(UPSTREAM_PATH) != UPSTREAM_SHA256:
        raise SystemExit("current adaptive full-wrapper SHA-256 mismatch")
    name = "geotarget_digs_current_adaptive_full_wrapper"
    specification = importlib.util.spec_from_file_location(name, UPSTREAM_PATH)
    if specification is None or specification.loader is None:
        raise SystemExit("cannot load current adaptive full wrapper")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def configure(*, frozen_root: Path, enable_portal: bool = True):
    upstream = _load_upstream()
    control = upstream.configure(frozen_root=frozen_root, enable_hybrid=False)
    upstream._verify_control_stack(control)
    if not enable_portal:
        return control
    paths = {
        "search_worker.py": SEARCH_WORKER,
        "search_adapter.py": SEARCH_ADAPTER,
        "candidate.py": SEARCH_CANDIDATE,
    }
    for name, path in paths.items():
        if not path.is_file() or _sha256(path) != EXPECTED_LOCAL_SHA256[name]:
            raise SystemExit(f"DiGS integration SHA-256 mismatch: {name}")
    base = control.CHAMPION.BASE
    base.SEARCH_WORKER = SEARCH_WORKER
    base.SEARCH_ADAPTER = SEARCH_ADAPTER
    base.SEARCH_CANDIDATE = SEARCH_CANDIDATE
    base.SEARCH_ARM = SEARCH_ARM
    base.EXPECTED_SEARCH_CANDIDATE_SHA256 = EXPECTED_LOCAL_SHA256["candidate.py"]
    return control


def main() -> None:
    frozen_root = Path(os.environ.get(
        "GEOTARGET_FROZEN_SOLVER_ROOT", str(DEFAULT_FROZEN_ROOT)
    )).resolve()
    configure(frozen_root=frozen_root, enable_portal=True).main()


if __name__ == "__main__":
    main()
