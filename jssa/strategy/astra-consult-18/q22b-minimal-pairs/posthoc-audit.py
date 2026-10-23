"""Post-result analytic audit, without starting any optimizer."""
import csv
import json
import math
from pathlib import Path

OUT = Path(__file__).resolve().parent


def main():
    rows = []
    for pair in json.loads((OUT / 'stimuli.json').read_text()):
        if pair['group'] != 'S':
            continue
        a, h = float(pair['a']), float(pair['h'])
        r, c = math.sqrt(a*a+1), 2*h-1
        def derivative_equation(y):
            return y*(3-2*r/math.sqrt(a*a+y*y))-c
        lo, hi = 0.0, h
        assert derivative_equation(lo) < 0 < derivative_equation(hi)
        for _ in range(100):
            mid = (lo+hi)/2
            if derivative_equation(mid) < 0:
                lo = mid
            else:
                hi = mid
        y = (lo+hi)/2
        t = math.sqrt(a*a+y*y)
        hxx = 6-4*r*y*y/(t**3)-2*(1-h)/(h-y)
        hyy = 6-4*r*a*a/(t**3)
        raw = json.loads((OUT / 'raw' / f"{pair['id']}.json").read_text())
        failures = [z for z in raw['rows'] if z['mode']=='length_near' and not z['hit']]
        distances = [math.hypot(z['x'][0], z['x'][1]-y) for z in failures]
        rows.append({'pair':pair['id'],'a':a,'h':h,'axis_stationary_y':y,
                     'H_xx':hxx,'H_yy':hyy,
                     'type':'strict_local_minimum' if min(hxx,hyy)>0 else 'saddle',
                     'saved_failures':len(failures),
                     'failures_within_1e_5':sum(d<=1e-5 for d in distances),
                     'maximum_endpoint_distance':max(distances,default=None)})
    with (OUT / 'length-near-posthoc.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print(json.dumps(rows,indent=2))


if __name__ == '__main__':
    main()
