"""Stage (0), syntax-only exhaustive selection. No solver or numerical results."""
import ast
import hashlib
import json
import re
from pathlib import Path

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[4]
ROOTS = ['benchmarks/dsl', 'jssa/difficulty/unseen-2/a/dsl',
         'jssa/difficulty/unseen-2/b/dsl', 'jssa/difficulty/unseen-1983/dsl',
         'jssa/difficulty/new2026/dsl', 'jssa/difficulty/holdout-1023/dsl']

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def save(p, value):
    data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    assert len(data.encode()) < 3_000_000
    p.write_text(data)

def identity(key):
    key = re.sub(r'\.k\d+$', '', key).upper()
    parts = key.split('-')
    if parts[0] == 'AIME' and len(parts) == 4:
        parts[2] = {'1': 'I', '2': 'II'}.get(parts[2], parts[2])
    return '-'.join(str(int(p)) if p.isdigit() else p for p in parts)

def contact_conditions(dsl):
    defs = {c['name']: ast.parse(c['expression'], mode='eval').body for c in dsl['constructions']}
    def resolve(n):
        seen = set()
        while isinstance(n, ast.Name) and n.id in defs and n.id not in seen:
            seen.add(n.id); n = defs[n.id]
        return n
    def call(n, name, count):
        return isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == name and len(n.args) == count
    def same(a, b):
        return ast.dump(resolve(a), include_attributes=False) == ast.dump(resolve(b), include_attributes=False)
    def circle_parts(n):
        n = resolve(n)
        if call(n, 'Circle', 2):
            return n.args
        return None
    rows = []
    for i, c in enumerate(dsl['conditions']):
        nodes = [ast.parse(str(c[k]), mode='eval').body for k in ['left','right','predicate'] if k in c]
        tangent = any(call(n, 'IsTangent', 2) for root in nodes for n in ast.walk(root))
        distances = []
        if c.get('operator') == '=':
            a, b = [ast.parse(str(c[k]), mode='eval').body for k in ['left','right']]
            for distance, radius in [(a,b),(b,a)]:
                distance = resolve(distance)
                if not call(distance, 'Distance', 2):
                    continue
                for center, line in [distance.args, list(reversed(distance.args))]:
                    if not call(resolve(line), 'Line', 2):
                        continue
                    circles = list(defs.values())
                    # Center(C)/Radius(C), including constructed circles.
                    if call(resolve(center), 'Center', 1) and call(resolve(radius), 'Radius', 1):
                        if same(resolve(center).args[0], resolve(radius).args[0]):
                            distances.append(dict(center=ast.unparse(center),line=ast.unparse(line),radius=ast.unparse(radius)))
                    # Circle(center,radius), including direct construction aliases.
                    for circle in circles:
                        parts = circle_parts(circle)
                        if parts and same(center, parts[0]) and same(radius, parts[1]):
                            distances.append(dict(center=ast.unparse(center),line=ast.unparse(line),radius=ast.unparse(radius)))
        if tangent or distances:
            rows.append(dict(condition_index=i, condition=c, kinds=(['IsTangent'] if tangent else []) + (['Distance(center,line)=radius'] if distances else []), distance_matches=distances))
    return rows

def main():
    contacts = OUT.parent / 'S3/contacts.json'
    excluded = {identity(c['case_id']) for c in json.loads(contacts.read_text())['cases']}
    assert len(excluded) == 12
    groups, scanned, exclusions, non_dsl = {}, {}, [], []
    for root in ROOTS:
        for p in sorted((REPO / root).rglob('*.json')):
            rel = str(p.relative_to(REPO)); scanned[rel] = sha(p)
            dsl = json.loads(p.read_text())
            if not isinstance(dsl, dict) or 'constructions' not in dsl:
                non_dsl.append(rel)
                continue
            rows = contact_conditions(dsl)
            if not rows:
                continue
            key = identity(dsl['id'])
            entry = dict(path=rel,sha256=sha(p),dsl_id=dsl['id'],contacts=rows)
            if key in excluded:
                exclusions.append(entry | dict(identity=key,reason='S1/S3 12問'))
            else:
                groups.setdefault(key,[]).append(entry)
    targets = []
    for key, occurrences in sorted(groups.items()):
        # ROOTS priority, then lexical path, independent of outcomes. All variants retained as provenance.
        chosen = occurrences[0]
        targets.append(dict(case_id=chosen['dsl_id'],identity=key,dsl_path=chosen['path'],sha256=chosen['sha256'],contacts=chosen['contacts'],occurrences=occurrences))
    save(OUT/'targets.json',dict(stage='(0)',selection_script_sha256=sha(Path(__file__)),roots=ROOTS,
        deduplication='case ID: remove .kN, case-fold, numeric zero-padding; AIME 1/2 -> I/II; choose ROOTS order then lexical path; retain every occurrence',
        excluded_contacts_sha256=sha(contacts),excluded_identities=sorted(excluded),scanned_count=len(scanned),target_count=len(targets),targets=targets))
    save(OUT/'selection-audit.json',dict(scanned_files_sha256=scanned,excluded_contact_files=exclusions,non_dsl_json=non_dsl))
    print('Scanned',len(scanned),'files; selected',len(targets),'unique problems')
    for t in targets: print(t['case_id'],len(t['contacts']),t['dsl_path'])

if __name__ == '__main__': main()
