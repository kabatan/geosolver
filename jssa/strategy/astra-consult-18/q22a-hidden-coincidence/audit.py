"""Post-result checks of frozen Q22a outputs; never modifies primary outputs.

The two content examples were named in preregistration.md. Their manual source
interpretations and this code were written after measurement, not preregistered.
No solve, no optimization, no fitted-feature change, no exact-proof claim.
"""
from __future__ import annotations

import csv
import hashlib
import itertools as it
import json
import math
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[key] = '1'
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
os.environ['MPLCONFIGDIR'] = str(HERE / '.mpl')
import numpy as np
from scipy.stats import spearmanr


def read(name):
    return json.loads((HERE / name).read_text())


def distance(p, a, b):
    return float(np.linalg.norm(p[a] - p[b]))


def triangle_sides(p, ns):
    return np.sort([distance(p, a, b) for a, b in it.combinations(ns, 2)])


def normalized_triangle(p, ns):
    lengths = triangle_sides(p, ns)
    # Independent area calculation via the Gram determinant.
    u, v = p[ns[1]] - p[ns[0]], p[ns[2]] - p[ns[0]]
    area2 = math.sqrt(max(0.0, float((u @ u) * (v @ v) - (u @ v) ** 2)))
    if lengths[0] <= 1e-6 or area2 <= 1e-5 * lengths[-1] ** 2:
        return None
    return (lengths[:2] / lengths[2]) ** 2


def brute_similar(p, tolerance=1e-7):
    """All triangle pairs in small blocks; no spatial index or primary imports."""
    triangles, descriptors = [], []
    for ns in it.combinations(sorted(p), 3):
        descriptor = normalized_triangle(p, ns)
        if descriptor is not None:
            triangles.append(ns)
            descriptors.append(descriptor)
    descriptors = np.array(descriptors)
    found = set()
    for lo in range(0, len(descriptors), 64):
        err = np.abs(descriptors[lo:lo+64, None] - descriptors[None]).max(axis=2)
        i, j = np.where(err <= tolerance)
        found.update(triangles[a+lo] + triangles[b] for a, b in zip(i, j) if a+lo < b)
    return found, len(triangles)


def check_predictions():
    summary = read('summary.json')
    checks = {}
    for filename, section in [('loyo-predictions.csv', 'primary_human'),
                              ('loyo-local-difficulty.csv', 'local_difficulty'),
                              ('loyo-baseline-all.csv', 'baseline_all')]:
        with (HERE / filename).open() as f:
            rows = list(csv.DictReader(f))
        result = {}
        for contest in ('AIME', 'HMMT'):
            data = [r for r in rows if r['contest'] == contest]
            models = summary[section][contest]['models']
            assert len(data) == summary[section][contest]['n']
            c = {}
            for model, expected in models.items():
                squared = [(float(r[model]) - float(r['actual_rank'])) ** 2 for r in data]
                assert max(abs(se - float(r['se_' + model])) for se, r in zip(squared, data)) < 1e-14
                mse = float(np.mean(squared))
                rho = float(spearmanr([float(r[model]) for r in data],
                                     [float(r['actual_raw']) for r in data]).statistic)
                assert abs(mse - expected['mse']) < 1e-14
                assert abs(rho - expected['spearman']) < 1e-14
                c[model] = {'mse': mse, 'spearman': rho}
            result[contest] = c
        checks[filename] = result
    return checks


def check_facts():
    counts = {kind: 0 for kind in ('collinear', 'concyclic', 'equal_length', 'similar', 'tangent')}
    max_circumcircle_error = 0.0
    rows = read('features.json')
    measured = [r for r in rows if r['status'] == 'ok']
    for row in measured:
        e = read(f"figures/{row['id']}.json")
        p = {n: np.array(v) for n, v in e['points'].items()}
        facts = [f for f in e['predicates'] if f['max_error'] <= 1e-7]
        keys = [(f['kind'], tuple(f['objects'])) for f in facts]
        assert len(keys) == len(set(keys))
        for kind in counts:
            active = [f for f in facts if f['kind'] == kind]
            hidden = [f for f in active if not f['explicit']]
            assert len(active) == row[f'raw_{kind}_1e-07']
            assert len(hidden) == row[f'hidden_{kind}_1e-07']
            counts[kind] += len(active)
        # Alternative concyclicity check: fit circle through 3 points, test 4th.
        # This is only a numerical audit of positive facts, not exhaustive proof.
        for fact in facts:
            if fact['kind'] != 'concyclic':
                continue
            a, b, c, d = [p[n] for n in fact['objects']]
            center = np.linalg.solve(2 * np.array([b-a, c-a]),
                                     np.array([b@b-a@a, c@c-a@a]))
            radii = [float(np.linalg.norm(x-center)) for x in (a, b, c, d)]
            error = (max(radii) - min(radii)) / max(radii)
            max_circumcircle_error = max(max_circumcircle_error, error)
            assert error <= 1e-5, (row['id'], fact, error)
    assert counts == read('summary.json')['counts']['raw']
    return {'measured_n': len(measured), 'raw_counts_recounted': counts,
            'positive_concyclic_facts_checked_by_circumcenter': counts['concyclic'],
            'max_relative_circumcircle_radial_range': max_circumcircle_error,
            'strict_threshold_changed_ids': [r['id'] for r in measured if not r['strict_stable']]}


