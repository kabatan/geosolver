"""Freeze a diagnostic-only suite; none of these outputs is training data."""
import json, hashlib
from pathlib import Path
from datetime import datetime, timezone
D=Path(__file__).resolve().parent
old=Path('/home/kabatan/.cache/huggingface/hub/models--Qwen--Qwen3-4B/snapshots/1cfa9a7208912126459214e8b04321603b3df60c')
new=Path('/home/kabatan/.cache/huggingface/hub/models--Qwen--Qwen3-4B-Thinking-2507/snapshots/768f209d9ea81521153ed38c47d515654e938aea')
foundation=[
('B01','点T,B,Cはこの順に一直線上にあり、TB=2、BC=6である。B=(0,0)、C=(6,0)と置いたときのTの座標とTCを求め、位置関係の理由を説明せよ。','T=(-2,0); TC=8','order'),
('B02','円ωの外部の点Mからの接線の接点をBとし、MB=6とする。Mから出る半直線は円とD,Pの順に交わり、MD=4である。DPを求め、使った関係と理由を説明せよ。','5','power_application'),
('B03','鋭角三角形ABCにおいて、BからACへの垂線の足をE、CからABへの垂線の足をFとする。B,C,E,Fが同一円周上にあることを証明し、その円の中心を特定せよ。','midpoint BC; diameter BC','cyclicity'),
('B04','M=(0,0)、A=(a,b)、H=(u,v)とし、a²+b²>0とする。Hから直線MAに下ろした垂線の足Pの座標をa,b,u,vで表し、その式を導け。Pが線分MA上にあるとは仮定しないこと。','P=((au+bv)/(a²+b²))(a,b)','projection'),
('B05','円ω: x²+y²-6x-8y=0と直線y=xの交点のうち、原点でないものを求めよ。また原点におけるωの接線の方程式を求め、両方について理由を説明せよ。','(7,7); 3x+4y=0','circle_algebra'),
('B06','円の外部の点Sを通る割線がS,U,Vの順に円と交わる。Sから円への接線の接点をTとし、SU=4、UV=5とする。STを求めよ。その際、方べきの定理を単に引用するだけでなく、この配置の三角形の相似から必要な積の等式を証明せよ。','6; ST²=SU SV via triangles STU and SVT','similarity_proof'),
]
jobs=[{'id':i,'stratum':'foundation','problem':p+'\n必要な根拠を示し、簡潔な最終答案を書いてください。','reference':a,'skill':s,'training_eligible':False} for i,p,a,s in foundation]
source=json.loads((D.parent/'initial-exploration-2026-09-23/meaningful-jobs.json').read_text())
hints={'H01':'AM·AP=AM²-MB²','DA03':'AKは三角形ABCの外接円のAにおける接線である','DA05':'Eは円ω1上にある','DA15':'AFはOFに垂直である'}
for condition in ['unassisted','relation_hint']:
 for r in source:
  if r['id'] not in hints:continue
  p=r['problem']
  if condition=='relation_hint':p+='\n\n診断用の手掛かりとして、次の関係に着目してください：'+hints[r['id']]+'。この関係を与条件として仮定せず、問題の定義と与条件から証明したうえで使ってください。'
  jobs.append({'id':r['id']+'_'+condition,'source_id':r['id'],'stratum':condition,'problem':p,'reference':r['answer_exact'],'training_eligible':False})
(D/'jobs.json').write_text(json.dumps(jobs,ensure_ascii=False,indent=2)+'\n')
models={}
for key,p in [('original_4b',old),('thinking_2507',new)]:
 index=json.loads((p/'model.safetensors.index.json').read_text())
 weights=sorted(set(index['weight_map'].values()))
 assert all((p/w).is_file() for w in weights)
 models[key]={'snapshot':str(p),'revision':p.name,'files':{f.name:{'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in p.iterdir() if f.is_file() and f.suffix=='.json'},'weight_files':{w:{'bytes':(p/w).stat().st_size,'blob':str((p/w).resolve())} for w in weights}}
protocol={'frozen_utc':datetime.now(timezone.utc).isoformat(),'question':'Elementary skill versus target relation discovery/proof; select learner, not teacher','models':models,'jobs_sha256':hashlib.sha256((D/'jobs.json').read_bytes()).hexdigest(),'samples_per_job':2,'job_count':len(jobs),'max_worker_seconds_total':5400,'updates':0,'training_eligible':False,'sampling':{'temperature':.6,'top_p':.95,'top_k':20,'max_context':32768,'max_completion':32512,'seed':2026092304},'judgement':'Manual final-proof validity, not final-value-only. Weak H01 does not receive strong usefulness. Hints diagnostic only, excluded from any training or transfer claim. All 56 outputs quarantined. Two samples per item are screening, not confidence of ability absence.','limitations':['Small hand-selected suite, elementary items easier than target composition','Target tasks selected after earlier failures','32k output budget is lower than 2507 official competition benchmark setting; truncation reported','Generic system prompt and per-model official chat template; no conversational memory','No human/strong-model hint in unassisted conditions; human relation statements only in diagnostic hint conditions','No held-out proof evaluation used']}
(D/'protocol.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2)+'\n')
print('Frozen',len(jobs),'jobs x 2 samples x 2 models =',len(jobs)*4,'answers')
