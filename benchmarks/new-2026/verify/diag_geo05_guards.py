# ruff: noqa
import sys, json, copy, mpmath
sys.argv=['x']; sys.path.insert(0,'benchmarks/new-2026/verify')
import check_dsl as c
dsl=json.load(open('benchmarks/new-2026/dsl/HMMT-2026-FEB-GEO-05.json'))
mpmath.mp.dps=60
xp=[mpmath.mpf(v) for v in json.load(open('/tmp/claude-0/geo05_point.json'))]
probes=[g['left'] for g in dsl['conditions'] if g.get('operator') in ('<','>')]
probes += ['Distance(K1, K2)','Distance(K1, K3)','Distance(K2, K3)','Distance(E1,F1)','Distance(E2,F2)','Distance(E3,F3)','Distance(O, l1)','Distance(O, l3)','Distance(V12,O)','Distance(V13,O)','Distance(V23,O)']
for i,p in enumerate(probes):
    d=copy.deepcopy(dsl); d['target']=p; d['id']='probe'
    _,_,b,ev=c.load_dict(d)
    print(i, mpmath.nstr(c.hp_target(ev,xp),12), '|', p[:90])
