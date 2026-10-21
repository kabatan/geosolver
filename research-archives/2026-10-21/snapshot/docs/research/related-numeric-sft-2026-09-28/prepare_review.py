"""Prepare arm-blinded full answers; private mapping remains outside packet."""
import argparse,hashlib,json,random
from pathlib import Path
P=Path(__file__).resolve().parent;R=P.parents[2];O=R/'qwen/.runtime/related_numeric_sft_20260928'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--kind',choices=['proof','numeric'],required=True);ap.add_argument('--label',default='final');ap.add_argument('--arms',nargs='+',choices=['base','sft-a','sft-b'],default=['base','sft-a','sft-b']);ap.add_argument('--exclude-jobs',nargs='*',default=[]);ap.add_argument('--include-jobs',nargs='*');ap.add_argument('--caps-file',type=Path);args=ap.parse_args()
 jobs=read(O/'main-jobs.json');cap_file=args.caps_file or O/'final-cap-by-job.json';caps=read(cap_file) if cap_file.exists() else {}
 entries=[]
 for arm in args.arms:
  for j in jobs:
   if j['id'] in args.exclude_jobs:continue
   if args.include_jobs is not None and j['id'] not in args.include_jobs:continue
   if (j['split']=='proof') != (args.kind=='proof'):continue
   if args.kind=='numeric' and j['split']!='untrained_configuration':continue
   cap=caps.get(j['id'],32768);suffix='' if cap==32768 else '-'+str(cap)
   f=O/f'{arm}-main{suffix}'/(j['id']+'-0.json')
   r=read(f)
   entries.append((arm,j,f,r,cap))
 random.Random(2026092809).shuffle(entries)
 dest=O/f'review-{args.kind}-{args.label}';dest.mkdir(exist_ok=False)
 index=[];private={}
 for i,(arm,j,f,r,cap) in enumerate(entries):
  cid=f'{args.kind}-{i:02d}';target=dest/(cid+'.md')
  text=f"# {cid}\n\n## Problem\n\n"+'\n\n'.join(m['content'] for m in j['messages'])+f"\n\n## Model answer (full, {r['finish_reason']}, {len(r['completion_ids'])} tokens)\n\n"+r['raw_text']+'\n'
  target.write_text(text)
  index.append({'case_id':cid,'file':str(target),'source_id':j['source_id'],'finish_reason':r['finish_reason'],'tokens':len(r['completion_ids']),'packet_sha256':sha(target)})
  private[cid]={'arm':arm,'job_id':j['id'],'source_id':j['source_id'],'file':str(f),'file_sha256':sha(f),'cap':cap}
 write(dest/'index.json',index);write(O/f'private-{args.kind}-{args.label}.json',private)
 print(dest,len(entries))
if __name__=='__main__':main()
