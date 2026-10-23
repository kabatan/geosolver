"""Independent checking of saved identities, input linkage, and rejection controls.

No new local searches. This program does not feed its findings back into any trial.
"""
from pathlib import Path
import json,sys,hashlib,copy,time
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE/'vendor'))
import sympy as sp
from mpmath import mp
from certificate import encode,sparse,Prover,isolate,target_bounds,deadline
from verify_certificate import verify

def save(p,d):p.write_text(json.dumps(d,indent=2,ensure_ascii=False,default=str)+'\n')

def main():
 t0=time.perf_counter();byid={};checks=[];systems={};trials=[]
 for p in sorted((HERE/'runs').glob('*/result.json')):
  r=json.loads(p.read_text());trials.append(r);cid=r['id']
  if cid not in byid:
   d=json.loads((HERE/'inputs'/(cid+'.json')).read_text())['dsl'];byid[cid]=(d,*encode(d))
  d,sy,t,fs,vs,nd=byid[cid]
  assert r['input_sha256']==hashlib.sha256((HERE/'inputs'/(cid+'.json')).read_bytes()).hexdigest()
  systems.setdefault(cid,set()).add(hashlib.sha256((p.parent/'system.json').read_bytes()).hexdigest())
  for q in sorted(p.parent.glob('certificate*.json')):
   c=json.loads(q.read_text());cv=[sp.Symbol(s) for s in c['variables']]
   ff=fs[:-1] if sp.Symbol('zz') in vs else fs
   same_F=c['F']==[sparse(e,cv) for e in ff]
   same_s=c['s']==sparse(sp.prod(nd) if sp.Symbol('zz') in vs else sp.Integer(1),cv)
   exact=verify(c)
   cc=copy.deepcopy(c);zero=[0]*len(cv)
   cc['Q'].append([zero,'1'])
   # Coalesce the tampered constant term so it actually changes the polynomial.
   coeff={}
   for mon,coef in cc['Q']:
    key=tuple(mon);coeff[key]=coeff.get(key,sp.Rational(0))+sp.Rational(coef)
   cc['Q']=[[list(m),str(v)] for m,v in coeff.items() if v]
   tampered_rejected=not verify(cc)
   assert same_F and same_s and exact and tampered_rejected,str(q)
   checks.append({'certificate':str(q.relative_to(HERE)),'same_original_F':same_F,'same_original_s':same_s,
                  'fraction_identity':exact,'tampered_identity_rejected':tampered_rejected,
                  'cofactor_terms':c['cofactor_terms'],'N':c['N']})
 controls=[]
 for cid in ['HMMT-2013-FEB-GEO-02','HMMT-2008-FEB-GEO-06','AIME-2013-I-03','HMMT-2022-FEB-GEO-01','AIME-2013-II-13']:
  r=next(r for r in trials if r['id']==cid and r['arm']=='C2' and r['seed']==4301)
  d,sy,t,fs,vs,nd=byid[cid];P=sp.sympify(r['certified_P']);wrong=sp.expand(P.subs(t,t-1))
  with deadline(45):
   pr=Prover(fs,vs)
   direct=pr.coefficients(wrong)
   reflection=sp.Poly(wrong*wrong.subs(t,-t),t).sqf_part().monic().as_expr()
   closed=pr.coefficients(reflection)
  controls.append({'id':cid,'kind':'shifted_P','wrong':str(wrong),'direct_member':direct is not None,'reflection_member':closed is not None,
                   'rejected':direct is None and closed is None})
  assert controls[-1]['rejected']
 # Sign reflection membership alone must not certify a negative claimed distance.
 cid='HMMT-2022-FEB-GEO-01';d,sy,t,fs,vs,nd=byid[cid]
 r=next(r for r in trials if r['id']==cid and r['arm']=='C2' and r['seed']==4301)
 P=sp.sympify(r['certified_P']);wrong=sp.expand(P.subs(t,-t));Q=sp.Poly(wrong*wrong.subs(t,-t),t).sqf_part().as_expr()
 with deadline(45):member=Prover(fs,vs).coefficients(Q) is not None
 roots=isolate(Q,t,target_bounds(d),wrong)
 controls.append({'id':cid,'kind':'negative_distance_candidate','Q_member':member,'root_check':roots,'rejected':not roots['unique']})
 assert member and not roots['unique']
 # No extra nonzero assumption is justified for this reducible toy input.
 x,y,t=sp.symbols('x y t');pr=Prover([x*y,t-x],[x,y,t]);rejected=pr.coefficients(t) is None
 controls.append({'kind':'unjustified_nondegeneracy','F':['x*y','t-x'],'claim':'t=0','missing_assumption':'y!=0','rejected':rejected})
 assert rejected
 multi=[r for r in trials if r['status']=='multiple_or_no_allowed_roots']
 assert multi
 controls.append({'kind':'real_multiple_roots_rejected','trials':[{'id':r['id'],'arm':r['arm'],'roots':r['root_check']['allowed_root_count']} for r in multi],
                   'rejected':all(r['root_check']['allowed_root_count']!=1 for r in multi)})
 # Real pipeline domain check at a zero denominator. Do not call a new optimizer.
 from geosolver import GeometryProblem
 from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
 from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
 from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
 d=byid['AIME-2013-I-03'][0];ev=build_ir_evaluator(load_problem_bundle(GeometryProblem.model_validate(d).engine_document()))
 with mp.workdps(100),high_precision_mode():
  xx=[mp.mpf(0)]*len(ev.bundle.var_names)
  a=ev.evaluate_answer_hp(xx,precision=100)
  h=ev.evaluate_hp_hard_feasibility(xx,precision=100,include_margins=False)
  invalid=a.answer_hp is None or not mp.isfinite(a.answer_hp)
 controls.append({'id':'AIME-2013-I-03','kind':'zero_denominator','answer':str(a.answer_hp),'hard_feasible':bool(h.hard_feasible),'rejected':invalid and not bool(h.hard_feasible)})
 assert controls[-1]['rejected']
 summary={'certificates_checked':len(checks),'all_exact_and_from_original_input':True,'unique_system_hash_per_problem':all(len(v)==1 for v in systems.values()),
          'problem_count':len(byid),'trial_count':len(trials),'wrong_P_controls':5,'negative_controls_all_passed':all(c['rejected'] for c in controls),'seconds':time.perf_counter()-t0}
 save(HERE/'certificate-validation.json',{'summary':summary,'checks':checks,'controls':controls})
 print(json.dumps(summary))
if __name__=='__main__':main()
