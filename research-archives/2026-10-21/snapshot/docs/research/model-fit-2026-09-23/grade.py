"""Persist explicit manual judgements and export audit copies; no model feedback."""
import json
from pathlib import Path
D=Path(__file__).resolve().parent
R=Path('qwen/.runtime/model_fit_20260923_attempt04')
def save(entries):
 p=D/'grades.json'
 old=json.loads(p.read_text()) if p.exists() else {}
 for key,value in entries.items():
  if key in old:assert old[key]==value, 'Record adjudication separately; no silent overwrite'
  old[key]=value
 p.write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n')
def export():
 for model in ['original_4b','thinking_2507']:
  out=[]
  for p in sorted((R/model).glob('group-*.json')):
   for x in json.loads(p.read_text()):
    out.append('## '+x['id']+' / '+str(x['sample'])+'\n\n'+x['problem']+'\n\n'+x['final_text'].replace('<|im_end|>','')+'\n')
  (D/(model+'-answers.md')).write_text('\n'.join(out))
if __name__=='__main__':export()
