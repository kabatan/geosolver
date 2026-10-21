"""Export saved generations with manually audited mathematical grades."""
import hashlib,json
from pathlib import Path
D=Path(__file__).resolve().parent
R=Path('qwen/.runtime/foundation_pilot_20260923')
def save(entries):
 p=D/'grades.json'; grades=json.loads(p.read_text()) if p.exists() else {}
 for key,value in entries.items():
  if key in grades: assert grades[key]==value, 'Append adjudication instead of silently changing a grade: '+key
  grades[key]=value
 p.write_text(json.dumps(grades,ensure_ascii=False,indent=2)+'\n')
def export():
 grades=json.loads((D/'grades.json').read_text()) if (D/'grades.json').exists() else {}
 results=[];summaries={}
 for folder in sorted(R.iterdir()):
  if not folder.is_dir():continue
  if folder.name=='screen-r1_8b':continue  # Invalid input tokenization; retained with an exclusion record.
  stat=dict(n=0,graded=0,valid=0,core_or_repairable=0,truncated=0,tokens=0,synthetic_or_area_valid=0)
  md=[]
  for path in sorted(folder.glob('group-*.json')):
   for row in json.loads(path.read_text()):
    key=f"{folder.name}:{row['id']}:{row['sample']}";g=grades.get(key)
    stat['n']+=1;stat['truncated']+=row['finish_reason']=='length';stat['tokens']+=row['tokens']
    if g:
     stat['graded']+=1;stat['valid']+=g['valid'];stat['core_or_repairable']+=g['valid'] or g.get('repairable',False)
     stat['synthetic_or_area_valid']+=g['valid'] and g['method'] in ['synthetic','area']
    results.append(dict(key=key,source=str(path),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),id=row['id'],sample=row['sample'],phase=folder.name,tokens=row['tokens'],finish_reason=row['finish_reason'],final_text=row['final_text'],grade=g))
    final=row['final_text'] or '[No completed final answer; raw generation retained in the source JSON.]'
    md.append(f"## {row['id']} sample {row['sample']}\n\n{row['problem']}\n\nTokens: {row['tokens']}; finish: {row['finish_reason']}.\n\n{final}\n\nGrade: {json.dumps(g,ensure_ascii=False)}\n")
  if stat['n']:
   receipt=json.loads((folder/'receipt.json').read_text())
   stat['elapsed_seconds']=receipt.get('elapsed_seconds');stat['status']=receipt['status'];summaries[folder.name]=stat
   (D/(folder.name+'-answers.md')).write_text('\n'.join(md))
 (D/'graded-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
 (D/'summary.json').write_text(json.dumps(summaries,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(summaries,indent=2))
if __name__=='__main__':export()
