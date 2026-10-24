"""Cheap deterministic contract probes, separate from full-pipeline smoke."""
import json
import sys
import time
from dataclasses import asdict
from types import SimpleNamespace as NS

from mpmath import mp
from geosolver.runtime.ablation import active_ablations
from geosolver.runtime.integrity import verify_engine_lock
from geosolver.problem.models import GeometryProblem
from geosolver.problem.domain_bounds import mathematical_bounds, search_bounds
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.evaluation import _hard_feasibility_core as core
from geosolver.engine.standard.contracts.hard_feasibility_check import HardFeasibilityCheck
from geosolver.engine.standard.contracts.hard_feasibility_snapshot import HardFeasibilitySnapshot
from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
from geosolver.engine.standard.evaluation.evaluate_float_residual import FloatResidualEvaluation
from geosolver.engine.standard.search.nomad_blackbox_adapter import NomadBlackboxAdapter
from geosolver.engine.standard.search.nomad_config import NomadConfig
from geosolver.engine.standard.interpreter.compile.infer_bounds import infer_bound_expansion_locks
from geosolver.engine.standard.search.nomad_backend import _expand_bounds


class Point:
    def __init__(self):
        self.payload = None
    def size(self):
        return 1
    def get_coord(self, index):
        return 0.0
    def setBBO(self, payload):
        assert self.payload is None
        self.payload = payload


class Evaluator:
    def __init__(self, hard, status):
        self.hard, self.status = hard, status
    def evaluate_float_residual(self, coords):
        return FloatResidualEvaluation([3., 4.], 5., self.status, self.status == EvaluationStatus.OK)
    def evaluate_float_hard_feasibility(self, coords, **kw):
        return HardFeasibilitySnapshot(self.hard, () if self.hard else ('guard:0',), None)
    def evaluate_guard(self, coords):
        return self.hard, () if self.hard else ('guard:0',)


def main():
    ok, lock = verify_engine_lock()
    assert ok, lock
    out = dict(active=active_ablations(), lock_valid=ok)
    # M014: positive tiny geometry, exact degeneracy, and HP unaffected.
    out['floors'] = {}
    for kind, fn, size in (
        ('line_distinct', core._evaluate_line_distinct_check, '1e-13'),
        ('triangle_nondegenerate', core._evaluate_triangle_check, '1e-15'),
        ('intersection_exclude_distinct', core._evaluate_intersection_exclude_check, '1e-13')):
        results = {}
        for tiny in (True, False):
            for allow in (True, False):
                point = lambda x,y: NS(x=mp.mpf(x), y=mp.mpf(y))
                ctx = dict(A=point(0,0), B=point(size if tiny else 0,0), C=point(0,1))
                names = ('A','B','C') if kind.startswith('triangle') else ('A','B')
                check = HardFeasibilityCheck('probe', kind, names, None)
                result = fn(check=check, state=core.HardFeasibilityRuntimeState(ctx, {}), allow_float=allow)
                results[f'{"tiny" if tiny else "zero"}_{"float" if allow else "hp"}'] = result[0]
        out['floors'][kind] = results
    out['guard_boundary'] = [core._evaluate_guard_check(
        check=HardFeasibilityCheck('guard:0','guard',(),None), guard_ok=True,
        guard_violations=(), guard_margin=mp.mpf(v))[0] for v in ('0','1e-50')]
    out['adapter'] = []
    for hard, status, scales in ((False, EvaluationStatus.OK, None),
                                 (False, EvaluationStatus.OK, (3.,2.)),
                                 (True, EvaluationStatus.OK, None),
                                 (False, EvaluationStatus.NON_FINITE, None),
                                 (False, EvaluationStatus.EVALUATION_FAILED, None)):
        adapter = NomadBlackboxAdapter(Evaluator(hard,status), NomadConfig(8), 0, 0,
                                       constraint_scales=scales)
        p = Point()
        ret = adapter(p)
        out['adapter'].append(dict(hard=hard, status=status.value, scales=scales,
            returncode=ret, payload=None if p.payload is None else p.payload.decode(),
            records=[asdict(r) for r in adapter.records], failures=adapter.failure_count))
    expired_adapter = NomadBlackboxAdapter(Evaluator(False,EvaluationStatus.NON_FINITE),
                            NomadConfig(8), 0, 0, deadline_monotonic=time.monotonic()-1)
    p = Point()
    out['deadline'] = dict(returncode=expired_adapter(p), payload=p.payload,
                           records=len(expired_adapter.records))
    out['params'] = {mode: NomadConfig(8).build_params(dimension=1,seed=0,search_mode=mode)
                     for mode in ('mads','disco_mads')}
    # Each box mechanism changes a distinct axis. Explicit/parameter domains survive.
    spec = GeometryProblem(id='box-probe', variables=['x','t'], constructions=[
        dict(name='A',expression='Point(0,0)'), dict(name='B',expression='Point(1,0)'),
        dict(name='P',expression='PointOnSegment(A,B,t)')], conditions=[
        dict(left='x',operator='=',right=100), dict(left='x',operator='>',right=2)],
        target='x').engine_document()
    bundle = load_problem_bundle(spec)
    b = search_bounds(bundle.spec)
    locks = infer_bound_expansion_locks(bundle.spec,bundle.var_names)
    out['box'] = dict(raw=b, locks=locks, expanded=_expand_bounds(b,.25,expansion_locks=tuple(locks)),
        mathematical={n:str(a) for n,a in mathematical_bounds(bundle.spec).items()},
        original_guards=bundle.spec.guards)
    from dataclasses import replace
    explicit = replace(bundle.spec, bounds=[(7,9),None])
    out['explicit_box'] = search_bounds(explicit)
    print(json.dumps(out,sort_keys=True,default=lambda v:v.value if hasattr(v,'value') else str(v),allow_nan=True))


if __name__ == '__main__':
    main()
