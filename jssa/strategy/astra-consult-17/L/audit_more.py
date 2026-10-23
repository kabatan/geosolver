"""Historical audit only. Old P/certificates never enter experiment.py."""
from pathlib import Path
import csv,json,subprocess,re,hashlib,sys
import sympy as sp
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE/'vendor'))
from certificate import isolate,target_bounds

def main():
 branch='origin/claude/project-thread-ulho54';prefix='jssa/theory/posdim-identities/out/'
 files=subprocess.check_output(['git','ls-tree','-r','--name-only',branch,prefix],text=True).splitlines()
 evidence=[]
 for f in files:
  if not f.endswith('/result.json'):continue
  cid=f.split('/')[-2];data=json.loads(subprocess.check_output(['git','show',branch+':'+f]))
  if not data.get('identity_check_sympy'):continue
  out=HERE/'audit_source/available_certificates'/cid;out.mkdir(parents=True,exist_ok=True)
  for name in ['result.json','system.txt','certificate.txt']:
   raw=subprocess.check_output(['git','show',branch+':'+prefix+cid+'/'+name]);assert len(raw)<2**20
   (out/name).write_bytes(raw)
  txt=(out/'system.txt').read_text();ct=(out/'certificate.txt').read_text()
  F={int(i):sp.sympify(v) for i,v in re.findall(r'^F(\d+) = (.*)$',txt,re.M)}
  C={int(i):sp.sympify(v) for i,v in re.findall(r'^C(\d+) = (.*)$',ct,re.M)}
  s=sp.sympify(re.search(r'^nondegeneracy s = (.*)$',txt,re.M)[1])
  qline=next(l for l in ct.splitlines() if l.startswith('# Q ='))
  Q=sp.sympify(qline.rsplit(' = ',1)[1]);N=int(data['N'])
  chk=sp.Poly(sp.expand(s**N*Q-sum(C[i]*F[i] for i in C)),*sorted(set().union(*[f.free_symbols for f in F.values()]),key=str)).is_zero
  evidence.append({'id':cid,'independent_recheck':chk,'N':N,'source_result_sha256':hashlib.sha256((out/'result.json').read_bytes()).hexdigest()})
 rows=list(csv.DictReader((HERE/'audit-24.csv').open()));old={r['id']:r for r in csv.DictReader((HERE/'audit_source/out/batch-summary.csv').open())}
 available={r['id'] for r in evidence}
 for r in rows:
  E=sp.sympify(old[r['id']]['elim']);t=next(iter(E.free_symbols));cs=list(map(sp.Rational,r['old_P'].split(',')));P=sum(c*t**(len(cs)-i-1) for i,c in enumerate(cs))
  d=json.loads((HERE/'inputs'/(r['id']+'.json')).read_text())['dsl'];root=isolate(E,t,target_bounds(d),P)
  r.update(P_is_factor_of_E=sp.rem(E,P,t)==0,input_range=str(root['range']),E_roots_in_input_range=root['allowed_root_count'],
   range_unique=root['unique'],raw_certificate_available=r['id'] in available,
   nondeg_origin='translator division/construction domains; no extra_nondeg in batch',
   direct_input='not independently verifiable: 246-ID audit absent; available comparison audit_A all blank')
 with (HERE/'audit-24.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 summary=json.loads((HERE/'audit-summary.json').read_text())
 summary.update(raw_available=len(evidence),raw_rechecked=sum(r['independent_recheck'] for r in evidence),
  range_unique=sum(r['range_unique'] for r in rows),range_unique_E=sum(r['range_unique'] and r['old_certificate']=='identity_E' for r in rows),
  low_p_and_range_unique=[r['id'] for r in rows if r['hard_p_le_0.1']=='True' and r['range_unique']],
  audit_direct_input_available=False)
 (HERE/'audit-summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
 (HERE/'old-certificate-recheck.json').write_text(json.dumps(evidence,indent=2)+'\n')
 print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
