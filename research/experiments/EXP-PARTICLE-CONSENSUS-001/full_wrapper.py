"""Exact common-control authority with only particle discovery rebound."""

from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
DEFAULT_FROZEN_ROOT = Path("/home/kabatan/work/solver-experiment-runtime/solver")
UPSTREAM_PATH = (
    HERE.parent / "EXP-V15-243-001/candidates/progressive_adaptive_hybrid_v1/full_wrapper.py"
)
UPSTREAM_SHA256 = "4c4640a3bce5719d66f577c0093eabe93916476e319b8a595003a16f73dfb9b4"
SEARCH_WORKER = HERE / "real_search_worker.py"
SEARCH_ADAPTER = HERE / "real_adapter.py"
SEARCH_CANDIDATE = HERE / "candidate.py"
EXPECTED_LOCAL_SHA256 = {
    "real_search_worker.py": "0f0f1983f2684caf043d51be8df3b70e0f502ea9ee6531b8c4d0e5ed8084ff61",
    "real_adapter.py": "3242434e21971a65753161adf8fb2119aa3001a628abdbe654cc08f2353e790a",
    "candidate.py": "1d24ab131de635ef47c5f9f2230822f3d62a6d7b5787be95e26089d59c924a4e",
}
SEARCH_ARM = "few_particle_equality_forced_prefix_25pct"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_upstream():
    if _sha256(UPSTREAM_PATH) != UPSTREAM_SHA256:
        raise SystemExit("current adaptive full-wrapper SHA-256 mismatch")
    name = "geotarget_particle_current_adaptive_full_wrapper"
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
        "real_search_worker.py": SEARCH_WORKER,
        "real_adapter.py": SEARCH_ADAPTER,
        "candidate.py": SEARCH_CANDIDATE,
    }
    for name, path in paths.items():
        if not path.is_file() or _sha256(path) != EXPECTED_LOCAL_SHA256[name]:
            raise SystemExit(f"particle integration SHA-256 mismatch: {name}")
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