def content_examples():
    # The square names come from the official problem, not automatic recognition.
    squares = [('A','B','B1','A2'), ('B','C','C1','B2'), ('C','A','A1','C2'),
               ('A1','A2','A3','A4'), ('B1','B2','B3','B4'), ('C1','C2','C3','C4'),
               ('A3','B4','B5','A6'), ('B3','C4','C5','B6'), ('C3','A4','A5','C6')]
    e = read('figures/HMMT-2019-FEB-GEO-10.json')
    p = {n: np.array(v) for n, v in e['points'].items()}
    square_triangles = {tuple(sorted(t)) for square in squares for t in it.combinations(square, 3)}
    assert len(square_triangles) == 36
    right_isosceles_residual = max(float(np.max(np.abs(normalized_triangle(p, t)-[.5,.5])))
                                   for t in square_triangles)
    assert right_isosceles_residual < 1e-12
    square_pairs = {a+b for a, b in it.combinations(sorted(square_triangles), 2)}
    saved = {tuple(f['objects']) for f in e['predicates']
             if f['kind']=='similar' and not f['explicit'] and f['max_error']<=1e-7}
    brute, triangle_n = brute_similar(p)
    assert brute == saved
    trivial_pairs = saved & square_pairs
    assert len(trivial_pairs) == math.comb(36, 2) == 630

    # Official S2 supplies this point. Adding it here is a content diagnostic,
    # and is not claimed as automatic auxiliary-point discovery.
    assert 'B7' not in p
    a, b, c, d = [p[n] for n in ('B5', 'B4', 'B6', 'B3')]
    t, _ = np.linalg.solve(np.column_stack((b-a, -(d-c))), c-a)
    p['B7'] = a + t*(b-a)
    small = triangle_sides(p, ('B7','B4','B3'))
    original = triangle_sides(p, ('B','B1','B2'))
    large = triangle_sides(p, ('B7','B5','B6'))
    congruence_error = float(np.max(np.abs(small-original)/original))
    scale_ratios = large/small
    assert congruence_error < 1e-12
    assert np.max(np.abs(scale_ratios-5)) < 1e-12

    a = read('figures/AIME-2012-I-12.json')
    q = {n: np.array(v) for n, v in a['points'].items()}
    hidden = [f for f in a['predicates'] if not f['explicit'] and f['max_error']<=1e-7]
    assert not hidden
    aime_brute, aime_triangle_n = brute_similar(q)
    assert not aime_brute
    ratios = {'CD_over_BC': distance(q,'C','D')/distance(q,'B','C'),
              'DE_over_BE': distance(q,'D','E')/distance(q,'B','E')}
    ratio_error = abs(ratios['CD_over_BC']-ratios['DE_over_BE'])
    assert ratio_error < 1e-12
    assert max(abs(v-8/15) for v in ratios.values()) < 1e-12

    return {'HMMT-2019-FEB-GEO-10': {
                'hidden_candidates': 720, 'similar_candidates': len(saved),
                'square_triangle_pairs': len(trivial_pairs),
                'square_pair_fraction_of_similar': len(trivial_pairs)/len(saved),
                'square_pair_fraction_of_hidden': len(trivial_pairs)/720,
                'manually_identified_given_squares': squares,
                'right_isosceles_triangle_n': len(square_triangles),
                'max_right_isosceles_descriptor_error': right_isosceles_residual,
                'brute_force_valid_triangles': triangle_n,
                'brute_force_similar_exact_set_match': True,
                'official_S2_B7_absent_from_primary_points': True,
                'official_supplied_B7_normalized': p['B7'].tolist(),
                'official_S2_congruence_relative_error': congruence_error,
                'official_S2_large_over_small_side_ratios': scale_ratios.tolist(),
                'source': 'https://hmmt-archive.s3.amazonaws.com/tournaments/2019/feb/geo/solutions.pdf',
                'source_location': 'Problem 10, S1/S2, PDF pages 5-6',
                'scope': 'One published solution; no claim about all proofs or minimum depth.'},
            'AIME-2012-I-12': {
                'hidden_candidates': len(hidden), 'brute_force_valid_triangles': aime_triangle_n,
                'brute_force_similar_pairs': len(aime_brute),
                'official_angle_bisector_step_ratios': ratios,
                'ratio_equality_absolute_error': ratio_error,
                'step_expressible_in_registered_five_predicates': False,
                'source': 'https://www.isinj.com/mt-aime/2012AIME-ISolutions.pdf',
                'source_location': 'Problem 12, printed page 5; MAA pamphlet on third-party mirror',
                'scope': 'One official solution; no claim about the minimum over all proofs.'}}


