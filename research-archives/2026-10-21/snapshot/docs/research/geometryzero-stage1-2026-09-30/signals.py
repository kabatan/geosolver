"""Censor-aware GCPO calibration, conservative committed-answer parsing."""
import json,math,re,statistics,sys
from pathlib import Path
from prepare import HERE,ROOT,RUN,write,sha
sys.path.insert(0,str(ROOT))
from qwen.answer_check import parse_numeric,extract_answer
def score(row,gold,tok):
 text=row['raw_text'];tags=re.findall(r'<answer>(.*?)</answer>',text,re.S);candidate=tags[-1].strip() if len(tags)==1 else None
 parsed=None;value=None;exact=False;rel=None
 if candidate is not None:
  try:
   try:expr=parse_numeric(candidate)
   except ValueError:
    boxed=extract_answer(candidate);expr=parse_numeric(boxed) if boxed is not None else None
   if expr is not None:
    want=parse_numeric(gold);value=float(expr);parsed=str(expr);exact=bool((expr-want).simplify()==0);rel=abs(value-float(want))/max(abs(float(want)),1e-30)
  except (ValueError,TypeError,OverflowError,ZeroDivisionError):pass
 censored=row['finish_reason']!='stop';want=float(parse_numeric(gold))
 relaxed=int(rel is not None and rel<=.02);strict=int(value is not None and abs(value-want)<=max(1e-4,1e-5*abs(want)))
 # Literal upstream fallback bug diagnostic, not used in adapted reward.
 numbers=re.findall(r'-?\d+(?:\.\d+)?',candidate or text.split('<answer>')[-1]);gnums=re.findall(r'-?\d+(?:\.\d+)?',gold)
 fallback=int(bool(gnums) and any(abs(float(n)-float(gnums[-1]))<=.02*abs(float(gnums[-1])) for n in numbers))
 return dict(parsed=parsed,value=value,relative_error=rel,exact=int(exact),relaxed=None if censored else relaxed,strict=None if censored else strict,censored=censored,format=.5 if re.match(r'<think>.*?</think>.*?<answer>.*?</answer>',text.strip(),re.S) else 0.,aux=.5 if re.findall(r'<auxiliary>.*?</auxiliary>',text.strip(),re.S) else 0.,length=.5*min(len(tok.encode(text)),900)/900,literal_fallback=fallback,answer_tags=len(tags))
def normalize(values):
 mean=statistics.mean(values);sd=statistics.stdev(values);return [(x-mean)/(sd+1e-9) for x in values]
def mask(with_values,without_values):
 d=statistics.mean(with_values)-statistics.mean(without_values)
 return 1 if d>=.05 else -1 if d<=-.05 else 0
def mask_bounds(w,b):
 def interval(xs):return (sum(x or 0 for x in xs)/8,(sum(x or 0 for x in xs)+sum(x is None for x in xs))/8)
 lo,hi=interval(w);bl,bh=interval(b);dlo,dhi=lo-bh,hi-bl
 return dict(difference_interval=[dlo,dhi],certain_mask=1 if dlo>=.05 else -1 if dhi<=-.05 else 0 if dlo>-.05 and dhi<.05 else None)
def analyze():
 from transformers import AutoTokenizer
 tok=AutoTokenizer.from_pretrained(json.loads((HERE/'model.json').read_text())['snapshot'],local_files_only=True)
 labels=json.loads((RUN/'labels.json').read_text());summary=[];scored=[];extension=[];eligible=[]
 for pid,key in labels.items():
  init=json.loads((RUN/'screen1024'/(pid+'-main.json')).read_text())
  if sum(r['finish_reason']!='stop' for r in init)>=4:extension.append(pid)
  stage='screen2048' if (RUN/'screen2048'/(pid+'-main.json')).exists() else 'screen1024';groups={}
  for name in ('without','with','main'):
   path=RUN/stage/(pid+'-'+name+'.json');rows=json.loads(path.read_text());ss=[dict(r,**score(r,key['answer_exact'],tok),source=str(path),source_sha256=sha(path)) for r in rows];groups[name]=ss
  w=[s['relaxed'] for s in groups['with']];b=[s['relaxed'] for s in groups['without']];bounds=mask_bounds(w,b);m=mask(w,b) if all(x is not None for x in w+b) else bounds['certain_mask']
  main=groups['main'];numeric=[s['relaxed'] for s in main];full=None
  if m is not None and all(x is not None for x in numeric):
   full=[s['relaxed']+s['format']+m*s['aux']+s['length'] for s in main]
   for r,A,R in zip(main,normalize(full),full,strict=True):r.update(advantage=A,total_reward=R)
  desc=dict(id=pid,stage=stage,mask=m,mask_bounds=bounds,groups={g:dict(rewards=[x['relaxed'] for x in ss],strict=[x['strict'] for x in ss],censored=sum(x['censored'] for x in ss),format_count=sum(x['format']>0 for x in ss),aux_count=sum(x['aux']>0 for x in ss),tokens=sum(len(x['completion_ids']) for x in ss),seconds=ss[0]['generation_seconds_group']) for g,ss in groups.items()},numeric_mixed=all(x is not None for x in numeric) and 0<sum(numeric)<8,full_mixed=full is not None and statistics.stdev(full)>0,main_natural=not any(x['censored'] for x in main),main_tokens=sum(len(x['completion_ids']) for x in main),numeric_sd=statistics.stdev(numeric) if all(x is not None for x in numeric) else None,full_sd=statistics.stdev(full) if full is not None else None)
  if full is not None and desc['full_mixed']:eligible.append(desc)
  summary.append(desc);scored.extend(x for ss in groups.values() for x in ss)
 preferred=[d for d in eligible if d['numeric_mixed']] or eligible
 selected=[]
 if preferred:
  selected=[min(preferred,key=lambda d:(d['main_tokens'],d['id'])),max(preferred,key=lambda d:(d['main_tokens'],d['id']))]
  selected=list({d['id']:d for d in selected}.values())
 for d in selected:write(RUN/('training-'+d['id']+'.json'),[r for r in scored if r['problem_id']==d['id'] and r['group']=='main'])
 write(RUN/'scores.json',scored);result=dict(groups=summary,extension_ids=extension,selected_updates=[d['id'] for d in selected],selection_kind='numeric_mixed' if any(d['numeric_mixed'] for d in preferred) else 'full_reward_only',completed_questions=len(summary));write(RUN/'signal-summary.json',result);return result
if __name__=='__main__':print(json.dumps(analyze(),indent=2))
