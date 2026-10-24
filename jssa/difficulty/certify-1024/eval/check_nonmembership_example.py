#!/usr/bin/env python3
"""Substitute one explicit counterexample into saved original equalities.

No Singular, solving, elimination, or repeated certification attempt.
"""
import hashlib
import json
from pathlib import Path
import sympy as sp

E=Path(__file__).resolve().parent
p=E/'runs/HMMT-2013-FEB-GUTS-01.work/translation.json'
m=json.loads(p.read_text())
x1,x2,x3,x4,z1,yy=sp.symbols('x1 x2 x3 x4 z1 yy')
local={str(v):v for v in (x1,x2,x3,x4,z1,yy)}
assignment={x1:3*sp.sqrt(105)/4,x2:sp.Integer(31),x3:sp.Integer(-93),x4:sp.Integer(-93),
            z1:4/(3*sp.sqrt(105)),yy:-sp.Rational(1,186)}
parse=lambda s:sp.sympify(s,locals=local)
residuals=[sp.simplify(parse(s).subs(assignment)) for s in m['equations']]
factors=[sp.simplify(parse(s).subs(assignment)) for s in m['saturation_factors']]
inverse_residuals=[sp.simplify(1-assignment[local[z]]*f) for z,f in zip(m['inverse_variables'],factors)]
pvalue=sp.simplify(parse(m['polynomial']).subs(assignment))
rab=sp.simplify(1-assignment[yy]*pvalue)
assert all(v==0 for v in residuals+inverse_residuals) and all(v!=0 for v in factors) and pvalue!=0 and rab==0
result={'id':'HMMT-2013-FEB-GUTS-01','method':'exact substitution in original translated equations and inverse guards',
        'model_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
        'assignment':{str(k):str(v) for k,v in assignment.items()},
        'equation_residuals':list(map(str,residuals)),'nonzero_factor_values':list(map(str,factors)),
        'inverse_residuals':list(map(str,inverse_residuals)),'p_value':str(pvalue),'rabinowitsch_residual':str(rab),
        'verified':True,'singular_called':False,'solver_called':False,
        'note':'A point of the original equalities with all saturation factors nonzero and p != 0 disproves radical membership. This is not a valid geometric answer: a distance auxiliary variable is negative.',
        'library':'sympy','version':sp.__version__}
(E/'nonmembership-example.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print('counterexample exact-substitution check passed')
