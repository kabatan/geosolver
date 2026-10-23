"""Independent checks on Q26's collected evidence and exported joins. No solver."""
import ast
import csv
import hashlib
import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]


def rows(name):
    with (ROOT / name).open(newline='') as f:
        return list(csv.DictReader(f))


def key(row):
    return row['competition'], row['model'], int(row['problem_idx'])


def close(actual, expected):
    assert math.isclose(float(actual), float(expected), rel_tol=0, abs_tol=1e-10), (actual, expected)


checks = []
llm = rows('llm_per_problem.csv')
traces = [json.loads(line) for line in (ROOT / 'trace-summaries.jsonl').read_text().splitlines()]
assert len(llm) == len(traces) == len({key(r) for r in traces}) == 246
index = {key(r): r for r in traces}
for r in llm:
    t = index[key(r)]
    q = parse_qs(urlsplit(r['source_url']).query)
    assert q['model'] == [r['model']]
    assert q['comp'][0].endswith('--' + r['competition'])
    assert int(q['problem_index'][0]) + 1 == int(r['problem_idx'])
    assert q['problem_name'] == [r['problem_label']]
    # Re-read saved HTML class evidence rather than trusting the derived counts.
    evidence = {}
    for b in t['grading_evidence']:
        attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', b['attributes']))
        classes = attrs['class'].split()
        assert ('correctTablink' in classes) != ('incorrectTablink' in classes)
        evidence[int(attrs['data-run'])] = int('correctTablink' in classes)
    assert set(evidence) == {1, 2, 3, 4}
    assert sum(evidence.values()) == int(r['n_correct'])
    assert [evidence[i] for i in range(1, 5)] == [x['correct'] for x in t['runs']]
    close(r['accuracy'], Fraction(sum(evidence.values()), 4))
assert sum(int(r['n_runs']) for r in llm) == 984
checks.append('246 problem-model rows / 984 grades agree with saved HTML tabs and URL IDs')

metadata = {(r['competition'], int(r['problem_idx'])): r for r in rows('problem_metadata.csv')}
for g in rows('geometry_gap.csv'):
    pool = [r for r in llm if r['competition'] == g['competition'] and r['model'] == g['model']]
    d = g['geometry_definition']
    if d.endswith('individual_only'):
        pool = [r for r in pool if int(r['problem_idx']) <= 30]
    flags = []
    for r in pool:
        i = int(r['problem_idx'])
        m = metadata[r['competition'], i]
        if d.startswith('official_geometry_section'):
            flag = 21 <= i <= 30
        elif d.startswith('publisher_any_geometry'):
            flag = 'Geometry' in m['publisher_types'].split('|')
        elif d == 'publisher_pure_geometry':
            flag = m['publisher_types'] == 'Geometry'
        else:
            flag = m['analyst_geometry'] == '1'
            if d.endswith('boundary') and i == 21:
                flag = False
        flags.append(flag)
    ng = sum(flags)
    kg = sum(int(r['n_correct']) for r, flag in zip(pool, flags) if flag)
    ko = sum(int(r['n_correct']) for r, flag in zip(pool, flags) if not flag)
    no = len(pool) - ng
    assert (ng, no, kg, ko, ng * 4, no * 4) == tuple(int(g[k]) for k in [
        'geometry_problems', 'other_problems', 'geometry_correct', 'other_correct', 'geometry_runs', 'other_runs'])
    close(g['gap_percentage_points'], 100 * (Fraction(kg, ng * 4) - Fraction(ko, no * 4)))
checks.append('All category definitions and rate differences recompute from per-problem records')

cross = rows('crosswalk.csv')
assert len(cross) == len({r['case_id'] for r in cross}) == 397
assert Counter(r['study_set'] for r in cross) == {'development_323': 323, 'new2026_20': 20, 'unseen_54': 54}
overlap = {s: sum(int(r['overlap_in_four_competitions']) for r in cross if r['study_set'] == s)
           for s in ['development_323', 'new2026_20', 'unseen_54']}
assert overlap == {'development_323': 16, 'new2026_20': 10, 'unseen_54': 0}
assert len(rows('matched_problems.csv')) == 26
compare = rows('solver_comparison.csv')
assert len(compare) == 52
assert all(r['study_set'] != 'unseen_54' for r in compare)
assert all(r['solver_final_runs'] == '' for r in compare if r['study_set'] == 'new2026_20')
with (REPO / 'jssa/results/stage-profile-20261023/per-case.csv').open(newline='') as f:
    source = {(r['case_id'], r['seed']): r for r in csv.DictReader(f)}
fr = rows('solver_final_runs.csv')
assert len(fr) == len({(r['case_id'], r['seed']) for r in fr}) == 48
for r in fr:
    original = source[r['case_id'], r['seed']]
    assert all(r[k] == original[k] for k in ['correct', 'status', 'wall_time_s'])
assert all(r['correct'] == 'True' for r in fr)
checks.append('397 unique study IDs; overlaps 16/10/0; final solver 48/48 from unchanged existing records')

for r in rows('source_manifest.csv'):
    data = (ROOT / r['file']).read_bytes()
    assert hashlib.sha256(data).hexdigest() == r['sha256']
    assert len(data) == int(r['bytes'])
answer = (ROOT / 'answer.md').read_text()
for url in re.findall(r'\]\(([^)]+)\)', answer):
    if not url.startswith('https://'):
        assert (ROOT / url.split('#')[0]).exists(), url
for path in ROOT.glob('*.py'):
    ast.parse(path.read_text(), filename=str(path))
files = [p for p in ROOT.rglob('*') if p.is_file()]
largest = max(files, key=lambda p: p.stat().st_size)
assert largest.stat().st_size <= 5_000_000
checks.append('Source snapshot hashes, relative report links, Python syntax, and 5 MB limit verified')
result = {'status': 'PASS', 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
          'checks': checks, 'overlap_counts': overlap, 'llm_problem_model_rows': len(llm),
          'llm_graded_runs': 984, 'solver_final_matched_runs': len(fr),
          'largest_file': largest.name, 'largest_file_bytes': largest.stat().st_size}
(ROOT / 'validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False))
