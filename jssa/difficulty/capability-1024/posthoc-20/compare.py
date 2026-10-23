"""Post-result bounded comparisons; never rewrites source data or converters."""
import os,sys,pathlib,json,hashlib,subprocess,resource,time,re,dataclasses
ROOT=pathlib.Path(__file__).resolve().parents[4]
OUT=pathlib.Path(__file__).resolve().parent
CLEAN=pathlib.Path('/tmp/posthoc20-clean')
CONV=pathlib.Path('/tmp/q6-tools/exact_comparison/benchmarks/exact_comparison')
os.environ.update(PATH='/tmp/q6-tools/bin:'+os.environ['PATH'],PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
sys.path[:0]=[str(CLEAN/'src'),str(CLEAN),str(CONV)]
import sympy as sp
from mpmath import mp
from algebraize import translate
from run_exact import build,poly_str,verifier_for
from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate
assert subprocess.check_output(['git','-C',str(CLEAN),'rev-parse','HEAD'],text=True).strip().startswith('60db4b6')
assert not subprocess.check_output(['git','-C',str(CLEAN),'status','--porcelain'],text=True).strip()
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
cases={c['id']:c for g in 'ab' for c in map(json.loads,(ROOT/f'jssa/difficulty/unseen-2/{g}/cases.jsonl').read_text().splitlines())}
def limits():
 resource.setrlimit(resource.RLIMIT_AS,(1536<<20,1536<<20));resource.setrlimit(resource.RLIMIT_CPU,(15,15))
def singular(cid,code):
 p=OUT/'evidence'/f'{cid}.sing';p.write_text(code)
 t=time.monotonic();load=os.getloadavg();cpu0=os.times()
 try:
  r=subprocess.run(['Singular','-q',str(p)],cwd=CLEAN,text=True,capture_output=True,timeout=20,preexec_fn=limits)
  log=r.stdout+r.stderr;rc=r.returncode
 except subprocess.TimeoutExpired as e:
  log=(e.stdout or b'').decode()+(e.stderr or b'').decode()+'\nTIMEOUT';rc='timeout'
 elapsed=time.monotonic()-t;cpu1=os.times()
 (OUT/'evidence'/f'{cid}.log').write_text(log)
 return {'id':cid,'returncode':rc,'wall_seconds':elapsed,'child_cpu_seconds':cpu1.children_user+cpu1.children_system-cpu0.children_user-cpu0.children_system,'load_start':load,'load_end':os.getloadavg(),'input_sha256':digest(p),'log':log}
def verify(cid,values):
 t=time.monotonic();bundle,ev=verifier_for(cases[cid])
 with mp.workdps(100):
  pt=tuple(mp.mpf(str(sp.N(sp.sympify(values[n]),95))) for n in bundle.var_names)
  r=verify_final_candidate(evaluator=ev,values=pt)
 out={'id':cid,'input_values':values,'var_names':bundle.var_names,'result':dataclasses.asdict(r),'wall_seconds':time.monotonic()-t}
 (OUT/'evidence'/f'{cid}.verification.json').write_text(json.dumps(out,default=str,ensure_ascii=False,indent=2)+'\n')
 print(cid,'verified',r.verified,'answer',r.answer_hp,flush=True)
 return out
if __name__=='__main__' and sys.argv[1]=='verify':
 # The eliminated equations allow x=-5,y=-sqrt(50/3); signs obey both DSL inequalities.
 verify('AIME-2012-I-14',dict(x='-5',y='-sqrt(50/3)',u='10',v='2*sqrt(50/3)'))
 verify('AIME-2005-I-01',dict(r='10',x1='10',y1='10*sqrt(3)',x2='-10',y2='10*sqrt(3)',x3='-20',y3='0',x4='-10',y4='-10*sqrt(3)',x5='10',y5='-10*sqrt(3)'))
 verify('HMMT-2011-FEB-GUTS-01',dict(b='2',x='0',y='1',u='1/3',v='1/3'))
 verify('HMMT-2023-FEB-GUTS-03',dict(d='4',a='sqrt(5)',cx='2',cy='-2'))
elif __name__=='__main__' and sys.argv[1]=='eliminate':
 results=[]
 for cid in ['AIME-2005-I-01','AIME-2012-I-14','HMMT-2011-FEB-GUTS-01','HMMT-2019-FEB-GUTS-17','HMMT-2023-FEB-GUTS-03']:
  t0=time.monotonic()
  if cid=='AIME-2005-I-01':
   lines=(pathlib.Path('/tmp/q6e1-run/raw/msolve')/cid/'in.ms').read_text().splitlines()
   names=lines[0].split(',');eq='\n'.join(lines[2:]).rstrip(',\n');target='T';others='*'.join(names)
   header=f'ring R=0,({",".join(names)},T),dp;\nideal I={eq},T-(900-6*x11^2);\n'
   extra='''LIB "elim.lib";
ideal J=I;
poly f;int i;int j;
list xs=30-x11,x12,x13,x14,x15,x16;
list ys=0,x17,x18,x19,x20,x21;
for(i=1;i<=6;i++){for(j=i+1;j<=6;j++){if(j-i!=1 && j-i!=5){f=(xs[i]-xs[j])^2+(ys[i]-ys[j])^2;J=sat(J,ideal(f));}}}
'''
  else:
   s,target_sym=translate(cases[cid]['dsl'],mode='fresh',with_target=True)
   eqs,used,_=build(s,True);ren={v:sp.Symbol(f'x{i}') for i,v in enumerate(used)}
   names=[str(ren[v]) for v in used];target=str(ren[target_sym]);others='*'.join(n for n in names if n!=target)
   header=f'ring R=0,({",".join(names)}),dp;\nideal I='+',\n'.join(poly_str(e.xreplace(ren)) for e in eqs)+';\n'
   extra='ideal J=I;\n'
   if cid=='HMMT-2019-FEB-GUTS-17':
    ss=str(ren[sp.Symbol('v_s')]);extra=f'LIB "elim.lib";\nideal J=sat(I,ideal({ss}));\n'
  code=header+extra+f'print("SAT_DONE");\nideal E=eliminate(J,{others});\nprint("ELIM_BEGIN");print(E);print("ELIM_END");\nquit;\n'
  prep=time.monotonic()-t0;r=singular(cid,code);r.update(target_variable=target,preparation_seconds=prep)
  m=re.search(r'ELIM_BEGIN\s*\n(.*?)ELIM_END',r['log'],re.S)
  if m:
   polys=[sp.sympify(v.strip().replace('^','**')) for v in m[1].strip().split(',')]
   r['elimination_polynomials']=[str(p) for p in polys]
   if any(p.free_symbols=={sp.Symbol(target)} for p in polys):
    p=next(p for p in polys if p.free_symbols=={sp.Symbol(target)})
    roots=sp.Poly(p,sp.Symbol(target)).real_roots();r['real_roots']=[str(x) for x in roots];r['real_roots_float']=[float(x.evalf()) for x in roots]
  results.append(r);(OUT/'comparison.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
  print(cid,r['returncode'],round(r['wall_seconds'],3),r.get('elimination_polynomials'),flush=True)
