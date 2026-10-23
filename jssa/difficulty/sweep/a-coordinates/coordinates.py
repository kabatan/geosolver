"""Q43a: exact similarity changes of the geometric coordinate frame.

The scalar search parameters and answer units are retained. Every Point leaf
is mapped by s R (p-a)+t, radii by s, and measured lengths/areas back by s/s².
This is an explicit change of the geometric frame, not of the search box.
Only a statically checked, similarity-equivariant DSL subset is admitted.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[3]
SELECT_SEED = 431024
SEEDS = [431101, 431102]
EXPECTED = 'sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5'
FROZEN = '60db4b679b04167175c51c479c87c22fa663fda0'
EXTERNAL = Path('/tmp/q43a-coordinates-20261024')


def expr(s):
    return ast.parse(str(s), mode='eval').body


def fmt(n):
    return ast.unparse(ast.fix_missing_locations(n))


def digest(x):
    return hashlib.sha256(json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def variants():
    vs = [{'name': f'scale_{k:+d}', 's': str(10**k) if k >= 0 else f'1/{10**(-k)}', 'c': '1', 'q': '0', 't': ['0','0'], 'anchor': None, 'k': k}
          for k in range(-6, 7)]
    for name, c, q in [('rot90','0','1'), ('rot180','-1','0'), ('rot37','4/5','3/5')]:
        vs.append(dict(name=name,s='1',c=c,q=q,t=['0','0'],anchor=None))
    for n in (1, 1000, 1000000):
        vs.append(dict(name=f'translate_{n}',s='1',c='1',q='0',t=[str(n),str(-2*n)],anchor=None))
    for anchor in ('last_leaf', 'leaf_centroid'):
        vs.append(dict(name=anchor,s='1',c='1',q='0',t=['0','0'],anchor=anchor))
    vs.append(dict(name='identity_rewrite',s='1',c='1',q='0',t=['0','0'],anchor=None))
    return vs


class Unsupported(ValueError):
    pass


class Frame:
    SCALAR = {'sqrt','cos','sin','tan','acos','asin','atan','atan2','abs','min','max','Degrees','Bound','IsInteger','IsPrime'}
    POINTOPS = {'Midpoint','FootOfPerpendicular','Circumcenter','Orthocenter','Incenter','Centroid','IncircleContactPoint','Reflect'}
    LINEOPS = {'PerpendicularLine','ParallelLine','PerpendicularBisector','AngleBisector'}
    CIRCLEOPS = {'Circumcircle','Incircle','Excircle','CircleThroughThreePoints','CircleThroughPoint'}
    PREDICATES = {'ConvexPolygon','SimplePolygon','AcuteTriangle','RightTriangle','ObtuseTriangle','AssumeConvex','And','Or'}
    MEASURES = {'Distance':1,'Radius':1,'Length':1,'Perimeter':1,'Circumference':1,'Area':2,'OnCircle':1,'OnSegment':1,'Collinear':2,'AreConcyclic':1}

    def __init__(self, dsl, variant):
        self.dsl = dsl
        self.v = variant
        self.types = {n:'scalar' for n in dsl['variables']} | {'pi':'scalar','True':'scalar','False':'scalar'}
        self.leaves = []
        # Only raw scalar Point leaves: no geometric attributes or measurements.
        for item in dsl['constructions']:
            n=expr(item['expression'])
            for p in ast.walk(n):
                if isinstance(p,ast.Call) and isinstance(p.func,ast.Name) and p.func.id=='Point':
                    if len(p.args)!=2 or p.keywords: raise Unsupported('Point arity')
                    for a in p.args:
                        for sub in ast.walk(a):
                            if isinstance(sub,ast.Attribute): raise Unsupported('Point attribute')
                            if isinstance(sub,ast.Name) and sub.id not in set(dsl['variables'])|self.SCALAR|{'pi'}:
                                raise Unsupported('Point depends on construction')
                    self.leaves.append([fmt(a) for a in p.args])
        if not self.leaves: raise Unsupported('no raw point leaves')
        self.anchor = ['0','0']
        if variant['anchor']=='last_leaf': self.anchor=self.leaves[-1]
        if variant['anchor']=='leaf_centroid':
            self.anchor=[f'({"+".join("("+p[j]+")" for p in self.leaves)})/{len(self.leaves)}' for j in (0,1)]

    def visit(self,n):
        if isinstance(n,ast.Constant): return copy.deepcopy(n),'scalar'
        if isinstance(n,ast.Name):
            if n.id not in self.types: raise Unsupported(f'unknown name {n.id}')
            return copy.deepcopy(n),self.types[n.id]
        if isinstance(n,(ast.List,ast.Tuple)):
            items=[self.visit(a) for a in n.elts]
            return type(n)(elts=[a for a,t in items],ctx=ast.Load()),'list'
        if isinstance(n,ast.UnaryOp):
            a,t=self.visit(n.operand)
            if t!='scalar': raise Unsupported('non-scalar unary')
            return ast.UnaryOp(op=copy.deepcopy(n.op),operand=a),'scalar'
        if isinstance(n,ast.BinOp):
            a,t=self.visit(n.left);b,u=self.visit(n.right)
            if t!='scalar' or u!='scalar': raise Unsupported('non-scalar binary')
            return ast.BinOp(left=a,op=copy.deepcopy(n.op),right=b),'scalar'
        if not isinstance(n,ast.Call) or not isinstance(n.func,ast.Name):
            raise Unsupported(type(n).__name__)
        f=n.func.id
        aa=[self.visit(a) for a in n.args]; args=[a for a,t in aa]; types=[t for a,t in aa]
        kws=[ast.keyword(arg=k.arg,value=self.visit(k.value)[0]) for k in n.keywords]
        out=ast.Call(func=copy.deepcopy(n.func),args=args,keywords=kws)
        if f=='Point':
            if types!=['scalar','scalar']: raise Unsupported('Point inputs')
            x,y=map(fmt,args);a,b=self.anchor;v=self.v
            xx=f"({v['s']})*(({v['c']})*(({x})-({a}))-({v['q']})*(({y})-({b})))+({v['t'][0]})"
            yy=f"({v['s']})*(({v['q']})*(({x})-({a}))+({v['c']})*(({y})-({b})))+({v['t'][1]})"
            return expr(f'Point({xx},{yy})'),'point'
        if f=='Line':
            if types!=['point','point'] or kws: raise Unsupported('Line not through 2 points')
            return out,'line'
        if f=='Circle':
            if types!=['point','scalar'] or kws: raise Unsupported('Circle inputs')
            out.args[1]=expr(f"({self.v['s']})*({fmt(args[1])})")
            return out,'circle'
        if f=='Vector':
            if types!=['point','point']: raise Unsupported('Vector inputs')
            return out,'vector'
        if f=='Dot':
            if types!=['vector','vector']: raise Unsupported('Dot not vector-vector')
            return self.measure(out,2),'scalar'
        if f=='Intersect':
            if types!=['line','line'] or kws: raise Unsupported('nonunique/directional Intersect')
            return out,'point'
        if f=='PointOnSegment' or f=='PointOnLine':
            if types!=['point','point','scalar'] or kws: raise Unsupported(f'{f} inputs')
            return out,'point'
        if f in self.POINTOPS:
            if kws or any(t not in ('point','line','circle') for t in types): raise Unsupported(f'{f} args')
            return out,'point'
        if f in self.LINEOPS:
            if kws or any(t not in ('point','line') for t in types): raise Unsupported(f'{f} args')
            return out,'line'
        if f in self.CIRCLEOPS:
            if kws or any(t!='point' for t in types): raise Unsupported(f'{f} args')
            return out,'circle'
        if f in ('Segment','Polygon'): return out,'object'
        if f in ('Parallel','Perpendicular'):
            if types!=['line','line']: raise Unsupported(f'{f} inputs')
            return out,'scalar'
        if f=='Angle':
            if types not in (['point']*3,['line']*2): raise Unsupported('Angle input')
            return out,'scalar'
        if f=='OnLine':
            if kws: raise Unsupported('ordered OnLine')
            if types not in (['point','line'],['point']*3): raise Unsupported('OnLine inputs')
            power=1 if len(types)==2 else 2
            return self.measure(out,power),'scalar'
        if f in self.MEASURES:
            if f=='Distance' and len(args)!=2: raise Unsupported('origin-dependent Distance')
            if kws: raise Unsupported(f'{f} kwargs')
            return self.measure(out,self.MEASURES[f]),'scalar'
        if f in self.SCALAR or f in self.PREDICATES: return out,'scalar'
        raise Unsupported(f'operation {f}')

    def measure(self,out,power):
        if self.v['s']=='1': return out
        return expr(f"({fmt(out)})/(({self.v['s']})**{power})")

    def transform(self):
        d=copy.deepcopy(self.dsl)
        for item in d['constructions']:
            n,t=self.visit(expr(item['expression']));item['expression']=fmt(n);self.types[item['name']]=t
        for c in d['conditions']:
            for k in ('left','right','predicate'):
                if k in c: c[k]=fmt(self.visit(expr(c[k]))[0])
        d['target']=fmt(self.visit(expr(d['target']))[0])
        # Preserve a byte-exact baseline, but still validate it above.
        if self.v['name']=='scale_+0': d=copy.deepcopy(self.dsl)
        return d


def transform(dsl,variant):
    return Frame(dsl,variant).transform()


def universe():
    rows=[]
    for group,path in [('development','benchmarks/cases.jsonl'),('unseen2026','jssa/difficulty/new2026/cases.jsonl')]:
        for c in map(json.loads,(ROOT/path).read_text().splitlines()):
            reason=''
            try:
                if not 1<=len(c['dsl']['variables'])<=8: raise Unsupported('not 1..8 variables')
                transform(c['dsl'],variants()[0])
            except (Unsupported,KeyError,SyntaxError) as e: reason=str(e)
            rank=hashlib.sha256(f'{SELECT_SEED}|{group}|{c["id"]}'.encode()).hexdigest()
            rows.append(dict(group=group,source=path,id=c['id'],eligible=not reason,exclusion=reason,rank=rank,case=c))
    return rows
