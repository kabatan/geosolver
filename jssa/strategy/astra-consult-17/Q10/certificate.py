"""Q10 common encoding; exact algebra engine snapshotted from read-only L."""
from pathlib import Path
import sys,ast,copy,signal,time
from contextlib import contextmanager
sys.path.insert(0,str(Path(__file__).resolve().parent/'vendor'))
import sympy as sp
from l_certificate import Prover,make_certificate,primitive,isolate,Limit
from l_certificate import target_bounds as base_bounds
from algebraize import Translator,AngleLin
from run_exact import build

@contextmanager
def deadline(seconds):
    if seconds<=0:raise Limit('budget exhausted')
    def alarm(*_):raise Limit('time budget')
    old=signal.signal(signal.SIGALRM,alarm)
    old_timer=signal.getitimer(signal.ITIMER_REAL);start=time.monotonic()
    signal.setitimer(signal.ITIMER_REAL,min(seconds,old_timer[0]) if old_timer[0]>0 else seconds)
    try:yield
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old)
        if old_timer[0]>0:signal.setitimer(signal.ITIMER_REAL,max(1e-6,old_timer[0]-(time.monotonic()-start)),old_timer[1])

def encode(dsl):
    tr=Translator(dsl,mode='fresh');sy,t=tr.run(with_target=True)
    audit=[]
    for c in dsl['conditions']:
        if c.get('operator') not in ['!=','>','<']:continue
        original=copy.deepcopy(tr)
        try:
            delta=tr.ev(str(c['left']))-tr.ev(str(c['right']))
            if isinstance(delta,AngleLin):raise ValueError('angle comparison')
            delta=sp.together(tr.sys.materialize(delta))
            num,den=sp.fraction(delta)
            for p in [num,den]:
                if p.has(sp.pi) or not p.is_polynomial():raise ValueError('nonrational scalar condition')
                if p.free_symbols and sp.Poly(p,*sorted(p.free_symbols,key=str)).domain!=sp.ZZ and sp.Poly(p,*sorted(p.free_symbols,key=str)).domain!=sp.QQ:
                    raise ValueError('nonrational coefficients')
            tr.sys.add_nondeg(num);tr.sys.add_nondeg(den)
            audit.append({'condition':c,'nonzero':str(num),'status':'included'})
        except Exception as e:
            tr=original
            audit.append({'condition':c,'status':'not_encoded','reason':type(e).__name__+': '+str(e)[:150]})
    sy=tr.sys;sy.q10_nondeg_audit=audit
    fs,vs,nd=build(sy,True)
    return sy,t,fs,vs,nd

def target_bounds(dsl):
    lo,hi,lop,hip=base_bounds(dsl)
    node=ast.parse(dsl['target'],mode='eval').body
    if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in ['cos','sin']:
        if lo<-1:lo=sp.Integer(-1);lop=False
        if hi>1:hi=sp.Integer(1);hip=False
    return lo,hi,lop,hip
