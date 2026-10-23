"""Q22a: saved-figure analysis, no solving or refinement; writes HERE only."""
from __future__ import annotations

import ast
import csv
import hashlib
import itertools as it
import json
import math
import os
from pathlib import Path
import re
import sys
import time

sys.dont_write_bytecode = True
for env_name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[env_name] = '1'
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'src'))
import numpy as np
from mpmath import mp
from scipy.spatial import cKDTree
from scipy.stats import spearmanr
from geosolver import GeometryProblem
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.evaluation.snapshots import numerical_snapshot, evaluation_session
from geosolver.geometry.mp.mp_core_types import MPPoint, MPCircle

KINDS = ('collinear', 'concyclic', 'equal_length', 'similar', 'tangent')
TOLS = (1e-8, 1e-7, 1e-6)
BASE = ['n_vars', 'n_cons', 'n_pts', 'n_circ', 'n_eq', 'n_ineq', 'has_angle', 'has_tangent', 'dsl_len']
DEEP = BASE + ['construction_depth']
HIDDEN = [f'log_hidden_{k}' for k in KINDS] + ['hidden_depth']
MODELS = {'B_S': BASE, 'B_D': DEEP, 'B_H': DEEP + HIDDEN,
          'B_C': DEEP + ['log_solution_dependent', 'solution_depth']}


def safe(x):
    if isinstance(x, dict): return {str(k): safe(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)): return [safe(v) for v in x]
    if isinstance(x, np.ndarray): return safe(x.tolist())
    if isinstance(x, np.generic): return safe(x.item())
    if isinstance(x, float) and not math.isfinite(x): return None
    return x


def write_json(name, data):
    text = json.dumps(safe(data), ensure_ascii=False, indent=2) + '\n'
    if len(text.encode()) > 10_000_000: raise ValueError('output exceeds 10MB')
    p = HERE / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def write_csv(name, rows):
    if not rows: return
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with (HERE / name).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader(); w.writerows(safe(rows))


def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def load_inputs():
    cases = {c['id']: c for c in map(json.loads, (ROOT / 'benchmarks/cases.jsonl').read_text().splitlines())}
    with (ROOT / 'jssa/difficulty/ghost-1023/human_feat.csv').open() as f:
        human = [r for r in csv.DictReader(f) if r['human']]
    return cases, sorted(human, key=lambda r: r['case_id'])


