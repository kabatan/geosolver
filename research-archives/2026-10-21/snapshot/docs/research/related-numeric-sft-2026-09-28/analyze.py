"""Numeric scoring and completion inventory; never supplies labels to a model."""
import argparse,hashlib,importlib.util,json,math,sys
from pathlib import Path
P=Path(__file__).resolve().parent;R=P.parents[2];O=R/'qwen/.runtime/related_numeric_sft_20260928';sys.path.insert(0,str(R))
from qwen.answer_check import parse_numeric,extract_answer,final_text
spec=importlib.util.spec_from_file_location('scorer',R/'docs/research/transfer-reanalysis-2026-09-26/score_numeric.py');sc=importlib.util.module_from_spec(spec);spec.loader.exec_module(sc)
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def parse(raw):
 c=sc.last_committed_answer(raw)
 if c:return c['parsed'],c['marker'],c['expression']
 text=(final_text(raw) or '').strip();p=extract_answer(text)
 if p is not None:return p,'whole_response',text
 line=text.splitlines()[-1] if text else '';return extract_answer(line.strip('*` ')),'last_line',line

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--partial',action='store_true');a=ap.parse_args()
 keys={};jobs=[]
 for kind in ['main','diagnostic']:
  if (O/f'{kind}-answer-key.json').exists():keys.update(read(O/f'{kind}-answer-key.json'))
  if (O/f'{kind}-jobs.json').exists():jobs += [dict(j,kind=kind) for j in read(O/f'{kind}-jobs.json')]
 caps=read(O/'final-cap-by-job.json') if (O/'final-cap-by-job.json').exists() else {}
 rows=[];proof=[]
 for arm in ['base','sft-a','sft-b']:
  for j in jobs:
   cap=caps.get(j['id'],32768);suffix='' if cap==32768 else '-'+str(cap)
   f=O/f"{arm}-{j['kind']}{suffix}"/(j['id']+'-0.json')
   if not f.exists():
    if a.partial:continue
    raise FileNotFoundError(f)
   r=read(f);assert r['messages']==j['messages'] and r['seed']==j['seed']
   row={'arm':arm,'job_id':j['id'],'source_id':j['source_id'],'split':j['split'],'file':str(f),'file_sha256':sha(f),'cap':cap,'finish_reason':r['finish_reason'],'tokens':len(r['completion_ids'])}
   if j['split']=='proof':proof.append(row);continue
   expected=keys[j['id']]['answer_exact'];got,method,excerpt=parse(r['raw_text']);correct=None;val=None
   if got is not None:
    try:
     val=float(parse_numeric(got));want=float(parse_numeric(expected));correct=math.isfinite(val) and (abs(val-want)<=1e-4 or abs(val-want)<=1e-5*abs(want))
    except (ValueError,TypeError,OverflowError):pass
   row.update(expected=expected,parsed=got,value=val,numeric_correct=correct,parse_method=method,answer_excerpt=excerpt[-500:],final_excerpt=r['final_text'][-1500:]);rows.append(row)
 summary={}
 for arm in ['base','sft-a','sft-b']:
  summary[arm]={}
  for split in ['untrained_configuration','new_shape','trained_example','retention']:
   subset=[r for r in rows if r['arm']==arm and r['split']==split]
   summary[arm][split]={'n':len(subset),'correct':sum(r['numeric_correct'] is True and r['finish_reason']=='stop' for r in subset),'unparsed':sum(r['numeric_correct'] is None for r in subset),'length':sum(r['finish_reason']=='length' for r in subset)}
  subset=[r for r in proof if r['arm']==arm];summary[arm]['proof_generation']={'n':len(subset),'length':sum(r['finish_reason']=='length' for r in subset)}
 result={'status':'partial' if a.partial else 'complete','summary':summary,'numeric':rows,'proof':proof,'tolerances':{'absolute':1e-4,'relative':1e-5},'note':'No proof or numeric-derivation grades included yet.'}
 write(O/('partial-scores.json' if a.partial else 'numeric-scores.json'),result)
 print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
