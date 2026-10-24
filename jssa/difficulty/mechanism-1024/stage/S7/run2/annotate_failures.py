"""Post-run reporting only: expand exit-code missing reasons from existing logs.

No search, refinement, candidate measurement, threshold or denominator changes.
This reporting utility is added after campaign start; its hash is in used-hashes.
"""
import csv
import hashlib
import io
import json
from datetime import datetime,timezone
from pathlib import Path

OUT=Path(__file__).resolve().parent
M=json.loads((OUT/'pre-run-hashes.json').read_text())
ROOT=Path(M['scratch'])
judgments=json.loads((OUT/'judgments.json').read_text())
replacements={}
for row in judgments['missing']:
    reason=row['reason']
    mode=reason.split(':',1)[0]
    path=ROOT/'runs'/row['case_id']/(mode+'.log')
    if path.exists() and path.stat().st_size:
        lines=[line.strip() for line in path.read_text(errors='replace').splitlines() if line.strip()]
        terminal=lines[-1][:1000]
        if 'Error' in terminal or 'Exception' in terminal:
            replacements[(row['case_id'],row['arm'],reason)]=reason+'; '+terminal+'; log='+str(path)

for name in ('per-problem.csv','per-candidate.csv'):
    path=OUT/name
    with path.open(newline='') as f:
        reader=csv.DictReader(f);keys=reader.fieldnames;rows=list(reader)
    for row in rows:
        for key,value in row.items():
            for (case,arm,old),new in replacements.items():
                if row.get('case_id')==case and value==old:
                    row[key]=new
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)

for name in ('judgments.json','audit.json'):
    path=OUT/name;obj=json.loads(path.read_text())
    for row in obj['missing']:
        row['reason']=replacements.get((row['case_id'],row['arm'],row['reason']),row['reason'])
    if name=='audit.json':
        obj['failure_log_annotations']=len(replacements)
        obj['reporting_note']='annotate_failures.py added after campaign start; expands missing reasons only; no measurements or judgments changed'
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

path=OUT/'answer.md';answer=path.read_text()
for (case,arm,old),new in replacements.items():
    oldline=f'| {case} | {arm} | {old.replace(chr(124),chr(47))} |'
    newline=f'| {case} | {arm} | {new.replace(chr(124),chr(47))} |'
    answer=answer.replace(oldline,newline)
answer+='\n終了コードだけでは不足する欠測理由は、生ログの例外末尾をannotate_failures.pyで追記した。この補助スクリプトは実行開始後の報告用追加であり、探索・精密化・測定値・判定規則は変更していない。\n'
path.write_text(answer)
with (OUT/'progress.md').open('a') as f:
    f.write('\n'+datetime.now(timezone.utc).isoformat()+f' 生ログから欠測例外の詳細を{len(replacements)}件追記。再実行なし。\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
paths=[p for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='used-hashes.json' and '__pycache__' not in p.parts]
assert all(p.stat().st_size<3_000_000 for p in paths)
(OUT/'used-hashes.json').write_text(json.dumps({str(p.relative_to(OUT)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in paths},indent=2)+'\n')
print('Expanded existing-log failure reasons:',len(replacements))
