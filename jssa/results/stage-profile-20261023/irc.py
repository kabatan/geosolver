import json,sys
from pathlib import Path
from collections import Counter
root=Path(sys.argv[1]); cases=Counter(); st=Counter(); ex=None
for f in sorted(root.glob('runs/*/*.json')):
    d=json.load(open(f)); sr=d.get('solver_result') or {}; dg=sr.get('diagnostics') or {}; ps=dg.get('pipeline_summary') or {}
    tags=(ps.get('exact_assembly') or {}).get('rejection_tags') or []
    if any('IRCompileError' in t for t in tags):
        cases[f.parent.name]+=1; st[sr.get('status')]+=1
print(len(cases),'cases', st); print(sorted(cases.items())[:40])
