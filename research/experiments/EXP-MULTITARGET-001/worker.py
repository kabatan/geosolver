#!/usr/bin/env python3
"""Hash-bound numerical-v15 worker with a post-answer diverse tail overlay."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import math
import os
from pathlib import Path
import sys

import candidate


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
DEFAULT_PYTHON = Path(
    os.environ.get("GEOTARGET_EXPERIMENT_PYTHON", "/home/kabatan/work/solver/.venv/bin/python")
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
        "geotarget_exp_multitarget_001_frozen_v15", path
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
    parser.add_argument("--python", type=Path, default=DEFAULT_PYTHON)
    parser.add_argument(
        "--minimum-tail-seconds",
        type=float,
        default=None,
    )
    return parser.parse_known_args(argv)


def _float_option(arguments: list[str], name: str, default: float) -> float:
    try:
        index = arguments.index(name)
    except ValueError:
        return default
    try:
        return float(arguments[index + 1])
    except (IndexError, ValueError) as error:
        raise SystemExit(f"{name} requires a finite number") from error


def _effective_minimum_tail(
    total_seconds: float,
    search_seconds: float,
    requested: float | None,
) -> float:
    if requested is not None:
        return requested
    return min(
        candidate.MINIMUM_POST_SEARCH_RESERVE_SECONDS,
        max(0.0, total_seconds - search_seconds),
    )


def main() -> None:
    overlay, frozen_arguments = _overlay_arguments(sys.argv[1:])
    if overlay.minimum_tail_seconds is not None and (
        not math.isfinite(overlay.minimum_tail_seconds)
        or overlay.minimum_tail_seconds < 0.0
    ):
        raise SystemExit("--minimum-tail-seconds must be finite and nonnegative")
    base = _load_frozen(overlay.frozen_root.resolve())
    total_seconds = _float_option(
        frozen_arguments, "--total-seconds", base.DEFAULT_TOTAL_SECONDS
    )
    search_seconds = _float_option(
        frozen_arguments, "--search-seconds", base.DEFAULT_SEARCH_SECONDS
    )
    minimum_tail_seconds = _effective_minimum_tail(
        total_seconds,
        search_seconds,
        overlay.minimum_tail_seconds,
    )
    if total_seconds - search_seconds < minimum_tail_seconds:
        raise SystemExit(
            "post-search tail is smaller than --minimum-tail-seconds: "
            f"{total_seconds - search_seconds:.6g} < {minimum_tail_seconds:.6g}"
        )
    if not overlay.python.is_file():
        raise SystemExit(f"experiment Python is unavailable: {overlay.python}")

    # The source evaluator, HP bridge, restoration worker and final descriptor
    # authority remain the frozen implementations.  Only scheduling hooks and
    # the interpreter location are replaced.
    # Preserve the venv entrypoint path.  Resolving its symlink would make the
    # child interpreter lose pyvenv.cfg and the pinned numerical packages.
    base.PYTHON = overlay.python.absolute()
    candidate.MINIMUM_POST_SEARCH_RESERVE_SECONDS = minimum_tail_seconds
    base.SELECTION_RESERVE_SECONDS = candidate.RESERVOIR_REPLAY_SECONDS
    base._service_candidates = lambda **kwargs: candidate.service_candidates(
        base, **kwargs
    )
    base._plan = candidate.patch_plan(
        base,
        base._plan,
        minimum_tail_seconds=minimum_tail_seconds,
        overlay_worker_sha256=_sha256(Path(__file__)),
        mechanism_sha256=_sha256(HERE / "candidate.py"),
    )
    sys.argv = [sys.argv[0], *frozen_arguments]
    base.main()


if __name__ == "__main__":
    main()
