import json,hashlib
from pathlib import Path
D=Path(__file__).resolve().parent
old=json.loads(Path('docs/research/model-fit-2026-09-23/jobs.json').read_text())
text={
'B04':'Let M=(0,0), A=(a,b), and H=(u,v), where a^2+b^2>0. Derive the coordinates of the foot P of the perpendicular from H to the line MA. Do not assume that P lies on the segment MA. Give the necessary justification and a concise final solution.',
'B06':'A secant from a point S outside a circle meets the circle at U and V, in the order S,U,V. The tangent from S touches the circle at T. Given SU=4 and UV=5, find ST. Prove the product identity you use by similarity of triangles in this configuration, rather than merely citing the power-of-a-point theorem. Give the necessary justification and a concise final solution.',
'H01_unassisted':'Let ABC be an acute scalene triangle with orthocenter H, and let M be the midpoint of BC. Let P be the foot of the perpendicular from H to the line AM. Given BC=12 and AM=10, find AP.',
'DA03_unassisted':'Let O be the circumcenter of an acute scalene triangle ABC. The circle through A and C tangent to the line AB at A meets the circle through B,O,C again at T, other than C. Let K be the intersection of the lines TO and BC. The points K,B,C are collinear in that order. Given BC=32 and BK=49, find AK.',
'DA05_unassisted':'Let ABC be an acute scalene triangle with BC=12. Let omega1 be the circle through A tangent to the line BC at B, and omega2 the circle through C tangent to the line BA at B. The two circles meet again at D, other than B. Let M be the midpoint of BC, and E the intersection of the lines MD and AC. The points M,D,E lie in that order, and MD=4. Find DE.',
'DA15_unassisted':'Let O be the circumcenter of an acute scalene triangle ABC, and M the midpoint of BC. The perpendicular bisectors of AB and AC meet the ray AM at D and E, respectively. Let F be the intersection of BD and CE, and suppose F lies inside triangle ABC. Given AO=13 and AF=12, find OF.'}
append=r'''

Justify your answer from the definitions and given conditions. Prove the central relation in your solution; merely citing the name or properties of a special point is not sufficient. Coordinate solutions are allowed. Put the final numerical value in \boxed{...}.
Seek a geometrically or mathematically meaningful solution: identify and actually use a relation that simplifies the calculation or proof, a viewpoint that reduces the unknowns, or an argument that concisely explains why a property holds. Any method is allowed. Justify the relations you discover from the given conditions.'''
rows=[]
for x in old:
 if x['id'] in text:
  rows.append({**x,'problem':text[x['id']]+(append if x['stratum']=='unassisted' else ''),'language':'en','source_problem_ja':x['problem']})
p=D/'jobs.json';assert not p.exists();p.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
keys=['qwen35_4b','qwen35_9b','phi4_mini','mimo7b','nemotron9b','qwen3_2507_en']
protocol={'models':keys,'phase':'primary_screen','jobs_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'samples_per_job':2,'seed':2026092317,'dtype':'bfloat16','max_context':32768,'max_completion':32000,'temperature':.6,'top_p':.95,'top_k':-1,'system_prompt':'empty, except Nemotron /think mode control','official_chat_template':True,'hints':False,'training_eligible':False,'budget':'60 minutes watchdog per model; adapt only for documented startup incompatibility; top candidates get new-task confirmation','selection':'Require valid reasoning plus useful self-generated solutions, not numerical answer alone','limitations':['English translations change language from previous diagnostic; a 2507 English baseline is rerun','Each tokenizer differs: same token cap is a practical budget, not equal compute','Generic shared sampling is not separately optimized per model','6 selected development tasks; not a held-out transfer score','Model selector sees task results; later confirmation remains model-selection data','High usefulness calibrated against user: H01 projection and DA15 routine coordinate identity are weak only']}
(D/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
m=json.loads(Path('docs/research/model-fit-2026-09-23/protocol.json').read_text())['models']['thinking_2507']
(D/'qwen3_2507_en-model.json').write_text(json.dumps({'model_id':'Qwen/Qwen3-4B-Thinking-2507','revision':m['revision'],'snapshot':m['snapshot'],'status':'complete','cached':True},indent=2)+'\n')
