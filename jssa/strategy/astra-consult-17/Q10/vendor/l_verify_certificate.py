"""Independent exact sparse-polynomial checker, using Fraction only (no SymPy)."""
import json,sys
from fractions import Fraction
from pathlib import Path

def poly(a):return {tuple(m):Fraction(c) for m,c in a if Fraction(c)}
def add(a,b,k=1):
 r=a.copy()
 for m,c in b.items():
  r[m]=r.get(m,Fraction(0))+k*c
  if not r[m]:del r[m]
 return r

def mul(a,b):
 r={}
 for ma,ca in a.items():
  for mb,cb in b.items():
   m=tuple(x+y for x,y in zip(ma,mb));r[m]=r.get(m,Fraction(0))+ca*cb
 return {m:c for m,c in r.items() if c}

def verify(c):
 n=len(c['variables']);s=poly(c['s']);left=poly(c['Q'])
 for _ in range(c['N']):left=mul(left,s)
 right={}
 for a,b in zip(c['C'],c['F'],strict=True):right=add(right,mul(poly(a),poly(b)))
 return not add(left,right,-1)
if __name__=='__main__':
 result={p:verify(json.loads(Path(p).read_text())) for p in sys.argv[1:]}
 print(json.dumps(result));sys.exit(0 if all(result.values()) else 1)
