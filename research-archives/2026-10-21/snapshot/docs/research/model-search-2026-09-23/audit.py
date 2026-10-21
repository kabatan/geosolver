import json,hashlib
from pathlib import Path
D=Path(__file__).resolve().parent
R=Path('qwen/.runtime/model_search_20260923_v2')
def save(entries):
 p=D/'grades.json';g=json.loads(p.read_text()) if p.exists() else {}
 for k,v in entries.items():
  if k in g:assert g[k]==v,'Use separate adjudication; never silently overwrite'
  g[k]=v
 p.write_text(json.dumps(g,ensure_ascii=False,indent=2)+'\n')
def export():
 g=json.loads((D/'grades.json').read_text()) if (D/'grades.json').exists() else {}
 summary={};allrows=[]
 for folder in sorted(R.iterdir()):
  if not folder.is_dir():continue
  out=[];stats={}
  for p in sorted(folder.glob('group-*.json')):
   for x in json.loads(p.read_text()):
    k=f"{folder.name}:{x['id']}:{x['sample']}";a=g.get(k)
    group=x['stratum'];s=stats.setdefault(group,{'n':0,'graded':0,'valid':0,'numeric_correct':0,'strong':0,'truncated':0,'tokens':0})
    s['n']+=1;s['tokens']+=x['tokens'];s['truncated']+=x['finish_reason']!='stop'
    if a:s['graded']+=1;s['valid']+=bool(a['valid']);s['numeric_correct']+=bool(a.get('numeric_correct'));s['strong']+=bool(a['valid'] and a['usefulness']=='strong')
    final=x['final_text']
    for tag in ['<|im_end|>','<|end|>','<|endoftext|>','<｜end▁of▁sentence｜>']:final=final.replace(tag,'')
    out.append(f"## {x['id']} / {x['sample']}\n\n"+x['problem']+'\n\n'+final+'\n')
    allrows.append({'key':k,'source':str(p),'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'id':x['id'],'model':x['model'],'sample':x['sample'],'stratum':group,'tokens':x['tokens'],'finish_reason':x['finish_reason'],'final_text':x['final_text'],'grade':a})
  if out:(D/(folder.name+'-answers.md')).write_text('\n'.join(out))
  if 'foundation' in stats:stats['foundation']['numeric_correct']=None
  summary[folder.name]={'results':stats,'receipt':json.loads((folder/'receipt.json').read_text()) if (folder/'receipt.json').exists() else None}
 (D/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
 (D/'graded-results.json').write_text(json.dumps(allrows,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:v['results'] for k,v in summary.items()},indent=2))
if __name__=='__main__':export()
