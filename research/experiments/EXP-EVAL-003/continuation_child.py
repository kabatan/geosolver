#!/usr/bin/env python3
"""Run one incremental continuation window inside a killable process tree."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any, Mapping


PINNED_SOURCE = Path("/home/kabatan/work/solver-wt/control-0967/src")
EXPERIMENT_ONE = Path(
    "/home/kabatan/work/solver-wt/evaluator/research/experiments/EXP-EVAL-001"
)
FROZEN_RUNTIME = Path("/home/kabatan/work/solver-experiment-runtime")
FROZEN_HP_WORKER = (
    FROZEN_RUNTIME
    / "solver/research/experiments/EXP-V15-243-001/candidates"
    / "point_on_circle_periodic_semantics/champion_composition_worker_no_1280.py"
)
PINNED_HP_SLOT = PINNED_SOURCE / "geotarget/hp_slot_entrypoint.py"


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2)
        + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


@contextmanager
def _runtime_facade(continuation: Any, parallel: Any):
    with tempfile.TemporaryDirectory(prefix="geotarget-exp-eval-003-child-") as raw:
        facade = Path(raw)
        (facade / "_engine").mkdir()
        (facade / "_engine/runtime").symlink_to(
            FROZEN_RUNTIME, target_is_directory=True
        )
        shutil.copyfile(PINNED_HP_SLOT, facade / "hp_slot_entrypoint.py")
        old_continuation_file = continuation.__file__
        old_hp_worker = parallel._hp_worker_path
        continuation.__file__ = str(facade / "continuation.py")
        parallel._hp_worker_path = lambda: FROZEN_HP_WORKER
        try:
            yield
        finally:
            parallel._hp_worker_path = old_hp_worker
            continuation.__file__ = old_continuation_file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--initial-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=float, required=True)
    parser.add_argument("--cpu", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    arguments = parser.parse_args()
    if arguments.seconds <= 0.0:
        raise SystemExit("continuation seconds must be positive")

    python_path = (
        str(PINNED_SOURCE),
        str(EXPERIMENT_ONE),
        str(FROZEN_RUNTIME / "geosolver/src"),
        str(FROZEN_RUNTIME / "solver"),
    )
    inherited = os.environ.get("PYTHONPATH")
    os.environ["PYTHONPATH"] = os.pathsep.join(
        (*python_path, inherited) if inherited else python_path
    )
    for path in reversed(python_path[:2]):
        if path not in sys.path:
            sys.path.insert(0, path)

    from geotarget import continuation, parallel

    from continuation_overlay import install

    install(continuation)
    output = arguments.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    with _runtime_facade(continuation, parallel):
        context = continuation.prepare_context(
            runtime=FROZEN_RUNTIME,
            source=arguments.source.resolve(),
            source_sha256=arguments.source_sha256,
            cpus=(arguments.cpu,),
        )
        result = continuation.continue_result(
            runtime=FROZEN_RUNTIME,
            source=arguments.source.resolve(),
            source_sha256=arguments.source_sha256,
            initial_output=arguments.initial_output.resolve(),
            output=output,
            seconds=arguments.seconds,
            cpu=arguments.cpu,
            cpus=(arguments.cpu,),
            seed=arguments.seed,
            context=context,
        )
        telemetry = getattr(
            context.base, "_geotarget_incremental_reservoir_telemetry", None
        )
    _atomic_json(output / "RESULT.json", dict(result))
    _atomic_json(
        output / "EXP-EVAL-003-CHILD-TELEMETRY.json",
        {
            "schema_version": "geotarget.exp-eval-003-child-telemetry/v1",
            "incremental_overlay": (
                dict(telemetry) if isinstance(telemetry, Mapping) else None
            ),
            "canonical_authority_modified": False,
            "hp_or_exactification_modified": False,
        },
    )


if __name__ == "__main__":
    main()
