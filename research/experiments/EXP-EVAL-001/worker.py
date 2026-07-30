#!/usr/bin/env python3
"""Connect EXP-EVAL-001 to the clean 0967ff1c frozen worker CLI."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from typing import Any, Mapping


PINNED_ROOT = Path("/home/kabatan/work/solver-wt/control-0967")
SOURCE_ROOT = PINNED_ROOT / "src"
FROZEN_RUNTIME = Path("/home/kabatan/work/solver-experiment-runtime")
FROZEN_HP_WORKER = (
    FROZEN_RUNTIME
    / "solver/research/experiments/EXP-V15-243-001/candidates"
    / "point_on_circle_periodic_semantics/champion_composition_worker_no_1280.py"
)
PINNED_HP_SLOT = SOURCE_ROOT / "geotarget/hp_slot_entrypoint.py"
TELEMETRY_NAME = "EXP-EVAL-001-TELEMETRY.json"
PHASE2_DIRECTORY = "exp-eval-001-continuation"
FINALIZE_RESERVE_SECONDS = 0.25
MIN_CONTINUATION_SECONDS = 0.75


@contextmanager
def _frozen_runtime_facade(
    *, optimized_entrypoint: Any, continuation: Any, parallel: Any
):
    """Bind clean product code to the separately frozen runtime payload.

    The 0967 worktree intentionally contains source but not the large embedded
    runtime closure.  A process-local facade preserves those exact product
    modules while making their ``.../_engine/runtime`` relative paths resolve
    to the verified archive extraction.  It is removed after both phases.
    """

    required = (FROZEN_RUNTIME / "solver", FROZEN_RUNTIME / "geosolver")
    missing = [
        str(path)
        for path in (*required, FROZEN_HP_WORKER, PINNED_HP_SLOT)
        if not path.exists()
    ]
    if missing:
        raise SystemExit("frozen runtime binding is incomplete: " + ", ".join(missing))
    with tempfile.TemporaryDirectory(prefix="geotarget-exp-eval-001-") as raw:
        facade = Path(raw)
        engine = facade / "_engine"
        engine.mkdir()
        (engine / "runtime").symlink_to(FROZEN_RUNTIME, target_is_directory=True)
        # hp_slot_entrypoint resolves __file__, so a symlink would resolve back
        # into the source-only worktree.  Copying the pinned bytes is deliberate.
        shutil.copyfile(PINNED_HP_SLOT, facade / "hp_slot_entrypoint.py")

        previous_optimized_file = optimized_entrypoint.__file__
        previous_optimized_root = optimized_entrypoint.engine_root
        previous_continuation_file = continuation.__file__
        previous_hp_worker = parallel._hp_worker_path
        optimized_entrypoint.__file__ = str(facade / "optimized_entrypoint.py")
        optimized_entrypoint.engine_root = lambda: engine
        continuation.__file__ = str(facade / "continuation.py")
        parallel._hp_worker_path = lambda: FROZEN_HP_WORKER
        try:
            yield
        finally:
            parallel._hp_worker_path = previous_hp_worker
            continuation.__file__ = previous_continuation_file
            optimized_entrypoint.engine_root = previous_optimized_root
            optimized_entrypoint.__file__ = previous_optimized_file


def _arguments(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--total-seconds", type=float, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--cpu", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    values, _unknown = parser.parse_known_args(argv)
    if values.total_seconds <= 0.0:
        raise SystemExit("--total-seconds must be positive")
    return values


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2)
        + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _promote_phase2(output: Path, phase2: Path, result: Mapping[str, Any]) -> None:
    # RESULT is committed last.  If the process exits during promotion, the
    # complete initial authority remains available at the top-level output.
    for name in ("search.json", "candidate-reservoir.json"):
        source = phase2 / name
        if source.is_file():
            temporary = output / f".{name}.exp-eval-001.tmp"
            shutil.copyfile(source, temporary)
            os.replace(temporary, output / name)
    _atomic_json(output / "RESULT.json", result)


def _continuation_telemetry(base: Any) -> dict[str, Any] | None:
    value = getattr(base, "_geotarget_incremental_reservoir_telemetry", None)
    return dict(value) if isinstance(value, Mapping) else None


def _run_remaining_continuation(
    *,
    continuation: Any,
    options: argparse.Namespace,
    started: float,
) -> dict[str, Any]:
    output = options.output.resolve()
    telemetry: dict[str, Any] = {
        "schema_version": "geotarget.exp-eval-001-worker-telemetry/v1",
        "overlay_installed": True,
        "initial_checkpoint_v2_requested": True,
        "continuation_attempted": False,
        "continuation_activated": False,
        "canonical_authority_modified": False,
        "hp_or_exactification_modified": False,
    }
    remaining = options.total_seconds - (time.monotonic() - started) - FINALIZE_RESERVE_SECONDS
    telemetry["remaining_before_continuation_seconds"] = max(0.0, remaining)
    if not (output / "search.json").is_file():
        telemetry["status"] = "initial-result-retained-search-artifact-absent"
        return telemetry
    if remaining < MIN_CONTINUATION_SECONDS:
        telemetry["status"] = "initial-result-retained-no-budget"
        return telemetry
    phase2 = output / PHASE2_DIRECTORY
    phase2.mkdir(parents=True, exist_ok=False)
    telemetry["continuation_attempted"] = True
    try:
        context = continuation.prepare_context(
            runtime=FROZEN_RUNTIME,
            source=options.source.resolve(),
            source_sha256=options.source_sha256,
            cpus=(options.cpu,),
        )
        result = continuation.continue_result(
            runtime=FROZEN_RUNTIME,
            source=options.source.resolve(),
            source_sha256=options.source_sha256,
            initial_output=output,
            output=phase2,
            seconds=max(0.01, remaining),
            cpu=options.cpu,
            cpus=(options.cpu,),
            seed=options.seed,
            context=context,
        )
        elapsed = time.monotonic() - started
        # Preserve the frozen worker schema and existing exact-authority fields.
        # These keys already belong to that schema and only widen accounting to
        # include this bounded second phase.
        result = dict(result)
        result["elapsed_wall_seconds"] = elapsed
        result["within_total_wall_budget"] = elapsed <= options.total_seconds
        _promote_phase2(output, phase2, result)
        overlay = _continuation_telemetry(context.base)
        telemetry["continuation_activated"] = overlay is not None
        telemetry["overlay"] = overlay
        telemetry["status"] = (
            "continuation-promoted" if overlay is not None else "continuation-no-overlay-event"
        )
        telemetry["elapsed_wall_seconds"] = elapsed
    except Exception as error:
        # The top-level initial RESULT/search remain canonical and complete.
        telemetry["status"] = "initial-result-retained-continuation-error"
        telemetry["error_type"] = type(error).__name__
        telemetry["error"] = str(error)
    return telemetry


def main() -> None:
    if not SOURCE_ROOT.is_dir():
        raise SystemExit(f"pinned product source is unavailable: {SOURCE_ROOT}")
    options = _arguments(sys.argv[1:])
    started = time.monotonic()
    os.environ["GEOTARGET_PRODUCT_PYTHON"] = sys.executable
    inherited_pythonpath = os.environ.get("PYTHONPATH")
    os.environ["PYTHONPATH"] = os.pathsep.join(
        value
        for value in (
            str(SOURCE_ROOT),
            str(FROZEN_RUNTIME / "geosolver/src"),
            str(FROZEN_RUNTIME / "solver"),
            inherited_pythonpath,
        )
        if value
    )
    sys.path.insert(0, str(SOURCE_ROOT))

    from geotarget import continuation, parallel
    from geotarget import optimized_entrypoint

    from continuation_overlay import install as install_continuation
    from incremental_reservoir import install_initial_checkpoint

    install_continuation(continuation)
    # optimized_entrypoint imported parallel.install, whose function resolves
    # this module global at call time.  Only the checkpoint writer seam changes.
    parallel.install_reservoir_checkpoint = install_initial_checkpoint

    with _frozen_runtime_facade(
        optimized_entrypoint=optimized_entrypoint,
        continuation=continuation,
        parallel=parallel,
    ):
        original_arguments = list(sys.argv)
        sys.argv = [sys.argv[0], "--product-cpus", str(options.cpu), *sys.argv[1:]]
        try:
            optimized_entrypoint.main()
        finally:
            sys.argv = original_arguments
        if not options.execute:
            return
        telemetry = _run_remaining_continuation(
            continuation=continuation,
            options=options,
            started=started,
        )
    _atomic_json(options.output.resolve() / TELEMETRY_NAME, telemetry)


if __name__ == "__main__":
    main()
