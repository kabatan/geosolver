# ruff: noqa
import sys, json, numpy as np, mpmath
sys.argv=['x']; sys.path.insert(0,'benchmarks/new-2026/verify')
import check_dsl as c
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
dsl, issues, b, ev = c.load('benchmarks/new-2026/dsl/HMMT-2026-FEB-GEO-05.json')
doc_guards = b.spec.guards
for i,g in enumerate(doc_guards): print(i, g)
x0=[-5.65685424949,-7.0,5.65685424949,-7.0,0.681424641097,0.210401910933,0.818575358903,0.289598089067,1.57509914386,1.92490085614]
xp,norm=c.polish(ev,x0); print('norm',mpmath.nstr(norm,3)); print([mpmath.nstr(v,15) for v in xp])
print('target',c.hp_target(ev,xp))
print('float guard',ev.evaluate_guard([float(v) for v in xp]))
print('float hard',ev.evaluate_float_hard_feasibility([float(v) for v in xp]))
mpmath.mp.dps=80
with high_precision_mode():
    print('hp hard',ev.evaluate_hp_hard_feasibility(xp,precision=80))
json.dump([str(v) for v in xp],open('/tmp/claude-0/geo05_point.json','w'))
# guard values via a scratch DSL whose target is each guard expression
import copy
from geosolver.problem.models import GeometryProblem
for i,g in enumerate(dsl['conditions']):
    if g.get('operator') in ('<','>'):
        d=copy.deepcopy(dsl); d['target']=g['left']; d['id']='probe'
        _,_,b2,ev2=c.load_dict(d) if hasattr(c,'load_dict') else (None,None,None,None)