def register():
    _, human = load_inputs()
    paths = [HERE / 'preregistration.md', HERE / 'experiment.py',
             ROOT / 'benchmarks/cases.jsonl', ROOT / 'jssa/difficulty/ghost-1023/human_feat.csv',
             ROOT / 'jssa/difficulty/minima/basins-323.csv']
    paths += sorted((ROOT / 'src').rglob('*.py'))
    paths += [ROOT / 'jssa/difficulty/minima/raw-323' / f"{r['case_id']}.json" for r in human]
    write_json('registration-lock.json', {'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               'files': {str(p.relative_to(ROOT)): digest(p) for p in paths if p.exists()}})
    write_json('manifest.json', [{'id': r['case_id'], 'contest': r['contest'],
                                'year': int(r['case_id'].split('-')[1]),
                                'fold': r['contest'] + '-' + r['case_id'].split('-')[1]} for r in human])
    print('registered', len(human), flush=True)


def parse(s):
    try: return ast.parse(str(s), mode='eval').body
    except (SyntaxError, TypeError): return None


def fname(node): return node.func.id if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) else ''
def symbol(node): return node.id if isinstance(node, ast.Name) else None
def canon(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return repr(float(node.value))
    return ast.dump(node, include_attributes=False) if node is not None else '?'


def structure(dsl):
    exprs = {c['name']: c['expression'] for c in dsl['constructions']}
    deps = {n: set(re.findall(r'(?<![\w.])[A-Za-z_]\w*', e)) & set(exprs) - {n} for n, e in exprs.items()}
    depth = {}
    def get(n, stack=frozenset()):
        if n in depth: return depth[n]
        if n in stack: raise ValueError('cyclic construction')
        depth[n] = 1 + max([get(q, stack | {n}) for q in deps[n]] or [0])
        return depth[n]
    for n in exprs: get(n)
    return depth


def merge_sets(groups, overlap):
    groups = [set(g) for g in groups if len(g) >= overlap]
    changed = True
    while changed:
        changed = False
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                if len(groups[i] & groups[j]) >= overlap:
                    groups[i] |= groups.pop(j); changed = True; break
            if changed: break
    return groups


def explicit_facts(dsl, points, circles):
    """Conservative syntactic consequences only; no numerical truth as premise."""
    defs = {c['name']: parse(c['expression']) for c in dsl['constructions']}
    lines, cpoints, ccenters, cradii, eqgroups = {}, {}, {}, {}, []
    tangent_keys, similar_keys = set(), set()
    ignored = []
    def expand(n, active=frozenset()):
        s = symbol(n)
        if s in defs and s not in points and s not in active:
            return expand(defs[s], active | {s})
        return n
    def p(n):
        s = symbol(n)
        return s if s in points else None
    def edge(a, b):
        a, b = p(a), p(b)
        return tuple(sorted((a, b))) if a is not None and b is not None and a != b else None
    def distance(n):
        return edge(*n.args[:2]) if fname(n) == 'Distance' and len(n.args) == 2 else None
    def linekey(n):
        n = expand(n)
        if fname(n) in ('Line', 'Segment', 'Ray') and len(n.args) >= 2:
            e = edge(*n.args[:2])
            if e:
                k = 'L:' + ','.join(e); lines.setdefault(k, set(e)); return k
        return None
    def circlekey(n):
        n = expand(n)
        if fname(n) not in ('Circle', 'Circumcircle', 'Incircle'): return None
        k = canon(n); cpoints.setdefault(k, set())
        if fname(n) == 'Circumcircle': cpoints[k].update(filter(None, map(p, n.args)))
        if fname(n) == 'Circle' and len(n.args) == 2:
            a = p(n.args[0]); ccenters[k] = a; cradii[k] = canon(n.args[1])
            e = distance(n.args[1])
            if a and e and a in e: cpoints[k].update(set(e) - {a})
        return k
    for n in defs.values():
        circlekey(n); linekey(n)
    def put_on(pt, n):
        if not pt: return
        lk = linekey(n); ck = circlekey(n)
        if lk: lines[lk].add(pt)
        if ck: cpoints[ck].add(pt)
    def add_col(names):
        names = set(filter(None, names))
        if len(names) >= 3: lines['S:' + ','.join(sorted(names))] = names
    def add_eq(es):
        es = set(e for e in es if e)
        if len(es) >= 2: eqgroups.append(es)
    for name, n in defs.items():
        f = fname(n)
        if name not in points: continue
        args = n.args if isinstance(n, ast.Call) else []
        if f in ('Midpoint', 'PointOnSegment') and len(args) >= 2:
            a, b = p(args[0]), p(args[1]); add_col([a, b, name])
            if f == 'Midpoint' and a and b: add_eq([tuple(sorted((a, name))), tuple(sorted((b, name)))])
        elif f == 'Reflect' and len(args) == 2 and p(args[1]):
            a, m = p(args[0]), p(args[1]); add_col([a, m, name])
            if a: add_eq([tuple(sorted((a, m))), tuple(sorted((m, name)))])
        elif f == 'Intersect':
            for ob in args[:2]: put_on(name, ob)
        elif f == 'FootOfPerpendicular':
            for ob in args:
                if linekey(ob): put_on(name, ob)
        elif f == 'Circumcenter':
            add_eq([tuple(sorted((name, p(a)))) for a in args if p(a)])
    numeric_lengths = {}
    for cond in dsl['conditions']:
        if cond.get('operator') != '=': continue
        left, right = parse(cond.get('left')), parse(cond.get('right'))
        f = fname(left); args = left.args if isinstance(left, ast.Call) else []
        if f in ('Collinear', 'OnSegment') and len(args) >= 3:
            add_col([p(a) for a in args[:3]])
        elif f == 'OnLine':
            if len(args) == 3: add_col([p(a) for a in args])
            elif len(args) == 2: put_on(p(args[0]), args[1])
        elif f == 'OnCircle' and len(args) == 2: put_on(p(args[0]), args[1])
        elif f in ('Cyclic', 'Concyclic'):
            ns = set(filter(None, map(p, args)))
            if len(ns) >= 4: cpoints['S:' + ','.join(sorted(ns))] = ns
        elif f == 'IsTangent' and len(args) == 2:
            for a, b in [args, args[::-1]]:
                lk, ck = linekey(a), circlekey(b)
                if lk and ck: tangent_keys.add(('line', lk, ck))
            c1, c2 = map(circlekey, args)
            if c1 and c2: tangent_keys.add(('circle', *sorted((c1, c2))))
        else:
            a, b = distance(left), distance(right)
            if a and b: add_eq([a, b])
            elif a and right is not None:
                numeric_lengths.setdefault(canon(right), set()).add(a)
            elif b and left is not None:
                numeric_lengths.setdefault(canon(left), set()).add(b)
            else: ignored.append(cond)
    for k, members in cpoints.items():
        center = ccenters.get(k)
        if center:
            es = {tuple(sorted((center, q))) for q in members if q != center}
            numeric_lengths.setdefault(cradii[k], set()).update(es)
    eqgroups += list(numeric_lengths.values())
    eqgroups = merge_sets(eqgroups, 1)
    eq_index = {e: i for i, g in enumerate(eqgroups) for e in g}
    linegroups = merge_sets(lines.values(), 2)
    circgroups = merge_sets(cpoints.values(), 3)
    named_circlekeys = {n: circlekey(ast.Name(id=n)) for n in circles}
    def explained(kind, names):
        if kind == 'collinear': return any(set(names) <= g for g in linegroups)
        if kind == 'concyclic': return any(set(names) <= g for g in circgroups)
        if kind == 'equal_length':
            a, b = tuple(names[:2]), tuple(names[2:])
            return a in eq_index and b in eq_index and eq_index[a] == eq_index[b]
        if kind == 'similar': return tuple(names) in similar_keys
        if kind == 'tangent':
            if len(names) == 2:
                ck = [named_circlekeys[n] for n in names]
                return all(ck) and ('circle', *sorted(ck)) in tangent_keys
            e, ck = set(names[:2]), named_circlekeys.get(names[2])
            for typ, lk, cc in tangent_keys:
                if typ == 'line' and cc == ck:
                    # Shared-line transitivity, while retaining the named-circle identity.
                    if any(e <= g and lines[lk] <= g for g in linegroups): return True
        return False
    return explained, {'unhandled_equalities': ignored, 'line_groups': [sorted(g) for g in linegroups],
                       'circle_groups': [sorted(g) for g in circgroups], 'equal_length_groups': [sorted(g) for g in eqgroups]}


def figure(bundle, x, object_names):
    with mp.workdps(35):
        snap = numerical_snapshot(bundle.spec, list(bundle.var_names), list(map(float, x)), dict(bundle.base_context))
        context = snap.for_expressions(object_names)
        pts, circles = {}, {}
        for n in object_names:
            v = context.get(n)
            if isinstance(v, MPPoint): pts[n] = np.array([float(v.x), float(v.y)])
            elif isinstance(v, MPCircle): circles[n] = np.array([float(v.center.x), float(v.center.y), float(v.radius)])
    if len(pts) < 3: raise ValueError('fewer than three points')
    if any(not np.isfinite(v).all() for v in list(pts.values()) + list(circles.values())): raise ValueError('nonfinite figure')
    xyz = np.array(list(pts.values())); diameter = float(np.max(np.linalg.norm(xyz[:, None] - xyz[None], axis=2)))
    if diameter <= 0: raise ValueError('zero diameter')
    origin = xyz.mean(axis=0)
    return {'points': {n: (v-origin)/diameter for n, v in pts.items()},
            'circles': {n: np.r_[(v[:2]-origin)/diameter, v[2]/diameter] for n, v in circles.items()},
            'diameter': diameter}


def cross(a, b): return a[..., 0] * b[..., 1] - a[..., 1] * b[..., 0]


def lengths2(v): return np.sum(v*v, axis=-1)


def triangle_ok(x):
    sides = [lengths2(x[1]-x[0]), lengths2(x[2]-x[0]), lengths2(x[2]-x[1])]
    return min(sides) > 1e-12 and abs(float(cross(x[1]-x[0], x[2]-x[0]))) > 1e-5 * max(sides)


def residual(fig, kind, ns):
    p, c = fig['points'], fig['circles']
    if kind in ('collinear', 'concyclic'):
        x = np.array([p[n] for n in ns])
        ds = [float(lengths2(a-b)) for a, b in it.combinations(x, 2)]
        if min(ds) <= 1e-12: return math.inf
        if kind == 'collinear': return abs(float(cross(x[1]-x[0], x[2]-x[0]))) / max(ds)
        if not all(triangle_ok(np.array(t)) for t in it.combinations(x, 3)): return math.inf
        u, v, w, z = x[0]-x[1], x[3]-x[1], x[0]-x[2], x[3]-x[2]
        return abs(float(cross(u,v)*np.dot(w,z)-cross(w,z)*np.dot(u,v))) / math.sqrt(float(lengths2(u)*lengths2(v)*lengths2(w)*lengths2(z)))
    if kind == 'equal_length':
        a, b = float(lengths2(p[ns[0]]-p[ns[1]])), float(lengths2(p[ns[2]]-p[ns[3]]))
        return abs(a-b)/max(a,b) if min(a,b)>1e-12 else math.inf
    if kind == 'similar':
        ratios = []
        for names in (ns[:3], ns[3:]):
            x = np.array([p[n] for n in names])
            if not triangle_ok(x): return math.inf
            ds = np.sort([lengths2(a-b) for a,b in it.combinations(x,2)])
            ratios.append(ds[:2]/ds[2])
        return float(np.max(np.abs(ratios[0]-ratios[1])))
    if len(ns) == 3:
        a,b = p[ns[0]],p[ns[1]]; center, r = c[ns[2]][:2], float(c[ns[2]][2])
        d2 = float(lengths2(a-b))
        if d2<=1e-12 or r<=1e-6: return math.inf
        d=abs(float(cross(center-a,b-a)))/math.sqrt(d2)
        return abs(d-r)/max(d,r)
    c1,c2 = c[ns[0]],c[ns[1]]; d=float(np.linalg.norm(c1[:2]-c2[:2])); r,s = float(c1[2]),float(c2[2])
    if min(d,r,s)<=1e-6: return math.inf
    return min(abs(d-r-s)/max(d,r+s), abs(d-abs(r-s))/max(d,abs(r-s)))


def enumerate_candidates(fig):
    """Complete over declared finite universe; KD tree only rejects distant ratios."""
    names = sorted(fig['points']); pts = fig['points']; out = []
    combos = {'collinear': it.combinations(names,3), 'concyclic': it.combinations(names,4)}
    for kind, tuples in combos.items():
        for ns in tuples:
            r=residual(fig,kind,ns)
            if r<=1e-6: out.append((kind,ns,r))
    es=list(it.combinations(names,2)); dist=np.array([lengths2(pts[a]-pts[b]) for a,b in es])
    order=np.argsort(dist)
    for i, ei in enumerate(order):
        if dist[ei]<=1e-12: continue
        j=i+1
        while j<len(order) and (dist[order[j]]-dist[ei])/dist[order[j]]<=1e-6:
            a,b=sorted((es[ei],es[order[j]])); ns=a+b
            out.append(('equal_length',ns,residual(fig,'equal_length',ns))); j+=1
    ts, desc=[],[]
    for ns in it.combinations(names,3):
        x=np.array([pts[n] for n in ns])
        if not triangle_ok(x): continue
        ds=np.sort([lengths2(a-b) for a,b in it.combinations(x,2)])
        ts.append(ns);desc.append(ds[:2]/ds[2])
    if len(desc)>1:
        for i,j in sorted(cKDTree(desc).query_pairs(1e-6, p=np.inf)):
            out.append(('similar',ts[i]+ts[j],float(np.max(np.abs(desc[i]-desc[j])))))
    for a,b in es:
        for circ in sorted(fig['circles']):
            ns=(a,b,circ); r=residual(fig,'tangent',ns)
            if r<=1e-6: out.append(('tangent',ns,r))
    for ns in it.combinations(sorted(fig['circles']),2):
        r=residual(fig,'tangent',ns)
        if r<=1e-6: out.append(('tangent',ns,r))
    return sorted(out)


def check_geometry():
    # Analytically known positive and negative examples, independent of corpus labels.
    fig={'points': {'A':np.array([0.,0.]), 'B':np.array([1.,0.]), 'C':np.array([1.,1.]),
                   'D':np.array([0.,1.]), 'M':np.array([.5,0.]), 'U':np.array([2.,0.]),
                   'V':np.array([2.,2.])},
         'circles': {'g':np.array([.5,.5,.5]), 'h':np.array([1.5,.5,.5])}}
    rows=[]
    checks=[('collinear',('A','M','B'),True),('collinear',('A','B','C'),False),
            ('concyclic',('A','B','C','D'),True),('concyclic',('A','B','C','U'),False),
            ('equal_length',('A','B','B','C'),True),('equal_length',('A','B','A','C'),False),
            ('similar',('A','B','C','A','U','V'),True),('similar',('A','B','C','A','B','V'),False),
            ('tangent',('A','B','g'),True),('tangent',('A','C','g'),False),
            ('tangent',('g','h'),True)]
    for k,ns,wanted in checks:
        r=residual(fig,k,ns); actual=r<=1e-7
        assert actual==wanted,(k,ns,r,wanted)
        rows.append({'kind':k,'objects':ns,'residual':r,'expected':wanted,'observed':actual})
    # Translation/rotation/scale invariance of the numerical predicates.
    angle=.347; R=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
    f2={'points':{n:7.3*R@v+np.array([5.,-2.]) for n,v in fig['points'].items()},
        'circles':{n:np.r_[7.3*R@v[:2]+np.array([5.,-2.]),7.3*v[2]] for n,v in fig['circles'].items()}}
    for k,ns,wanted in checks: assert (residual(f2,k,ns)<=1e-7)==wanted
    return rows


def measure_case(case, human):
    t0=time.monotonic(); cid=case['id']; dsl=case['dsl']; depth=structure(dsl)
    row={k:(float(v) if k in BASE+['human'] else v) for k,v in human.items()}
    row.update(id=cid,year=int(cid.split('-')[1]),construction_depth=max(depth.values(),default=0))
    bundle=load_problem_bundle(GeometryProblem.model_validate(dsl).engine_document())
    ev=build_ir_evaluator(bundle); names=[c['name'] for c in dsl['constructions']]
    rawp=ROOT/'jssa/difficulty/minima/raw-323'/f'{cid}.json'
    raw=json.loads(rawp.read_text()) if rawp.exists() else {}
    recs=raw.get('records',[])
    row['saved_starts']=len(recs);row['saved_hits']=sum(r.get('cls')=='hit' for r in recs)
    row['local_difficulty']=-math.log((row['saved_hits']+.5)/(len(recs)+1)) if recs else None
    row['p_saved']=row['saved_hits']/len(recs) if recs else None
    selected=sorted([r for r in recs if r.get('cls')=='hit' and 'x' in r and np.isfinite(r['x']).all()],key=lambda r:r['k'])[:3]
    if not bundle.var_names: selected=[{'k':None,'x':[]}]
    row['selected_hits']=len(selected)
    figs=[];checks=[];accepted=[]
    with evaluation_session(ev):
        for rec in selected:
            x=rec['x']
            try:
                rr=ev.evaluate_float_residual(x); g=ev.evaluate_guard(x)[0]
                hf=ev.evaluate_float_hard_feasibility(x,include_margins=False).hard_feasible
                ok=rr.is_finite and rr.residual_norm_float<=1e-7 and g and hf
                checks.append({'k':rec['k'],'residual':rr.residual_norm_float,'guard':g,'hard':hf,'ok':ok})
                if ok:
                    fig=figure(bundle,x,names)
                    if len(fig['points'])>30: raise ValueError('over 30 named points')
                    figs.append(fig);accepted.append(rec)
            except Exception as e:
                checks.append({'k':rec['k'],'error':str(e),'ok':False})
        row['accepted_figures']=len(figs)
        if not figs:
            row.update(status='no_saved_hit' if not selected else 'revalidation_or_geometry_failed',seconds=time.monotonic()-t0)
            return row,{'id':cid,'checks':checks,'predicates':[]}
        if any(set(f['points'])!=set(figs[0]['points']) or set(f['circles'])!=set(figs[0]['circles']) for f in figs):
            raise ValueError('inconsistent named geometry across hits')
        row['measured_points']=len(figs[0]['points']); row['measured_circles']=len(figs[0]['circles'])
        explained, explicit=explicit_facts(dsl,set(figs[0]['points']),set(figs[0]['circles']))
        candidates=enumerate_candidates(figs[0]); facts=[]
        for kind,ns,err in candidates:
            errors=[err]+[residual(f,kind,ns) for f in figs[1:]]
            mx=max(errors)
            if mx<=1e-6:
                facts.append({'kind':kind,'objects':ns,'max_error':mx,'explicit':explained(kind,ns),
                              'depth':max(depth[n] for n in ns)})
        pert=[];pt_tries=0
        if bundle.var_names:
            x=np.array(accepted[0]['x']);rng=np.random.default_rng([22023,int(hashlib.sha256(cid.encode()).hexdigest()[:8],16)])
            while len(pert)<8 and pt_tries<64:
                pt_tries+=1
                try:
                    pf=figure(bundle,x+1e-3*np.maximum(1,np.abs(x))*rng.standard_normal(len(x)),names)
                    if set(pf['points'])==set(figs[0]['points']) and set(pf['circles'])==set(figs[0]['circles']): pert.append(pf)
                except Exception: pass
        for fact in facts:
            errors=[residual(f,fact['kind'],fact['objects']) for f in pert]
            # Undefined/degenerate predicates cannot count as a broken relation.
            finite=[v for v in errors if math.isfinite(v)]
            fact['perturbations_valid']=len(finite)
            fact['perturbations_broken']=sum(v>1e-5 for v in finite)
            fact['solution_dependent']=len(finite)>=3 and fact['perturbations_broken']>=2
        row['perturbation_figures']=len(pert);row['perturbation_tries']=pt_tries
        for tol in TOLS:
            tag=f'{tol:.0e}'
            active=[f for f in facts if f['max_error']<=tol]
            hidden=[f for f in active if not f['explicit']]
            for kind in KINDS:
                row[f'raw_{kind}_{tag}']=sum(f['kind']==kind for f in active)
                row[f'hidden_{kind}_{tag}']=sum(f['kind']==kind for f in hidden)
            row[f'hidden_depth_{tag}']=max([f['depth'] for f in hidden]or[0])
            row[f'hidden_count_{tag}']=len(hidden)
            row[f'kind_count_{tag}']=len({f['kind'] for f in hidden})
        active=[f for f in facts if f['max_error']<=1e-7 and not f['explicit']]
        dependent=[f for f in active if f['solution_dependent']]
        row['solution_dependent_count']=len(dependent)
        row['log_solution_dependent']=math.log1p(len(dependent))
        row['solution_depth']=max([f['depth'] for f in dependent]or[0])
        for kind in KINDS: row[f'log_hidden_{kind}']=math.log1p(row[f'hidden_{kind}_1e-07'])
        row['hidden_depth']=row['hidden_depth_1e-07'];row['status']='ok';row['seconds']=time.monotonic()-t0
        row['strict_stable']=all(row[f'hidden_{k}_1e-07']==row[f'hidden_{k}_1e-08'] for k in KINDS)
        row['loose_stable']=all(row[f'hidden_{k}_1e-07']==row[f'hidden_{k}_1e-06'] for k in KINDS)
        evidence={'id':cid,'checks':checks,'var_names':list(bundle.var_names),'saved_coordinates':accepted,
                  'points':figs[0]['points'],'circles':figs[0]['circles'],'depths':depth,
                  'explicit_extraction':explicit,'predicates':facts}
        return row,evidence


def ecdf(train,test):
    a=np.sort(train)
    return (np.searchsorted(a,test,side='left')+np.searchsorted(a,test,side='right'))/(2*len(a))


def cross_validate(rows, target='human', models=MODELS):
    out=[]
    for contest in ('AIME','HMMT'):
        data=[r for r in rows if r['contest']==contest and r.get(target) is not None]
        for year in sorted({r['year'] for r in data}):
            tr=[r for r in data if r['year']!=year];te=[r for r in data if r['year']==year]
            if not tr: continue
            y=np.array([r[target] for r in tr]);z=np.array([r[target] for r in te])
            yt,zt=ecdf(y,y),ecdf(y,z)
            scored=[{'id':r['id'],'contest':contest,'year':year,'target':target,'actual_raw':r[target],'actual_rank':float(t)} for r,t in zip(te,zt)]
            for name,cols in models.items():
                a=np.array([[r[k] for k in cols] for r in tr],float);b=np.array([[r[k] for k in cols] for r in te],float)
                a,b=np.column_stack([ecdf(a[:,j],a[:,j]) for j in range(a.shape[1])]),np.column_stack([ecdf(a[:,j],b[:,j]) for j in range(a.shape[1])])
                mean,scale=a.mean(0),a.std(0);scale=np.where(scale>0,scale,1)
                a=np.column_stack([np.ones(len(a)),(a-mean)/scale]);b=np.column_stack([np.ones(len(b)),(b-mean)/scale])
                penalty=np.eye(a.shape[1]);penalty[0,0]=0
                beta=np.linalg.solve(a.T@a+penalty,a.T@yt);pred=np.clip(b@beta,0,1)
                for r,p,t in zip(scored,pred,zt): r[name]=float(p);r[f'se_{name}']=float((p-t)**2)
            out+=scored
    summary={}
    for contest in ('AIME','HMMT'):
        data=[r for r in out if r['contest']==contest];rng=np.random.default_rng(2202301)
        years=sorted({r['year'] for r in data});by={yr:[r for r in data if r['year']==yr] for yr in years}
        s={'n':len(data),'years':years,'models':{}}
        if not data:summary[contest]=s;continue
        for model in models:
            mse=float(np.mean([r[f'se_{model}'] for r in data]));rho=float(spearmanr([r[model] for r in data],[r['actual_raw'] for r in data]).statistic)
            vals={'mse':mse,'spearman':rho}
            if 'B_D' in models:
                base=np.mean([r['se_B_D'] for r in data]);vals['reduction_vs_B_D']=float(1-mse/base)
                diffs=[]
                for _ in range(2000):
                    sample=[r for yr in rng.choice(years,len(years),replace=True) for r in by[yr]]
                    diffs.append(np.mean([r['se_B_D']-r[f'se_{model}'] for r in sample]))
                vals['mse_improvement_ci95']=np.quantile(diffs,[.025,.975]).tolist()
            s['models'][model]=vals
        summary[contest]=s
    return out,summary


def analyze(rows):
    good=[r for r in rows if r.get('status')=='ok']
    baseline_rows=[r for r in rows if 'construction_depth' in r]
    bo,bs=cross_validate(baseline_rows,models={'B_S':BASE,'B_D':DEEP})
    pred,cv=cross_validate(good);po,ps=cross_validate(good,target='local_difficulty')
    sensitivity={}
    for tol in (1e-8,1e-6):
        changed=[];tag=f'{tol:.0e}'
        for r in good:
            q=dict(r)
            for k in KINDS:q[f'log_hidden_{k}']=math.log1p(r[f'hidden_{k}_{tag}'])
            q['hidden_depth']=q[f'hidden_depth_{tag}'];changed.append(q)
        _,sensitivity[tag]=cross_validate(changed,models={'B_D':DEEP,'B_H':DEEP+HIDDEN})
    positive=[r for r in good if r['n_vars']>0 and r['perturbation_figures']>=3]
    p1=all(cv[c]['models']['B_H']['reduction_vs_B_D']>=.1 for c in ('AIME','HMMT'))
    p2=all(cv[c]['models']['B_H']['spearman']>v for c,v in [('AIME',.80),('HMMT',.70)])
    p3=sum(r['solution_dependent_count']>0 for r in positive)/len(positive) if positive else None
    p4=all(ps[c]['models']['B_H']['reduction_vs_B_D']<=.05 for c in ('AIME','HMMT'))
    quality=sum(r['strict_stable'] for r in good)/len(good)
    summary={'target_n':len(rows),'measured_n':len(good),'excluded':[{k:r.get(k) for k in ('id','status','error')} for r in rows if r.get('status')!='ok'],
             'baseline_all':bs,'primary_human':cv,'local_difficulty':ps,'sensitivity':sensitivity,
             'predictions':{'P1':p1,'P2_reference_numbers_only':p2,'P3_fraction':p3,'P3':p3 is not None and p3>=.25,'P4':p4,'quality_fraction':quality,'quality_pass':quality>=.90},
             'counts':{'hidden':{k:sum(r[f'hidden_{k}_1e-07'] for r in good) for k in KINDS},
                       'raw':{k:sum(r[f'raw_{k}_1e-07'] for r in good) for k in KINDS},
                       'solution_dependent':sum(r['solution_dependent_count'] for r in good),
                       'positive_var_evaluable_n':len(positive),'solution_dependent_problem_n':sum(r['solution_dependent_count']>0 for r in positive),
                       'zero_vars_n':sum(r['n_vars']==0 for r in good),
                       'no_hidden_n':sum(r['hidden_count_1e-07']==0 for r in good)}}
    write_csv('loyo-predictions.csv',pred);write_csv('loyo-baseline-all.csv',bo);write_csv('loyo-local-difficulty.csv',po)
    write_json('summary.json',summary)
    print(json.dumps(safe(summary),ensure_ascii=False),flush=True)


def main():
    mode=sys.argv[1] if len(sys.argv)>1 else 'run'
    if mode=='register':register();return
    lock=json.loads((HERE/'registration-lock.json').read_text())
    mismatches=[p for p,h in lock['files'].items() if digest(ROOT/p)!=h]
    if mismatches:raise ValueError(f'registration mismatch {mismatches}')
    if mode=='analyze':analyze(json.loads((HERE/'features.json').read_text()));return
    t0=time.monotonic();cases,human=load_inputs();rows=[]
    write_json('primitive-validation.json',check_geometry())
    for i,h in enumerate(human):
        cid=h['case_id']
        try:
            row,evidence=measure_case(cases[cid],h)
            write_json(f'figures/{cid}.json',evidence)
        except Exception as e:
            row={k:(float(v) if k in BASE+['human'] else v) for k,v in h.items()}
            row.update(id=cid,year=int(cid.split('-')[1]),status='error',error=f'{type(e).__name__}: {e}',construction_depth=max(structure(cases[cid]['dsl']).values(),default=0))
        rows.append(row)
        print(i+1,cid,row['status'],row.get('hidden_count_1e-07'),round(time.monotonic()-t0,2),flush=True)
    write_json('features.json',rows);write_csv('features.csv',rows)
    write_json('run-metadata.json',{'elapsed_measurement_seconds':time.monotonic()-t0,'new_local_searches':0,
             'python':sys.version,'numpy':np.__version__,'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'registration_verified':True})
    analyze(rows)


if __name__=='__main__':main()
