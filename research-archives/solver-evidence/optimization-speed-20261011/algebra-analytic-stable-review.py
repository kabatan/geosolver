import json
import random
from pathlib import Path

from mpmath import mp

from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.engine.standard.refinement import analytic_jacobian as analytic

def unsigned_point_angle(x,y):
    ax,ay=x,y
    bx,by=x*y,mp.mpf(1)
    cx,cy=mp.mpf(1),-y
    vx,vy=ax-bx,ay-by
    wx,wy=cx-bx,cy-by
    return mp.atan2(abs(vx*wy-vy*wx),vx*wx+vy*wy)

def acute_line_angle(x,y):
    a,b=x,y
    c,d=x+y,x-y
    return mp.atan2(abs(a*d-b*c),abs(a*c+b*d))

cases=[
    ('moving_point_angle','Angle(Point(x,y),Point(x*y,1),Point(1,-y))',unsigned_point_angle),
    ('moving_line_angle','Angle(Line(x,y,1),Line(x+y,x-y,2))',acute_line_angle),
    ('angle_trig_chain','cos(Angle(Point(x,y),Point(x*y,1),Point(1,-y)))+sin(x+y)*tan(x-y)',
        lambda x,y:mp.cos(unsigned_point_angle(x,y))+mp.sin(x+y)*mp.tan(x-y)),
    ('pi_trig_chain','sin(pi*x*y)+cos(pi*(x+y))+tan(x-y)',
        lambda x,y:mp.sin(mp.pi*x*y)+mp.cos(mp.pi*(x+y))+mp.tan(x-y)),
]
randomizer=random.Random(67011)
points=[(randomizer.randint(-29,29),randomizer.randint(2,19),
    randomizer.randint(-23,23),randomizer.randint(2,17))for _ in range(12)]
results=[]
with high_precision_mode():
    for name,source,original in cases:
        plan=analytic.compile_jacobian((('x','y'),(),(source,),('0',)))
        assert plan is not None,name
        for dps in (80,180,500):
            with mp.workdps(dps):
                for a,b,c,d in points:
                    x,y=mp.mpf(a)/b,mp.mpf(c)/d
                    row=analytic.evaluate_jacobian(plan,[x,y],dps)
                    if row is None:
                        results.append({'case':name,'dps':dps,'point':[a,b,c,d],'declined':True})
                        continue
                    expected=[mp.diff(lambda u:original(u,y),x),mp.diff(lambda v:original(x,v),y)]
                    errors=[abs(v-w)/max(mp.mpf(1),abs(w))for v,w in zip(row[0],expected,strict=True)]
                    assert max(errors)<mp.mpf(10)**(-dps+12),(name,dps,[a,b,c,d],errors)
                    results.append({'case':name,'dps':dps,'point':[a,b,c,d],
                        'declined':False,'max_relative_scaled_error':str(max(errors))})
    near=[]
    plan=analytic.compile_jacobian((('x','y'),(),('Angle(Point(1,0),Point(0,0),Point(x,y))',),('0',)))
    for dps in (80,180,500):
        with mp.workdps(dps):
            for exponent in (5,20,50,100,200):
                for sign in (-1,1):
                    x,y=mp.mpf(1),sign*mp.mpf(10)**(-exponent)
                    row=analytic.evaluate_jacobian(plan,[x,y],dps)
                    expected=[-abs(y)/(1+y*y),sign/(1+y*y)]
                    errors=None if row is None else [str(abs(v-w))for v,w in zip(row[0],expected,strict=True)]
                    assert row is not None,(dps,exponent,sign)
                    relative_errors=[abs((v-w)/w)for v,w in zip(row[0],expected,strict=True)]
                    assert max(relative_errors)<mp.mpf(10)**(-dps+8),(dps,exponent,sign,relative_errors)
                    near.append({'dps':dps,'negative_y':sign<0,'y_exponent':-exponent,
                        'declined':row is None,'absolute_errors':errors,
                        'relative_errors':list(map(str,relative_errors))})
    cusp=[]
    for point in ((0,0),(1,0),(-1,0)):
        result=analytic.evaluate_jacobian(plan,list(map(mp.mpf,point)),180)
        assert result is None
        cusp.append({'point':point,'declined':True})
    lineplan=analytic.compile_jacobian((('x','y'),(),('Angle(Line(0,1,0),Line(x,y,0))',),('0',)))
    for point in ((0,0),(1,0),(0,1)):
        result=analytic.evaluate_jacobian(lineplan,list(map(mp.mpf,point)),180)
        assert result is None
        cusp.append({'line_point':point,'declined':True})
    invalid=[]
    for source,point in (
        ('Angle(Point(1,0),Point(0,0),Point(x,y))',(mp.inf,1)),
        ('Angle(Point(1,0),Point(0,0),Point(x,y))',(mp.nan,1)),
        ('Angle(Line(x,y,0),Line(1,0,0))',(0,0)),
        ('Angle(Point(x,y),Point(x,y),Point(1,0))',(1,2)),
    ):
        plan=analytic.compile_jacobian((('x','y'),(),(source,),('0',)))
        result=None if plan is None else analytic.evaluate_jacobian(plan,list(map(mp.mpf,point)),180)
        assert result is None,(source,point)
        invalid.append({'source':source,'point':list(map(str,point)),'declined':True})

report={'smooth_comparisons':len(results),'smooth_declines':sum(x['declined']for x in results),
    'smooth_all_returned_rows_match_independent_atan2_or_trig_derivatives':True,
    'smooth_rows':results,'near_collinear_rows':near,'exact_cusp_rows':cusp,
    'invalid_domain_rows':invalid,
    'interpretation':'The derivative-only atan2 representation agrees with independent original unsigned point-angle and acute line-angle formulas on every tested smooth branch. All30 near-collinear rows retain relative precision10^(-dps+8), including separation1e-200 at80dps; all6exactcusps and4invalid-domain inputs decline. Derivatives remain optional Newton proposals; original residual/domain/final verification unchanged.'}
destination=Path('/home/kabatan/work/solver/benchmarks/local-evaluation/optimization-speed-20261011/algebra-analytic-stable-review.json')
destination.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k]for k in ('smooth_comparisons','smooth_declines','smooth_all_returned_rows_match_independent_atan2_or_trig_derivatives')}))
