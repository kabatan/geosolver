"""DA15: one hand-formalized premise template, automatic SSS/query/label batch."""
from __future__ import annotations

from fractions import Fraction
import hashlib
import json
from pathlib import Path
import random

from geosolver import SolveOptions, solve
from premises_cpu_trial import DA15, HERE, problem


SEED = 20260927
QUERIES = [("AF", "Distance(A,F)"), ("OF", "Distance(O,F)"), ("AO", "Distance(A,O)")]
DOMAIN = [
    {"left": "Dot(Vector(A,D),Vector(A,M))", "operator": ">", "right": 0},
    {"left": "Dot(Vector(A,E),Vector(A,M))", "operator": ">", "right": 0},
    {"left": "Area(A,F,B)+Area(B,F,C)+Area(C,F,A)",
     "operator": "=", "right": "Area(A,B,C)"},
    *[{"left": expr, "operator": ">", "right": 0}
      for expr in ["Area(A,F,B)", "Area(B,F,C)", "Area(C,F,A)"]],
]


def main():
    rng = random.Random(SEED)
    seen = set()
    shapes = []
    sampling_rejects = []
    attempts = 0
    while len(shapes) < 3:
        attempts += 1
        a, b, c = [rng.randint(5, 18) for _ in range(3)]
        sides = sorted((a, b, c))
        signature = [str(Fraction(v, sides[-1])) for v in sides]
        if len(set(sides)) != 3 or sides[-1] ** 2 >= sides[0] ** 2 + sides[1] ** 2:
            sampling_rejects.append({"attempt": attempts, "sides": [a,b,c],
                                     "reason": "not_acute_scalene"})
            continue
        if tuple(signature) in seen:
            sampling_rejects.append({"attempt": attempts, "sides": [a,b,c],
                                     "reason": "similar_shape"})
            continue
        seen.add(tuple(signature))
        shapes.append({"BC": a, "CA": b, "AB": c, "signature": signature})

    receipt = {"purpose": "mechanical SSS/query generation from one premise DSL",
               "seed": SEED, "gpu_used": False,
               "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "formalization": "DA15 premises manually encoded once; no theorem used",
               "shapes": shapes, "sampling_rejects": sampling_rejects, "rows": []}
    for index, shape in enumerate(shapes):
        a, b, c = [shape[k] for k in ["BC", "CA", "AB"]]
        x = Fraction(c*c+a*a-b*b, 2*a)
        height2 = c*c-x*x
        triangle = [("A", f"Point({x},sqrt({height2}))"),
                    ("B", "Point(0,0)"), ("C", f"Point({a},0)")]
        for name, target in QUERIES:
            task = problem(f"DA15_shape{index}_{name}", triangle + DA15[3:], target, DOMAIN)
            # Public prompt includes only source premises and base ABC lengths.
            prompt = (f"鋭角不等辺三角形ABCで、AB={c}, BC={a}, CA={b}とする。"
                      "外心をO、BCの中点をMとする。AB,ACの垂直二等分線と"
                      "半直線AMの交点をそれぞれD,Eとし、F=BD∩CEは三角形ABCの内部にある。"
                      f"{name}の長さを求めよ。")
            result = solve(task, SolveOptions(time_limit_seconds=180, cores=1, seed=0))
            row = {"shape_index": index, "query": name, "public_prompt": prompt,
                   "problem": task.model_dump(mode="json"),
                   "result": result.model_dump(mode="json"),
                   "adopted": result.status == "solved" and len(result.answers) == 1}
            receipt["rows"].append(row)
            print(task.id, result.status, [ans.decimal for ans in result.answers], flush=True)
            (HERE / "CPU_BATCH_RECEIPT.json").write_text(
                json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
