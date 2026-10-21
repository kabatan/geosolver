"""Fresh-process GMB measurement; never imports GeoSolver or edits upstream code."""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import random
import sys
import time
import traceback
from collections.abc import Mapping
from pathlib import Path


def json_value(value):
    """Preserve nonfinite diagnostics explicitly, without emitting invalid JSON."""
    if isinstance(value, Mapping):
        return {str(key): json_value(item) for key, item in value.items()}
    if hasattr(value, "_asdict"):
        return json_value(value._asdict())
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if hasattr(value, "tolist"):
        return json_value(value.tolist())
    if isinstance(value, float) and not math.isfinite(value):
        return {"nonfinite": str(value)}
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise TypeError(f"unsupported model value: {type(value)}")


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(json_value(value), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def install_recording_optimizer(builder, seed, event, save_model, instrument=True):
    """Call each upstream method once. Never add TensorFlow/session evaluations."""
    original = builder.TfOptimizer

    class SeededOptimizer(original):
        def __init__(self, *args, **kwargs):
            # builder constructs a NEW graph. Setting a seed outside it is insufficient.
            builder.tf.set_random_seed(seed)
            super().__init__(*args, **kwargs)

    if not instrument:
        builder.TfOptimizer = SeededOptimizer
        return

    class RecordingOptimizer(SeededOptimizer):
        def preprocess(self):
            event("preprocess_start")
            result = super().preprocess()
            event("preprocess_end")
            return result

        def gen_inits(self):
            event("initializations_start")
            result = super().gen_inits()
            event("initializations_end", count=self.n_inits)
            return result

        def train(self, init_name):
            event("train_start", checkpoint=init_name)
            try:
                result = super().train(init_name)
            except Exception as exc:
                # Upstream catches these errors. Retain them without changing that behavior.
                event("train_error", exception=type(exc).__name__, message=str(exc))
                raise
            event("train_end", loss=result)
            return result

        def get_model(self):
            model = super().get_model()
            save_model(model)
            return model

        def solve(self):
            event("solve_start")
            result = super().solve()
            event("solve_end", models=len(result))
            return result

    builder.TfOptimizer = RecordingOptimizer


def main(request_path):
    request = json.loads(Path(request_path).read_text(encoding="utf-8"))
    directory = Path.cwd()
    origin = request["monotonic_origin"]
    model_paths = []
    stage = "startup"

    def event(name, **values):
        nonlocal stage
        stage = name
        record = dict(event=name, elapsed_seconds=time.monotonic() - origin, **values)
        with (directory / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(json_value(record), allow_nan=False, sort_keys=True) + "\n")

    def save_model(model):
        elapsed = time.monotonic() - origin
        path = directory / "models" / f"{len(model_paths):03d}.json"
        path.parent.mkdir(exist_ok=True)
        write_json(path, model)
        model_paths.append(str(path.relative_to(directory)))
        event("model_materialized", model=model_paths[-1], materialized_seconds=elapsed)

    try:
        event("worker_start", pid=os.getpid())
        if sorted(os.sched_getaffinity(0)) != [request["cpu"]]:
            raise RuntimeError("worker must be pinned before Python starts")
        if Path(sys.prefix).resolve() != Path(request["venv"]).resolve():
            raise RuntimeError("unexpected interpreter prefix")
        if platform.python_version() != request["python_version"]:
            raise RuntimeError("unexpected Python version")
        problem = Path(request["input"])
        if hashlib.sha256(problem.read_bytes()).hexdigest() != request["input_sha256"]:
            raise RuntimeError("input hash mismatch")
        sys.path.insert(0, str(Path(request["source"]) / "src"))
        random.seed(request["seed"])
        event("imports_start")
        import numpy as np
        import tensorflow as tf

        np.random.seed(request["seed"])
        import builder
        from util import DEFAULTS

        if Path(builder.__file__).resolve() != Path(request["source"]) / "src/builder.py":
            raise RuntimeError("unexpected builder import")
        if tf.config.get_visible_devices("GPU"):
            raise RuntimeError("GPU must be disabled")
        if request["upstream_defaults"] != DEFAULTS:
            raise RuntimeError("upstream defaults differ from frozen manifest")
        event("imports_end")
        identity = {
            "python": platform.python_version(),
            "executable": sys.executable,
            "builder": builder.__file__,
            "tensorflow": tf.__version__,
            "numpy": np.__version__,
            "cpu_affinity": sorted(os.sched_getaffinity(0)),
            "visible_gpus": [],
        }
        write_json(directory / "identity.json", identity)
        install_recording_optimizer(
            builder, request["seed"], event, save_model, request.get("instrument", True)
        )
        options = dict(request["options"], problem=str(problem))
        event("build_start")
        models = builder.build(options, show_plot=False, save_plot=False, encode_fig=False)
        event("build_end", models=len(models))
        if not request.get("instrument", True):
            for model in models:
                save_model(model)
        goals = []
        for model in models:
            values = [float(value) for value in model.goals.values()]
            goals.append(
                {
                    "total": len(values),
                    "passed": sum(math.isfinite(v) and v <= options["eps"] * 10 for v in values),
                    "all_passed": (
                        all(math.isfinite(v) and v <= options["eps"] * 10 for v in values)
                        if values
                        else None
                    ),
                    "threshold": options["eps"] * 10,
                }
            )
        write_json(
            directory / "child-result.json",
            {
                "schema_version": 1,
                "outcome": "model_returned" if models else "no_model",
                "models_returned": len(models),
                "model_files": model_paths,
                "goal_diagnostics": goals,
                "independent_geometry_validation": "not_performed",
                "build_complete_seconds": time.monotonic() - origin,
            },
        )
        event("worker_end")
        return 0
    except Exception as exc:
        failed_stage = stage
        traceback.print_exc()
        write_json(
            directory / "child-result.json",
            {
                "schema_version": 1,
                "outcome": "error",
                "exception": type(exc).__name__,
                "message": str(exc),
                "failure_stage": failed_stage,
                "model_files": model_paths,
            },
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
