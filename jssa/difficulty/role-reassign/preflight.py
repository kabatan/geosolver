"""Artificial residual evaluations; no optimizer or benchmark solve."""
from common import *
from collections import Counter
import os
import numpy as np
from geosolver import GeometryProblem
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator, IREvaluator
from geosolver.engine.standard.search import scipy_multistart_backend as smb
from role_patch import install, bundle_plans

verify_lock()
mode = sys.argv[1]
os.environ.update(ROLE_CONDITION=mode, ROLE_AUDIT_PATH=str(HERE / f"preflight-{mode}.audit.jsonl"))
def make(name, construction, conditions):
    doc = dict(id="Q13-artificial-" + name, variables=["h"],
               constructions=[dict(name=n, expression=e) for n, e in construction],
               conditions=[dict(left=l, operator=op, right=r) for l, op, r in conditions], target="h")
    return load_problem_bundle(GeometryProblem.model_validate(doc).engine_document())

examples = [
    make("shared-contact", [("P","Point(1,0)"),("Q","Point(0,1)"),("Z","Point(-1,0)"),
         ("C","Circumcircle(P,Q,Z)"),("L","Line(P,Point(1+h,1))")],
         [("IsTangent(L,C)","=",0),("h",">",0)]),
    make("line-circle", [("C","Circle(Point(0,0),1)"),("L","Line(Point(0,1+h),Point(1,1+h))")],
         [("IsTangent(L,C)","=",0)]),
    make("circle-circle", [("C","Circle(Point(0,0),1)"),("D","Circle(Point(3+h,0),2)")],
         [("IsTangent(C,D)","=",0)]),
    make("nonzero-target", [("C","Circle(Point(0,0),1)"),("L","Line(Point(0,1+h),Point(1,1+h))")],
         [("IsTangent(L,C)","=",1)]),
    make("invalid-domain", [("C","Circle(Point(0,0),h)"),("L","Line(Point(0,1),Point(1,1))")],
         [("IsTangent(L,C)","=",0)]),
]
original_vector = smb._evaluate_augmented_residual_vector
preserved = {n: getattr(IREvaluator,n) for n in ("evaluate_float_residual", "evaluate_hp_residual", "evaluate_float_hard_feasibility", "evaluate_hp_hard_feasibility", "evaluate_guard")}
before = []
for b in examples:
    ev = build_ir_evaluator(b)
    for x in [-0.1, 0.0, 0.1]:
        kw = dict(bundle=b, evaluator=ev, values=np.array([x]), n_constraints=len(b.spec.constraints),
                  telemetry=smb._SearchTelemetry())
        v = original_vector(**kw)
        before.append((b, ev, x, kw, v, ev.evaluate_float_residual([x]), ev.evaluate_float_hard_feasibility([x])))
install()
rows = []
for b, ev, x, kw, v, old_res, old_hard in before:
    w = smb._evaluate_augmented_residual_vector(**kw)
    assert np.array_equal(np.isnan(old_res.residual_vector), np.isnan(ev.evaluate_float_residual([x]).residual_vector))
    assert old_hard == ev.evaluate_float_hard_feasibility([x])
    assert all(getattr(IREvaluator,n) is fn for n,fn in preserved.items())
    if mode == "B":
        assert np.array_equal(v,w)
    elif all(y == smb._NONFINITE_RESIDUAL_PENALTY for y in v):
        assert np.array_equal(v,w)
    else:
        assert w[-1] == 0 and v[-2] == w[-2]
        if not bundle_plans(b):
            assert np.array_equal(v[:-1],w[:-1])
    rows.append(dict(id=b.problem_id, x=x, before=v.tolist(), after=w.tolist(),
                     hard_feasible=old_hard.hard_feasible, plans=bundle_plans(b)))
if mode == "R":
    assert any(r["before"][0] != r["after"][0] for r in rows)
    assert any(r["before"][-1] > 0 and r["after"][-1] == 0 and not r["hard_feasible"] for r in rows)
dump(HERE / f"preflight-{mode}.json", dict(utc=now(), mode=mode, optimizer_calls=0,
                                         evaluations=len(rows), all_passed=True, rows=rows))
print(json.dumps(dict(mode=mode, evaluations=len(rows), all_passed=True)))
