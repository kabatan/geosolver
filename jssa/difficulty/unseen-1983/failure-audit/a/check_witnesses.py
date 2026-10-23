"""Substitute analytic witnesses into EVERY original DSL condition and frozen IR."""
from common import *
import csv
from dataclasses import asdict
from mpmath import mp
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.evaluation.high_precision_expressions import build_solution_context_high_precision
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.problem.ir.compiler import safe_eval_expr_hp
from geosolver.engine.standard.search.nomad_backend import _expand_bounds
from geosolver.engine.standard.search.nomad_config import NomadConfig
from geosolver.engine.standard.interpreter.compile.infer_bounds import infer_bound_expansion_locks

def check(cid):
    p = problem(cid)
    bundle = load_problem_bundle(p.engine_document())
    evaluator = build_ir_evaluator(bundle)
    with mp.workdps(100), high_precision_mode():
        values = witness(cid)
        x = [values[v] for v in bundle.var_names]
        ctx = build_solution_context_high_precision(bundle.spec, list(bundle.var_names), x,
                                                    dict(bundle.base_context), 100)
        rows, margins, residuals = [], [], []
        for i, c in enumerate(p.conditions):
            left, right = safe_eval_expr_hp(c.left, ctx), safe_eval_expr_hp(str(c.right), ctx)
            difference = left-right
            if c.operator == "=":
                margin = None
                residuals.append(abs(difference))
                satisfied = abs(difference) < mp.mpf("1e-85")
            else:
                margin = difference if c.operator in (">", ">=") else -difference
                margins.append(margin)
                satisfied = margin > 0 if c.operator in (">", "<") else margin >= 0
            rows.append(dict(index=i, left=c.left, operator=c.operator, right=c.right,
                             lhs=str(left), rhs=str(right), residual=str(difference),
                             satisfied=bool(satisfied), margin=None if margin is None else str(margin)))
        hp = evaluator.evaluate_hp_residual(x, precision=100)
        hard = evaluator.evaluate_hp_hard_feasibility(x, precision=100)
        guard = evaluator.evaluate_guard(x)
        target = safe_eval_expr_hp(p.target, ctx)
        assert all(row['satisfied'] for row in rows)
        assert hp.is_finite and hp.residual_norm_hp < mp.mpf("1e-85")
        assert hard.hard_feasible and guard[0]
        assert abs(target-EXPECTED[cid]) < mp.mpf("1e-85")
        bounds = infer_problem_bounds(bundle)
        outside = {n: dict(value=str(v), heuristic_bounds=b) for n,v,b in zip(bundle.var_names,x,bounds)
                   if not mp.mpf(str(b[0])) <= v <= mp.mpf(str(b[1]))}
        expanded = _expand_bounds(bounds, NomadConfig.standard_tier().bound_expansion_ratio,
            expansion_locks=tuple(infer_bound_expansion_locks(bundle.spec,bundle.var_names)))
        expanded_outside = [n for n,v,b in zip(bundle.var_names,x,expanded)
                            if not mp.mpf(str(b[0])) <= v <= mp.mpf(str(b[1]))]
        constructions = {}
        for c in p.constructions:
            v = ctx[c.name]
            if hasattr(v, "x") and hasattr(v,"y"):
                constructions[c.name] = dict(x=str(v.x),y=str(v.y))
            else:
                constructions[c.name] = str(v)
        data = dict(id=cid, precision_dps=100, original_DSL=True,
                    dsl_sha256=sha(CORPUS / "dsl" / f"{cid}.json"),
                    values={k:str(v) for k,v in values.items()}, constructions=constructions,
                    conditions=rows, raw_max_abs_equality_residual=str(max(residuals)),
                    min_raw_inequality_margin=str(min(margins)),
                    compiled_hp_residual=asdict(hp), compiled_hard_feasibility=asdict(hard),
                    compiled_guard_ok=guard[0], compiled_guard_violations=guard[1],
                    compiled_guards=list(bundle.spec.guards), target=str(target),
                    expected=EXPECTED[cid], heuristic_search_bounds=dict(zip(bundle.var_names,bounds)),
                    witness_outside_heuristic_bounds=outside,
                    NOMAD_expanded_bounds=dict(zip(bundle.var_names,expanded)),
                    witness_outside_NOMAD_bounds=expanded_outside)
        save(HERE / "witnesses" / f"{cid}.json", data)
        print(cid, 'residual',mp.nstr(max(residuals),6),'margin',mp.nstr(min(margins),8),
              'hard',hard.hard_feasible,'target',mp.nstr(target,8),'outside',list(outside))
        return data

if __name__ == "__main__":
    identity()
    rows = [check(cid) for cid in IDS]
    with (HERE / "conditions.csv").open("w",newline="") as f:
        writer = csv.DictWriter(f,fieldnames=["id",*rows[0]['conditions'][0]])
        writer.writeheader()
        for data in rows:
            for c in data['conditions']:
                writer.writerow(dict(id=data['id'],**c))
