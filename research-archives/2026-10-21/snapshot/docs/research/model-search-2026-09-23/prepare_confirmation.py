import json,hashlib
from pathlib import Path
D=Path(__file__).resolve().parent
base=json.loads((D/'jobs.json').read_text())
append=next(x['problem'].split('\n\n',1)[1] for x in base if x['stratum']=='unassisted')
def row(i,p,a,stratum='unassisted'):
 return {'id':i,'problem':p+ ('\n\n'+append if stratum=='unassisted' else '\nGive a complete, concise proof.'),'reference':a,'stratum':stratum,'language':'en','training_eligible':False,'phase':'confirmation'}
rows=[
row('C01','In a nondegenerate triangle ABC, the internal bisector of angle BAC meets BC at D. Prove DB/DC=AB/AC using triangle areas, without citing the angle-bisector theorem.','DB/DC=AB/AC','foundation'),
row('C02','Two distinct circles with distinct centers O1 and O2 meet at distinct points A and B. Prove that line AB is perpendicular to line O1O2. Explain why your argument applies even when one circle center lies outside the other circle.','AB perpendicular O1O2','foundation'),
row('H04_new','Let ABC be an acute scalene triangle with orthocenter H, and let M be the midpoint of BC. Let P be the foot of the perpendicular from H to the line AM. The perpendicular bisector of AP meets the line BC at T. The points T,B,C are collinear in that order, with BT=2 and BC=6. Find AT.','4'),
row('DA06_new','Let ABC be an acute scalene triangle with AB>AC. Let O be its circumcenter and M the midpoint of BC. The circle omega1 passes through A and B and is tangent to the line AC at A. The circle omega2 passes through A and C and is tangent to the line AB at A. These circles meet again at D, other than A. The line AM meets omega2 again at E, other than A. Given AO=5 and AD=4, find OE.','3'),
row('DB02_new','Let ABC be a triangle with AB=7, AC=11, BC=12. Points P,Q in the interior of side BC satisfy angle PAB=angle BCA and angle CAQ=angle ABC. On rays AP and AQ choose M and N, respectively, such that P is the midpoint of AM and Q is the midpoint of AN. Let X be the intersection of the lines BM and CN. Find BX.','6'),
row('DA15_variant','Let O be the circumcenter of an acute scalene triangle ABC, and M the midpoint of BC. The perpendicular bisectors of AB and AC meet the ray AM at D and E, respectively. Let F be the intersection of BD and CE, and suppose F lies inside triangle ABC. Given AO=13 and AF=11, find OF.','4*sqrt(3)')]
p=D/'confirmation-jobs.json';assert not p.exists();p.write_text(json.dumps(rows,indent=2)+'\n')
(D/'confirmation-protocol.json').write_text(json.dumps({'jobs_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'frozen_before_primary_target_results':True,'selection':'Up to three candidates with the best mix of complete target proofs, usefulness, basic-proof reliability and local learning feasibility. Do not certify a model if no candidate qualifies.','samples_per_job':2,'training_eligible':False,'same_sampling_as_primary':True,'DA15_variant':'Same layout with changed numbers; NOT a new independent configuration','new_layout_ids':['H04_new','DA06_new','DB02_new'],'limitations':'All confirmation tasks are development/model-selection data, never a held-out learning-transfer result.'},indent=2)+'\n')
