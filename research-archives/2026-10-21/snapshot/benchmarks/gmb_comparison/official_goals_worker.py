"""Evaluate pinned upstream GMB goals on fixed saved objects, with no optimization.

Run with GMB's Python 3.8 environment. Named objects are supplied as float64
feeds; only original Eval instructions are evaluated. No named construction is
recomputed, and neither the assumptions nor overall configuration are certified.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path


def checked_read(path, expected):
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("input_hash_mismatch: " + str(path))
    return data


def finite(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):  # noqa: UP038
        raise ValueError("invalid_coordinate")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("nonfinite_coordinate")
    return result


def fixed_objects(model, kind):
    """Only change representation, never move or repair geometric objects."""
    if kind == "gmb":
        points = {k: [finite(v["x"]), finite(v["y"])] for k, v in model["named_points"].items()}
        lines = {
            k: [finite(v["n"]["x"]), finite(v["n"]["y"]), finite(v["r"])]
            for k, v in model["named_lines"].items()
        }
        circles = {
            k: [finite(v["center"]["x"]), finite(v["center"]["y"]), finite(v["radius"])]
            for k, v in model["named_circles"].items()
        }
    elif kind == "geosolver":
        witness = model["witness"]
        points = {k: list(map(finite, v)) for k, v in witness["points"].items()}
        circles = {
            k: [*map(finite, v["center"]), finite(v["radius"])]
            for k, v in witness["circles"].items()
        }
        lines = {}
        for name, coefficients in witness["lines"].items():
            a, b, c = map(finite, coefficients)
            magnitude = math.hypot(a, b)
            if not math.isfinite(magnitude) or magnitude == 0:
                raise ValueError("invalid_line_normal")
            # a*x + b*y + c = 0 -> n dot p = r, upper-half-plane normal.
            sign = -1 if b < 0 or (b == 0 and a < 0) else 1
            lines[name] = [sign * a / magnitude, sign * b / magnitude, -sign * c / magnitude]
    else:
        raise ValueError("unsupported_model_kind")
    for values, size in ((points, 2), (lines, 3), (circles, 3)):
        if any(len(v) != size or not all(math.isfinite(x) for x in v) for v in values.values()):
            raise ValueError("invalid_object")
    return {"points": points, "lines": lines, "circles": circles}


class GoalEvaluator:
    """Use upstream parser, geometry, residual transforms and goal registration."""

    def __init__(self, source):
        import tensorflow.compat.v1 as tf
        from instruction import Eval
        from instruction_reader import InstructionReader
        from optimizer import CircleNF, LineNF
        from tf_optimizer import TfOptimizer
        from util import DEFAULTS

        self.tf = tf
        self.threshold = DEFAULTS["eps"] * 10
        reader = InstructionReader(source.splitlines(keepends=True))
        goals = [item for item in reader.instructions if isinstance(item, Eval)]
        self.goal_clauses = len(goals)
        self.graph = tf.Graph()
        self.slots = {"points": {}, "lines": {}, "circles": {}}
        with self.graph.as_default():
            self.engine = TfOptimizer(
                [], dict(DEFAULTS, verbosity=-1), [], [], [], [], [], self.graph
            )

            def slots(kind, name, count):
                values = [tf.placeholder(tf.float64, shape=()) for _ in range(count)]
                self.slots[kind][name] = values
                return values

            for obj in reader.points:
                x, y = slots("points", obj.val, 2)
                self.engine.name2pt[obj] = self.engine.get_point(x, y)
            for obj in reader.lines:
                x, y, r = slots("lines", obj.val, 3)
                self.engine.name2line[obj] = LineNF(self.engine.get_point(x, y), r)
            for obj in reader.circles:
                x, y, r = slots("circles", obj.val, 3)
                self.engine.name2circ[obj] = CircleNF(self.engine.get_point(x, y), r)
            for goal in goals:
                self.engine.eval_cons(goal)
            if tf.global_variables() or any(
                op.type.startswith(("Random", "Variable", "Assign", "Apply"))
                for op in self.graph.get_operations()
            ):
                raise ValueError("goal_graph_must_not_optimize_or_sample")

    def evaluate(self, model, kind):
        objects = fixed_objects(model, kind)
        feeds = {}
        for category, names in self.slots.items():
            if set(objects[category]) != set(names):
                raise ValueError("named_object_set_mismatch: " + category)
            for name, tensors in names.items():
                # Python 3.8 has no strict=; dimensions were checked above.
                feeds.update(zip(tensors, objects[category][name]))  # noqa: B905
        values = self.engine.sess.run(self.engine.goals, feed_dict=feeds)
        values = {key: float(value) for key, value in values.items()}
        is_finite = all(math.isfinite(value) for value in values.values())
        return {
            "status": "no_eval" if not values else ("evaluated" if is_finite else "nonfinite"),
            "goal_clause_count": self.goal_clauses,
            "goal_value_count": len(values),
            "threshold": self.threshold,
            "values": {
                k: v if math.isfinite(v) else {"nonfinite": str(v)} for k, v in values.items()
            },
            "all_passed": (is_finite and all(v <= self.threshold for v in values.values()))
            if values
            else None,
            "all_values_finite": is_finite,
            "optimization_steps": 0,
        }

    def close(self):
        self.engine.sess.close()


def main(request_path, output_path):
    request = json.loads(Path(request_path).read_text())
    for relative, digest in request["upstream_sha256"].items():
        checked_read(Path(request["upstream_source"]) / relative, digest)
    sys.path.insert(0, str(Path(request["upstream_source"]) / "src"))
    import tensorflow.compat.v1 as tf

    tf.disable_v2_behavior()
    tf.logging.set_verbosity(tf.logging.ERROR)
    evaluators = {}
    try:
        with Path(output_path).open("x", encoding="utf-8") as output:
            for job in request["jobs"]:
                source = checked_read(job["input"], job["input_sha256"]).decode()
                model = json.loads(checked_read(job["model"], job["model_sha256"]))
                key = job["input_sha256"]
                try:
                    if key not in evaluators:
                        evaluators[key] = GoalEvaluator(source)
                    if evaluators[key].goal_clauses != job["goal_clause_count"]:
                        raise ValueError("official_goal_clause_count_mismatch")
                    result = evaluators[key].evaluate(model, job["method"])
                except Exception as error:
                    result = {
                        "status": "evaluation_error",
                        "all_passed": False,
                        "error_type": type(error).__name__,
                        "error": str(error),
                    }
                output.write(
                    json.dumps(dict(job=job["id"], result=result), sort_keys=True, allow_nan=False)
                    + "\n"
                )
                output.flush()
                print(job["id"], result["status"], result["all_passed"], flush=True)
    finally:
        for evaluator in evaluators.values():
            evaluator.close()


if __name__ == "__main__":
    main(*sys.argv[1:])
