"""Reuse the existing, independently saved saturation instead of repeating it."""
import compare as c
import sympy as sp,json,time
cid='HMMT-2019-FEB-GUTS-17'
source=c.OUT.parent/'examples/evidence'/f'{cid}.components.log'
old=(c.OUT.parent/'examples/evidence'/f'{cid}.sing').read_text()
names=old.split('(')[1].split(')')[0].split(',')
# Saved fresh translation order: ax,ay,px,py,s,t1,t2,u1,u2,v1,v2 map below.
s,unused=c.translate(c.cases[cid]['dsl'],mode='fresh',with_target=False)
eqs,used,_=c.build(s,True)
ren={str(v):f'x{i}' for i,v in enumerate(used)}
assert names==[f'x{i}' for i in range(len(used))]
a={k:sp.Symbol(ren['v_'+k]) for k in c.cases[cid]['dsl']['variables']}
pts=[(4*a['t1'],0),(4*a['t2'],0),(4+(a['ax']-4)*a['u1'],a['ay']*a['u1']),(4+(a['ax']-4)*a['u2'],a['ay']*a['u2']),(a['ax']*(1-a['v1']),a['ay']*(1-a['v1'])),(a['ax']*(1-a['v2']),a['ay']*(1-a['v2']))]
S=sp.expand(sum(pts[i][0]*pts[(i+1)%6][1]-pts[i][1]*pts[(i+1)%6][0] for i in range(6)))
# poly_str makes a primitive polynomial. Track its scale explicitly: T=Area/4.
scale, primitive=sp.Poly(S).primitive()
assert scale==4 and sp.expand(S-4*sp.sympify(c.poly_str(S).replace('^','**')))==0
gb=source.read_text().split('NONZERO_S_DIM\n0\n')[1].strip()
code=f'ring R=0,({",".join(names)},T),dp;\nideal J={gb},4*T^2-({c.poly_str(S)})^2;\nideal E=eliminate(J,{"*".join(names)});\nprint("ELIM_BEGIN");print(E);print("ELIM_END");\nquit;\n'
r=c.singular(cid+'.reuse',code)
r.update(saturation_source=str(source.relative_to(c.ROOT)),saturation_source_sha256=c.digest(source),method='saved sat(I,s); T=Area/4, 4*T^2-(shoelace/4)^2=0; eliminate all x variables',variable_mapping=ren,twice_signed_area=str(S),target_scale=4,answer_set_verified=False)
(c.OUT/'reuse-saturation.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
print(r['returncode'],r['wall_seconds'],r['log'][-1500:])
