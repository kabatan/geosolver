"""Print source text and literal DSL for manual review; never evaluates DSL."""
from pathlib import Path
import json
import re
import sys

HERE = Path(__file__).resolve().parent
for r in json.loads((HERE/'primary-extracts.json').read_text()):
    if not any(re.search(pattern,r['id']) for pattern in sys.argv[1:]):
        continue
    d = json.loads((HERE.parent/'dsl'/f"{r['id']}.json").read_text())
    print('\n###',r['id'])
    print('PRIMARY:', r.get('primary_statement',{}).get('text') if r.get('primary_statement') else '(unavailable / HMMT separately)')
    print('SECONDARY:', r['secondary_statement'])
    print('ANSWER:',json.dumps(r['stored_answer'],ensure_ascii=False))
    print('VARIABLES:',d['variables'])
    for i,c in enumerate(d['constructions']):
        print(f"c{i}: {c['name']} = {c['expression']}")
    for i,c in enumerate(d['conditions']):
        print(f"q{i}: "+(c['predicate'] if 'predicate' in c else f"{c['left']} {c['operator']} {c['right']}"))
    print('TARGET:',d['target'])
