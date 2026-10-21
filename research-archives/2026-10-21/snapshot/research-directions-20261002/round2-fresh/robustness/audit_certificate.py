"""Independent Decimal(70-digit, directed rounding) checks of the tightest boxes.
Audits supplied dyadic centers/radii; does not claim a complete replay of all cells.
"""
import json,sys,time,hashlib
from pathlib import Path
from decimal import Decimal,localcontext,ROUND_FLOOR,ROUND_CEILING,getcontext
import numpy as np
OUT=Path(__file__).resolve().parent
BENCH=OUT.parents[2]/'benchmarks/local-evaluation/research-directions-20261002/round2-kinematic'
# OUT is round2-fresh/robustness; repository is three levels up.
BENCH=OUT.parents[2]/'benchmarks/local-evaluation/research-directions-20261002/round2-kinematic'
sys.path.insert(0,str(BENCH))
import certify_rational_boxes as cert
v=cert.v
getcontext().prec=250
ZERO=Decimal(0);ONE=Decimal(1)
def D(x):return Decimal.from_float(float(x))
def interval(x):d=D(x);return d,d
def rounded(fn,rounding):
 with localcontext() as c:c.prec=70;c.rounding=rounding;return fn()
def add(a,b):return rounded(lambda:a[0]+b[0],ROUND_FLOOR),rounded(lambda:a[1]+b[1],ROUND_CEILING)
def neg(a):return -a[1],-a[0]
def sub(a,b):return add(a,neg(b))
def scale(c,a):
 if c<0:return neg(scale(-c,a))
 return rounded(lambda:c*a[0],ROUND_FLOOR),rounded(lambda:c*a[1],ROUND_CEILING)
def divpos(a,d):return rounded(lambda:a[0]/d,ROUND_FLOOR),rounded(lambda:a[1]/d,ROUND_CEILING)
def square(a):
 lo=ZERO if a[0]<=0<=a[1] else rounded(lambda:min(a[0]*a[0],a[1]*a[1]),ROUND_FLOOR)
 hi=rounded(lambda:max(a[0]*a[0],a[1]*a[1]),ROUND_CEILING);return lo,hi
def absup(a):return max(abs(a[0]),abs(a[1]))
def psum(terms):
 with localcontext() as c:c.prec=70;c.rounding=ROUND_CEILING;return sum(terms,ZERO)
def product(a,b):return rounded(lambda:a*b,ROUND_CEILING)
def quotient(a,b):return rounded(lambda:a/b,ROUND_CEILING)
def mat_interval(C,F):return [suminterval([scale(D(c),f) for c,f in zip(row,F)]) for row in C]
def suminterval(values):
 out=(ZERO,ZERO)
 for x in values:out=add(out,x)
 return out

def residual(X,w,wrad,delta):
 pts=[[interval(q) for q in row] for row in np.r_[X,v.fixed]];L=[D(x) for x in v.L0];a=[D(x) for x in v.alpha0];de=D(delta);r=[]
 for i,(aa,bb,_) in enumerate(v.BASE_LEN):
  d=[sub(x,y) for x,y in zip(pts[v.ix[aa]],pts[v.ix[bb]])];norm=add(square(d[0]),square(d[1]));length=scale(L[i],(ONE-de,ONE+de));r.append(divpos(sub(norm,square(length)),2*L[i]))
 for i,(dd,uu,tt,_) in enumerate(v.LINEARS):
  for xy in range(2):
   diff=sub(pts[v.ix[uu]][xy],pts[v.ix[tt]][xy]);nom=add(sub(pts[v.ix[dd]][xy],pts[v.ix[uu]][xy]),scale(a[i],diff));e=scale(a[i]*de,(-absup(diff),absup(diff)));r.append(add(nom,e))
 for xy,ww in enumerate([w.real,w.imag]):
  wi=sub(interval(ww),(-D(wrad[xy]),D(wrad[xy])));target=divpos(scale(D(v.src.K),wi),Decimal(3));r.append(sub(pts[v.ix['D1']][xy],target))
 return r

