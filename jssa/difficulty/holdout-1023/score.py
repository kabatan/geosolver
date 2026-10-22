"""Score the pre-registered E/Y/Z predictions (predictions.csv) against probe_common outputs.
Endpoint match for P1: same class, and residuals both <=1e-8 or relative difference <=1e-3."""
import csv, json, os, sys
OUT = sys.argv[1]
rows = list(csv.DictReader(open(os.path.join(os.path.dirname(__file__), 'predictions.csv'))))
def same(a, b):
    if a['cls'] != b['cls']: return False
    ra, rb = a.get('res'), b.get('res')
    if ra is None or rb is None: return ra == rb
    return (ra <= 1e-8 and rb <= 1e-8) or abs(ra - rb) <= 1e-3 * max(abs(ra), abs(rb))
res = []
for r in rows:
    f = os.path.join(OUT, r['case_id'] + '.json')
    if not os.path.exists(f):
        res.append(dict(r, status='missing')); continue
    d = json.load(open(f)); s = d['summary']
    pE, pY, pZ = s['E']['p'], s['Y']['p'], s['Z']['p']
    match = sum(same(x['E'], x['Z']) for x in d['rows'] if 'E' in x and 'Z' in x)
    N = d['starts']
    inf = float(r['col_inflation']) if r['col_inflation'] else float('nan')
    p1 = None
    if r['pred_Z'].startswith('Z_equals_E'):
        p1 = match / N >= 0.95
    p2 = None
    if inf <= 1.05: p2 = abs(pY - pE) <= 0.10
    elif inf >= 3 and pE >= 0.3: p2 = pY <= pE - 0.20
    res.append(dict(r, status='done', N=N, pE=pE, pY=pY, pZ=pZ, EZ_match=match, P1=p1, P2=p2))
w = csv.DictWriter(open(os.path.join(OUT, 'scored.csv'), 'w'), fieldnames=list(res[0].keys()) + ['N','pE','pY','pZ','EZ_match','P1','P2'], extrasaction='ignore')
w.writeheader(); [w.writerow(x) for x in res]
done = [x for x in res if x['status'] == 'done']
print('done', len(done), 'of', len(res))
for key in ('P1', 'P2'):
    v = [x[key] for x in done if x[key] is not None]
    print(key, 'tested', len(v), 'held', sum(v))
for x in done:
    print(f"{x['case_id']:28s} inEq={x['picks_in_equalities'][0]} inf={(float(x['col_inflation']) if x['col_inflation'] else float('nan')):8.2f} E={x['pE']:.2f} Y={x['pY']:.2f} Z={x['pZ']:.2f} EZ={x['EZ_match']}/{x['N']} P1={x['P1']} P2={x['P2']}")
