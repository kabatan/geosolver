#!/usr/bin/env python3
"""Hash-bound frozen numerical-v15 with post-answer-only adaptation."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import sys

import candidate_v2


HERE = Path(__file__).resolve().parent
DEFAULT_FROZEN_ROOT = Path(
    os.environ.get(
        "GEOTARGET_FROZEN_SOLVER_ROOT",
        "/home/kabatan/work/solver-experiment-runtime/solver",
    )
)
FROZEN_RELATIVE_WORKER = Path(
    "research/experiments/EXP-REAL61-008/finalist_numeric_worker_v15/worker.py"
)
EXPECTED_FROZEN_WORKER_SHA256 = (
    "330e52c75b98d3c58a1422cec415b5a53673ebafb7e90789a271df34a308309d"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_frozen(root: Path):
    path = root / FROZEN_RELATIVE_WORKER
    if not path.is_file():
        raise SystemExit(f"frozen numerical-v15 worker is unavailable: {path}")
    if _sha256(path) != EXPECTED_FROZEN_WORKER_SHA256:
        raise SystemExit("frozen numerical-v15 worker SHA-256 mismatch")
    specification = importlib.util.spec_from_file_location(
        "geotarget_exp_multitarget_001_frozen_v15_post_answer_v2", path
    )
    if specification is None or specification.loader is None:
        raise SystemExit(f"cannot import frozen worker: {path}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def _overlay_arguments(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--frozen-root", type=Path, default=DEFAULT_FROZEN_ROOT)
    return parser.parse_known_args(argv)


def main() -> None:
    overlay, frozen_arguments = _overlay_arguments(sys.argv[1:])
    # Hash overlay files before importing frozen v15.  Its PROCESS_STARTED is
    # initialized during import, so provenance I/O must not consume its budget.
    overlay_worker_sha256 = _sha256(Path(__file__))
    mechanism_sha256 = _sha256(HERE / "candidate_v2.py")
    base = _load_frozen(overlay.frozen_root.resolve())

    # In particular, do not patch PYTHON, SELECTION_RESERVE_SECONDS,
    # _run_search, _fresh_replay_candidates, or any deadline.  Those must stay
    # byte-for-byte/float-for-float on the frozen path through confirmation.
    base._service_candidates = lambda **kwargs: candidate_v2.service_candidates(
        base, **kwargs
    )
    base._plan = candidate_v2.patch_plan(
        base._plan,
        overlay_worker_sha256=overlay_worker_sha256,
        mechanism_sha256=mechanism_sha256,
    )
    sys.argv = [sys.argv[0], *frozen_arguments]
    base.main()


if __name__ == "__main__":
    main()
