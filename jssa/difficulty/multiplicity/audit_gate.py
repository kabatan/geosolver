"""Complete the preregistered equality audit, including original fallbacks.

experiment.py's original audit added an unregistered 'zero fallback' gate.
A fallback shared by the original and copied implementation is not a mismatch.
Retain that observation rather than altering the frozen implementation.
"""
import json
from pathlib import Path
from mpmath import mp
import experiment as e
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
import geosolver.engine.standard.refinement.mpmath_refiner as mr

e.verify_lock()
path = e.HERE / "implementation-audit.json"
old = json.loads(path.read_text())
backup = e.HERE / "implementation-audit-initial.json"
if not backup.exists():
    e.dump(backup, old)
manifest = {x['id']: x for x in json.loads((e.HERE / 'manifest.json').read_text())}
frozen = json.loads((e.HERE / 'frozen-candidates.json').read_text())
for row in old:
    if row['status'] != 'fail':
        continue
    if not (row['all_equal'] and row['original_equal'] and row['noops_equal']):
        raise RuntimeError('actual residual mismatch')
    item = manifest[row['id']]
    b = e.bundle_for(item['dsl'])
    evaluator = build_ir_evaluator(b)
    with mp.workdps(120), high_precision_mode():
        point = [mp.mpf(repr(x)) for x in frozen[row['id']][0]['x']]
        ev = evaluator.evaluate_hp_residual(point, precision=120)
        kwargs = dict(bundle=b, point=point, dps=120, residuals=list(ev.residual_vector))
        fn, stats = e.smoother('A')
        actual = fn(**kwargs)
        expected = mr._smooth_zero_constraint_residuals(**kwargs)
        assert actual == expected == kwargs['residuals']
        row.update(status='pass', existing_fallback=True, fallback_stats=stats,
                   original_evaluation_status=str(ev.evaluation_status),
                   note='Source and gated copy both return original residuals; counted, not repaired.')
e.dump(path, old)
print(json.dumps([r for r in old if r.get('existing_fallback')], ensure_ascii=False))