def nominal_jacobian(X):
 pts=[[interval(q) for q in row] for row in np.r_[X,v.fixed]];J=[{} for _ in range(36)]
 for i,(aa,bb,_) in enumerate(v.BASE_LEN):
  d=[divpos(sub(x,y),D(v.L0[i])) for x,y in zip(pts[v.ix[aa]],pts[v.ix[bb]])]
  for name,sign in [(aa,1),(bb,-1)]:
   if v.ix[name]<v.N:
    for xy in range(2):J[i][2*v.ix[name]+xy]=d[xy] if sign==1 else neg(d[xy])
 for i,(dd,uu,tt,_) in enumerate(v.LINEARS):
  for xy in range(2):
   row=26+2*i+xy;J[row][2*v.ix[dd]+xy]=(ONE,ONE);J[row][2*v.ix[uu]+xy]=sub(interval(v.alpha0[i]),(ONE,ONE));J[row][2*v.ix[tt]+xy]=neg(interval(v.alpha0[i]))
 J[-2][2*v.ix['D1']]=(ONE,ONE);J[-1][2*v.ix['D1']+1]=(ONE,ONE);return J

def prepare(X):
 _,Jfloat=v.rows(X[None],v.src.W0,v.L0,v.alpha0);C=np.linalg.inv(Jfloat[0]);J=nominal_jacobian(X);AC=[[abs(D(c)) for c in row] for row in C];defect=[]
 for i in range(36):
  row=[(ONE,ONE) if i==j else (ZERO,ZERO) for j in range(36)]
  for k in range(36):
   c=D(C[i,k])
   for j,value in J[k].items():row[j]=sub(row[j],scale(c,value))
  defect.append([absup(x) for x in row])
 return C,AC,defect

def derivative_radius(R,delta,W=None):
 rr=[D(x) for x in R]+[ZERO]*6;ww=rr if W is None else [D(x) for x in W]+[ZERO]*6;result=[]
 for i,(aa,bb,_) in enumerate(v.BASE_LEN):
  terms=[]
  for xy in range(2):
   dr=psum([rr[2*v.ix[aa]+xy],rr[2*v.ix[bb]+xy]]);dw=psum([ww[2*v.ix[aa]+xy],ww[2*v.ix[bb]+xy]]);terms.append(product(dr,dw))
  result.append(quotient(psum(terms),D(v.L0[i])*(2 if W is None else 1)))
 for i,(dd,uu,tt,_) in enumerate(v.LINEARS):
  for xy in range(2):result.append(product(product(D(v.alpha0[i]),D(delta)),psum([ww[2*v.ix[uu]+xy],ww[2*v.ix[tt]+xy]])))
 return result+[ZERO,ZERO]

def numerators(AC,defect,rem,W):
 wd=[D(w) for w in W]
 return [psum([product(a,b) for a,b in zip(ar,rem)]+[product(a,b) for a,b in zip(dr,wd)]) for ar,dr in zip(AC,defect)]
def check(X,r,w,wrad,delta,R=None):
 C,AC,defect=prepare(X)
 contraction=numerators(AC,defect,derivative_radius(r if R is None else R,delta,r),r)
 ans={'contraction':max(quotient(a,D(b)) for a,b in zip(contraction,r))}
 if R is None:
  base=[absup(x) for x in mat_interval(C,residual(X,w,wrad,delta))];terms=numerators(AC,defect,derivative_radius(r,delta),r);ans['inclusion']=max(quotient(psum([a,b]),D(c)) for a,b,c in zip(base,terms,r))
 return {k:str(vv) for k,vv in ans.items()}