def draw_examples(examples):
    # No plotting package is installed in the fixed environment. The two
    # coordinate diagrams are written as standard SVG using the stdlib.
    import xml.etree.ElementTree as ET
    root = ET.Element('svg', {'xmlns':'http://www.w3.org/2000/svg', 'width':'1240',
                             'height':'740', 'viewBox':'0 0 1240 740'})
    ET.SubElement(root,'rect',{'width':'1240','height':'740','fill':'white'})
    ink, blue, orange, gray = '#163047', '#167caf', '#c66a1e', '#9aa6ad'
    def text(x,y,value,size=18,color=ink,bold=False):
        t=ET.SubElement(root,'text',{'x':str(x),'y':str(y),'font-family':'DejaVu Sans',
            'font-size':str(size),'fill':color,'font-weight':'bold' if bold else 'normal'})
        t.text=value
    def point(v,offset):
        scale, center_y = (330,420) if offset == 285 else (410,390)
        return np.array([offset+scale*v[0],center_y-scale*v[1]])
    def path(p,names,offset,color,width=2):
        xy=[point(p[n],offset) for n in names]
        ET.SubElement(root,'polyline',{'points':' '.join(f'{x:.4f},{y:.4f}' for x,y in xy),
            'fill':'none','stroke':color,'stroke-width':str(width),'stroke-linejoin':'round'})
    def dot(v,offset,color=ink):
        x,y=point(v,offset)
        ET.SubElement(root,'circle',{'cx':str(x),'cy':str(y),'r':'3.5','fill':color})
    text(38,43,'Content audit: counted coincidences and solution relations differ',25,bold=True)
    text(38,83,'Saved numerical figures. No claim about minimum proof depth.',16)
    text(38,126,'AIME 2012 I-12',22,bold=True)
    text(38,155,'0 retained coincidence candidates',18)
    p={n:np.array(v) for n,v in read('figures/AIME-2012-I-12.json')['points'].items()}
    for names,color in [(('A','B','C','A'),ink),(('C','D'),blue),(('C','E'),blue)]:
        path(p,names,285,color,2.5)
    for n,v in p.items():
        dot(v,285)
        x,y=point(v,285)
        dx,dy={'A':(12,7),'B':(-22,-8),'C':(-22,17),'D':(13,9),'E':(12,4)}[n]
        text(x+dx,y+dy,n,18)
    text(38,649,'Official solution uses a ratio equality:',18)
    text(38,679,'CD / BC = DE / BE = 8 / 15',21,color=blue,bold=True)
    text(38,710,'This relation is outside the five registered predicate types.',15)
    text(634,126,'HMMT 2019 Geometry 10',22,bold=True)
    text(634,155,'630 / 679 similar pairs come from given squares',18)
    p={n:np.array(v) for n,v in read('figures/HMMT-2019-FEB-GEO-10.json')['points'].items()}
    squares=examples['HMMT-2019-FEB-GEO-10']['manually_identified_given_squares']
    for square in squares:
        path(p,square+square[:1],900,gray,1.4)
    p['B7']=np.array(examples['HMMT-2019-FEB-GEO-10']['official_supplied_B7_normalized'])
    for names,color in [(('B7','B5','B6','B7'),orange),(('B7','B4','B3','B7'),blue)]:
        path(p,names,900,color,2.5)
    offsets={'B7':(-37,-9),'B4':(-35,14),'B3':(8,15),'B5':(-9,24),
             'B6':(8,-2),'B1':(-32,18),'B2':(-16,-10),'B':(-24,-8)}
    for n,(dx,dy) in offsets.items():
        dot(p[n],900,orange if n=='B7' else ink)
        x,y=point(p[n],900);text(x+dx,y+dy,n,16)
    text(634,649,'Official S2 uses B7, absent from the DSL.',18)
    text(634,679,'Blue and orange triangles have scale ratio 1:5.',18,color=blue)
    text(634,710,'B7 was supplied by the official solution, not discovered.',15)
    ET.ElementTree(root).write(HERE/'content-audit.svg',encoding='utf-8',xml_declaration=True)


def main():
    lock = read('registration-lock.json')
    mismatches = [p for p,h in lock['files'].items()
                  if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
    assert not mismatches, mismatches
    result = {'audit_timing': 'post-result', 'registration_file_n': len(lock['files']),
              'registration_hash_mismatches': mismatches, 'primary_outputs_modified': False,
              'predictions_recomputed_from_csv': check_predictions(),
              'fact_counts_and_independent_geometry_checks': check_facts(),
              'content_examples': content_examples()}
    draw_examples(result['content_examples'])
    (HERE/'audit-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
