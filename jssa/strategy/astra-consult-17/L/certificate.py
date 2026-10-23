"""Answer-free exact identity generator; no geometry-specific formula or polynomial."""
import ast,time,signal
from contextlib import contextmanager
import sympy as sp
from sympy.polys.distributedmodules import sdm_nf_buchberger
from algebraize import translate
from run_exact import build

class Limit(Exception):pass
@contextmanager
def deadline(seconds):
 def alarm(*_):raise Limit('stage timeout')
 old=signal.signal(signal.SIGALRM,alarm)
 signal.setitimer(signal.ITIMER_REAL,seconds)
 try:yield
 finally:
  signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old)

def primitive(p,t):
 return sp.Poly(p,t,domain=sp.QQ).clear_denoms()[1].primitive()[1].monic().as_expr()

def encode(dsl):
 sy,t=translate(dsl,mode='fresh',with_target=True)
 fs,vs,nd=build(sy,True)
 return sy,t,fs,vs,nd

class Prover:
 def __init__(self,fs,vs,order="grevlex"):
  self.fs=fs;self.vs=vs
  self.ring=sp.QQ.old_poly_ring(*vs,order=order)
  self.module=self.ring.ideal(*fs)._module
  self.gb,self.gbc=self.module._groebner(extended=True)
 def coefficients(self,q):
  R=self.ring;M=self.module
  form=R._vector_to_sdm([R.from_sympy(q)],M.order)
  nf,comb=sdm_nf_buchberger(form,self.gb,M.order,R.dom,phantom=([],self.gbc))
  if nf:return None
  return [-R.to_sympy(c) for c in R._sdm_to_vector(comb,len(self.fs))]

def sparse(expr,vs):
 p=sp.Poly(expr,*vs,domain=sp.QQ)
 return [[list(m),str(c)] for m,c in p.terms() if c]

def make_certificate(fs,vs,nd,q,cofs):
 z=sp.Symbol('zz');hasz=z in vs;s=sp.prod(nd) if hasz else sp.Integer(1)
 N=max([sp.degree(c,z) if c!=0 else 0 for c in cofs]+[0]) if hasz else 0
 N=int(N);outvars=[v for v in vs if v!=z]
 new=[]
 for c in (cofs[:-1] if hasz else cofs):
  if hasz:
   c=sum(coef*s**(N-mono[0]) for mono,coef in sp.Poly(c,z).terms())
  new.append(sp.expand(c))
 original=fs[:-1] if hasz else fs
 # independent verifier reads only these polynomial arrays, never a Groebner basis.
 return {'variables':list(map(str,outvars)),'N':N,'s':sparse(s,outvars),
  'Q':sparse(q,outvars),'F':[sparse(f,outvars) for f in original],
  'C':[sparse(c,outvars) for c in new], 'Q_expression':str(q),
  'nondeg_factors':list(map(str,nd)), 'cofactor_terms':sum(len(sparse(c,outvars)) for c in new)}

def target_bounds(dsl):
 defs={c['name']:c['expression'] for c in dsl['constructions']}
 def nonneg(node,seen=()):
  if isinstance(node,ast.Constant):return isinstance(node.value,(int,float)) and node.value>=0
  if isinstance(node,ast.Name) and node.id in defs and node.id not in seen:return nonneg(ast.parse(defs[node.id],mode='eval').body,seen+(node.id,))
  if isinstance(node,ast.Call) and isinstance(node.func,ast.Name):return node.func.id in ['Distance','Length','Area','abs','sqrt','Radius','Perimeter']
  if isinstance(node,ast.BinOp):
   if isinstance(node.op,(ast.Add,ast.Mult,ast.Div)):return nonneg(node.left,seen) and nonneg(node.right,seen)
   if isinstance(node.op,ast.Pow) and isinstance(node.right,ast.Constant):return isinstance(node.right.value,int) and node.right.value%2==0
  return False
 lo=sp.Integer(0) if nonneg(ast.parse(dsl['target'],mode='eval').body) else -sp.oo
 hi=sp.oo;lo_open=False;hi_open=False
 norm=lambda s:ast.dump(ast.parse(str(s),mode='eval').body)
 for c in dsl['conditions']:
  if c.get('operator') not in ['>','>=','<','<=']:continue
  if norm(c['left'])!=norm(dsl['target']):continue
  try:b=sp.sympify(str(c['right']))
  except Exception:continue
  if not b.is_Rational:continue
  op=c['operator']
  if op.startswith('>') and b>=lo:
   lo=b;lo_open=op=='>'
  if op.startswith('<') and b<=hi:
   hi=b;hi_open=op=='<'
 return lo,hi,lo_open,hi_open

def isolate(q,t,bounds,p=None):
 lo,hi,lop,hip=bounds
 sq=sp.Poly(q,t,domain=sp.QQ).sqf_part()
 intervals=sq.intervals(eps=sp.Rational(1,10**30))
 allowed=[]
 # count_roots is exact; endpoints are rational or infinite.
 total=int(sq.count_roots(lo,hi))
 if lop and lo.is_finite and sq.eval(lo)==0:total-=1
 if hip and hi.is_finite and sq.eval(hi)==0:total-=1
 common=sp.gcd(sq,sp.Poly(p,t)) if p is not None else sq
 common_n=int(common.count_roots(lo,hi)) if common.degree()>0 else 0
 if lop and lo.is_finite and common.eval(lo)==0:common_n-=1
 if hip and hi.is_finite and common.eval(hi)==0:common_n-=1
 for (a,b),m in intervals:
  if b<lo or a>hi or (lop and b==lo) or (hip and a==hi):continue
  allowed.append([str(a),str(b)])
 return {'range':[str(lo),str(hi),lop,hip],'real_root_intervals':[[str(a),str(b)] for (a,b),m in intervals],
         'allowed_intervals':allowed,'allowed_root_count':total,'candidate_root_count':common_n,
         'unique':total==1 and common_n==1}
