"""Prepare bounded curl batches; summarize fetched public grading without retaining traces."""
import json,re,csv,hashlib,datetime,sys
from pathlib import Path
from urllib.parse import urlencode
ROOT=Path(__file__).resolve().parent
COMP=['aime_2025','hmmt_feb_2025','aime_2026','hmmt_feb_2026']
MODELS={c:['GPT-5.2 (high)', 'DeepSeek-R1' if '2025' in c else 'DeepSeek-v3.2 (Think)'] for c in COMP}
if sys.argv[1]=='prepare':
    jobs=[]
    for c in COMP:
        table=json.loads((ROOT/f'{c}-tables.json').read_text())['problem_table']
        cells=re.findall(r'<td\s+class="problem [\s\S]*?</td>',table)
        for cell in cells:
            attrs=dict(re.findall(r'([\w-]+)="([^"]*)"',cell))
            model=attrs.get('data-model-name')
            if model not in MODELS[c]: continue
            params={'comp':attrs['data-competition-key'],'model':model,'problem_index':attrs['data-problem-index'],'run':1,'problem_name':attrs['data-problem-name'],'model_name':model}
            jobs.append({'competition':c,'model':model,'model_config':attrs['data-model-id'],'problem_idx':int(attrs['data-problem-index'])+1,'problem_label':attrs['data-problem-name'],'url':'https://matharena.ai/trace?'+urlencode(params),'color':attrs['class']})
    assert len(jobs)==246,len(jobs)
    (ROOT/'trace-jobs.json').write_text(json.dumps(jobs,ensure_ascii=False,indent=2))
    for batch in range((len(jobs)+29)//30):
        lines=[]
        for j in range(batch*30,min((batch+1)*30,len(jobs))):
            if lines: lines.append('next')
            lines += ['silent','show-error','location','max-time = 15','max-filesize = 500000','url = "'+jobs[j]['url']+'"','output = "'+str(ROOT/f'trace-{j:03}.html')+'"']
        (ROOT/f'curl-batch-{batch}.txt').write_text('\n'.join(lines)+'\n')
    print('prepared',len(jobs),'public problem-model trace requests, 9 bounded sequential batches')
else:
    jobs=json.loads((ROOT/'trace-jobs.json').read_text());batch=int(sys.argv[1]);records=[]
    summaries=ROOT/'trace-summaries.jsonl'
    previous=[json.loads(l) for l in summaries.read_text().splitlines()] if summaries.exists() else []
    key=lambda r:(r['competition'],r['model'],r['problem_idx'])
    old={key(r):r for r in previous}
    assert len(old)==len(previous),'duplicate summaries; resolve explicitly before collecting'
    for j in range(batch*30,min((batch+1)*30,len(jobs))):
        rec=jobs[j].copy();p=ROOT/f'trace-{j:03}.html'
        if not p.exists() and old.get(key(rec),{}).get('status')=='取得':
            records.append(old[key(rec)]);continue
        rec['retrieved_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        rec['timestamp_basis']='summary extraction time, not HTTP acquisition time'
        if p.exists():
            b=p.read_bytes();s=b.decode(errors='replace');rec.update(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
            buttons=re.findall(r'<button\b([^>]*)>(.*?)</button>',s,re.S)
            runs=[]
            for a,t in buttons:
                at=dict(re.findall(r'([\w-]+)="([^"]*)"',a))
                if 'data-run' not in at: continue
                cls=at.get('class','').split()
                val=1 if 'correctTablink' in cls else 0 if 'incorrectTablink' in cls else None
                runs.append({'run':int(at['data-run']),'correct':val,'class':at.get('class','')})
            rec['runs']=runs
            rec['status']='取得' if len(runs)==4 and {r['run'] for r in runs}=={1,2,3,4} and all(r['correct'] is not None for r in runs) else '未取得'
            if rec['status']=='未取得': rec['reason']='response has no recognized complete grading tabs';rec['response_prefix']=s[:200]
            # Preserve only the grading tabs and content hash, not model reasoning.
            rec['grading_evidence']=[{'attributes':a,'label':re.sub(r'\s+',' ',t)} for a,t in buttons if 'data-run' in a]
            p.unlink()
        else: rec.update(status='未取得',reason='curl produced no response file (see collection log)')
        records.append(rec)
    old.update({key(r):r for r in records})
    ordered=[old[key(j)] for j in jobs if key(j) in old]
    data=''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in ordered).encode('utf-8')
    assert len(data)<=5_000_000,'summary exceeds 5 MB'
    temporary=ROOT/'trace-summaries.jsonl.tmp';temporary.write_bytes(data);temporary.replace(summaries)
    print('batch',batch,'retrieved',sum(r['status']=='取得' for r in records),'/',len(records))
    for r in records:
        if r['status']!='取得':print(r['competition'],r['model'],r['problem_idx'],r.get('runs'),r.get('response_prefix','')[:80])
