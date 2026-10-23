"""Analytic far-field check for AIME-2020-II-15; no geometry solving.

All quantities follow from the DSL. Endpoint coordinates are not used.
The symmetric probe a=0 is a diagnostic configuration, not an admissible
scalene answer to the problem.
"""
from __future__ import annotations
import json
import math
import sys

sys.dont_write_bytecode=True
import numpy as np
from measure_attraction import HERE, ROOT, GeometryProbe


def main():
    cases={c['id']:c for c in map(json.loads,(ROOT/'benchmarks/cases.jsonl').read_text().splitlines())}
    dsl=cases['AIME-2020-II-15']['dsl']
    probe=GeometryProbe(dsl)
    # B=(-11,0), C=(11,0), A=(a,b):
    # circumcenter O=(0,(a^2+b^2-121)/(2b)); T=(0,-242b/(a^2+b^2-121)).
    # BT=CT=16 implies t^2=135, hence (a,b) lies on one of two circles
    # centered at (0, +/-121/sqrt(135)), with radius sqrt(121+121^2/135).
    center=121/math.sqrt(135)
    radius=math.sqrt(121+center*center)
    bound_y=center+radius
    rows=[]
    for R in [100,1000,10000]:
        x=np.array([0.,float(R)])
        f,points=probe.evaluate((x-probe.lower)/probe.width)
        t=-242*R/(R*R-121)
        q=242*R*R*(3*R*R+121)/(R*R-121)**2
        tj=probe.names.index('T')
        np.testing.assert_allclose(points[tj],[0,t],rtol=1e-9,atol=1e-10)
        expected=np.array([0.,math.sqrt(121+t*t)-16,math.sqrt(121+t*t)-16,q-1143])
        np.testing.assert_allclose(f,expected,rtol=1e-9,atol=1e-7)
        step=R*1e-4
        def fs(r):
            return probe.evaluate((np.array([0.,r])-probe.lower)/probe.width)[0]
        jrad=(fs(R+step)-fs(R-step))/(2*step)
        rows.append({'R':R,'T_y':t,'distance_residual':float(f[1]),
                     'squared_distance_sum_residual':float(f[-1]),
                     'radial_residual_derivative_norm':float(np.linalg.norm(jrad))})
    k2=json.loads((ROOT/'jssa/difficulty/holdout-1023/dsl/AIME-2020-II-15.k2.json').read_text())
    existing=json.loads((ROOT/'jssa/difficulty/holdout-1023/out/AIME-2020-II-15.json').read_text())
    report={'box':probe.bounds.tolist(),'true_ax_abs_bound':radius,'true_ay_upper_bound':bound_y,
            'all_finite_solutions_inside_proposed_box':[[-16,16],[0,26]],
            'area_ratio_original_to_proposed':float(np.prod(probe.width)/(32*26)),
            'k2_changed_constructions':[c['name'] for c,d in zip(k2['constructions'],dsl['constructions']) if c!=d],
            'k2_T_expression':next(c['expression'] for c in k2['constructions'] if c['name']=='T'),
            'far_field_checks':rows,
            'existing_common_start_results':existing['summary'],
            'note':'Existing E/Y/Z outcomes are read-only context, not new experimental results. Radial probes include inadmissible symmetric figures and are not full LM trajectories.'}
    (HERE/'aime-limit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