def approx_metrics(rec,j):
 X=np.array(rec['centers'][j]);r=np.array(rec['radii'][j]);a=complex(*rec['control_start']);b=complex(*rec['control_end']);w=(a+b)/2;wrad=cert.up(np.maximum(abs(np.array([a.real,a.imag])-np.array([w.real,w.imag])),abs(np.array([b.real,b.imag])-np.array([w.real,w.imag]))));C,AC,defect=cert.prepare(X);base=cert.mag(cert.dot(C,cert.residual_interval(X,w,wrad,1e-5)));terms=cert.up(base+cert.up(cert.posdot(AC,cert.nonlinear(r,1e-5))+cert.posdot(defect,r)));inc=max(cert.div(cert.exact(terms),cert.exact(r))[1]);return float(inc),X,r,w,wrad

def main():
 start=time.monotonic();records=json.loads((BENCH/'rational_box_cells.json').read_text());rank=[]
 for i,rec in enumerate(records):
  for j in range(3):rank.append((approx_metrics(rec,j)[0],i,j))
 rank.sort(reverse=True);out={'scope':'Independent Decimal70 directed-rounding check of 12 tightest inclusion cells and 12 corresponding preceding unions; not a second complete path proof','delta':1e-5,'root_source_sha256':hashlib.sha256((BENCH/'certify_rational_boxes.py').read_bytes()).hexdigest(),'cells_sha256':hashlib.sha256((BENCH/'rational_box_cells.json').read_bytes()).hexdigest(),'checks':[]}
 for _,i,j in rank[:12]:
  rec=records[i];inc,X,r,w,wrad=approx_metrics(rec,j);ans=check(X,r,w,wrad,1e-5);item={'loop':rec['loop'],'segment':rec['segment'],'state':j,'binary64_inclusion_bound':inc,'decimal70':ans}
  if i>0 and records[i-1]['loop']==rec['loop']:
   prev=records[i-1];_,px,pr,pw,prad=approx_metrics(prev,j);disp=cert.mag(cert.sub(cert.exact(X.ravel()),cert.exact(px.ravel())));R=np.maximum(pr,cert.up(disp+r));item['previous_union_decimal70']=check(px,pr,pw,prad,1e-5,R)
  out['checks'].append(item);print(item,flush=True)
 X,err,okay=v.newton(v.init(),v.src.W0,v.L0,v.alpha0);assert okay
 homes=[cert.certify_cell(x,v.src.W0,np.zeros(2),1e-5) for x in X]
 out['home_checks']=[check(h['X'],h['r'],v.src.W0,np.zeros(2),1e-5) for h in homes]
 out['home_disjoint_exact_decimal_margins']=[]
 for i in range(3):
  for j in range(i):
   margin=max(abs(D(a)-D(b))-D(c)-D(d) for a,b,c,d in zip(homes[i]['X'].ravel(),homes[j]['X'].ravel(),homes[i]['r'],homes[j]['r']))
   out['home_disjoint_exact_decimal_margins'].append({'i':i,'j':j,'margin':str(margin)})
 out['endpoint_gluing']=[]
 for name,perm in [('A',[1,0,2]),('B',[0,2,1])]:
  recs=[rec for rec in records if rec['loop']==name]
  for j in range(3):
   for label,rec,h,homefirst in [('start',recs[0],homes[j],True),('end',recs[-1],homes[perm[j]],False)]:
    _,cx,cr,cw,crad=approx_metrics(rec,j)
    if homefirst:px,pr,pw,prad,tx,tr=h['X'],h['r'],v.src.W0,np.zeros(2),cx,cr
    else:px,pr,pw,prad,tx,tr=cx,cr,cw,crad,h['X'],h['r']
    disp=cert.mag(cert.sub(cert.exact(tx.ravel()),cert.exact(px.ravel())));R=np.maximum(pr,cert.up(disp+tr))
    out['endpoint_gluing'].append({'loop':name,'state':j,'end':label,'decimal70':check(px,pr,pw,prad,1e-5,R)})
 out['seconds']=time.monotonic()-start;(OUT/'certificate_audit.json').write_text(json.dumps(out,indent=2))
if __name__=='__main__':main()
