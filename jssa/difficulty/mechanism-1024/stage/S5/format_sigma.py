"""Lossless notation-only serialization: append e+0 to sigma with exponent zero."""
import json
from pathlib import Path
from select_targets import save,sha
OUT=Path(__file__).resolve().parent
changes=[]
def sci(s):
    return s if 'e' in s.lower() else s+'e+0'
for p in sorted((OUT/'results').rglob('*.json')):
    obj=json.loads(p.read_text());before=sha(p);changed=False
    def visit(v):
        global changed
        if isinstance(v,dict):
            for k,x in list(v.items()):
                if k=='singular_values':
                    new=[sci(s) for s in x];changed=changed or new!=x;v[k]=new
                elif k in ['T1_sigma','T1_sigma_check','T2_sigma','T2_sigma_check']:
                    new=sci(x);changed=changed or new!=x;v[k]=new
                else:visit(x)
        elif isinstance(v,list):
            for x in v:visit(x)
    visit(obj)
    if changed:
        save(p,obj);changes.append(dict(path=str(p.relative_to(OUT)),before_sha256=before,after_sha256=sha(p)))
save(OUT/'sigma-formatting-audit.json',dict(script_sha256=sha(Path(__file__)),
    transformation='append e+0 where sigma exponent is zero; no numerical value changes',changes=changes))
print('Formatted',len(changes),'files; no numerical computations')
