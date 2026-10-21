"""60-digit independent reconstruction from input points, not theorem labels.

This implementation does not import the double-precision data generator.
Only the root input points A/B/C (or A/B/M) are reused. All other points and
measurements are reconstructed using high-precision elementary geometry.
"""
import mpmath as mp
mp.mp.dps = 60
j = mp.mpc(0, 1)
def dot(a,b): return (mp.conj(a)*b).real
def cross(a,b): return (mp.conj(a)*b).imag
def line(a,b,c,d): return a+(b-a)*cross(c-a,d-c)/cross(b-a,d-c)
def foot(p,a,b): return a+(b-a)*dot(p-a,b-a)/abs(b-a)**2
def circle(a,b,c):
    # Solve the two linear equations for the center, independently of bisectors.
    u,v=b-a,c-a
    mat=mp.matrix([[2*u.real,2*u.imag],[2*v.real,2*v.imag]])
    rhs=mp.matrix([abs(b)**2-abs(a)**2,abs(c)**2-abs(a)**2])
    xy=mp.lu_solve(mat,rhs);o=mp.mpc(xy[0],xy[1])
    return o,abs(o-a)
def tangent(a,b,p):
    n=j*(b-a);o=a+n*abs(p-a)**2/(2*dot(n,p-a))
    return o,abs(o-a)
def lc(a,b,circ):
    o,r=circ;f=foot(o,a,b);h=mp.sqrt(r*r-abs(o-f)**2);u=(b-a)/abs(b-a)
    return f+h*u,f-h*u
def cc(w,z):
    o,r=w;p,s=z;d=abs(p-o);u=(p-o)/d;t=(r*r-s*s+d*d)/(2*d)
    h=mp.sqrt(r*r-t*t);return o+t*u+j*h*u,o+t*u-j*h*u
def other(pair,p): return max(pair,key=lambda q:abs(q-p))
def reconstruct(cid,coords):
    p={k:mp.mpc(str(v[0]),str(v[1])) for k,v in coords.items()}
    a,b=p['A'],p['B']
    if cid!='H07':c=p['C']
    if cid in ('H01','H04'):
        m=(b+c)/2;o,_=circle(a,b,c);h=a+b+c-2*o;z=foot(h,a,m)
        if cid=='H01':return {'BC':abs(b-c),'AM':abs(a-m)},abs(a-z)
        t=line((a+z)/2,(a+z)/2+j*(a-z),b,c)
        return {'BC':abs(b-c),'BT':abs(b-t)},abs(a-t)
    if cid=='H07':
        m=p['M'];w=tangent(a,b,m);z=tangent(b,a,m);n=other(cc(w,z),m)
        c=other(lc(m,m+1,w),m);d=other(lc(m,m+1,z),m)
        e=line(a,c,b,d);pp=line(a,n,c,d);q=line(b,n,c,d)
        return {'AB':abs(a-b),'ON':abs((a+b)/2-n),'MF':abs(m-foot(m,a,b))},abs(cross(pp-e,q-e))/2
    if cid=='H13':
        m=(a+c)/2;o,_=circle(b,m,c);k=line(c,c+j*(c-o),b,b+j*(c-b));jj=line(a,k,b,m);z,_=circle(b,jj,k)
        return {'BC':abs(b-c),'BK':abs(b-k),'cos_ACB':dot(a-c,b-c)/(abs(a-c)*abs(b-c))},abs(c-z)
    if cid=='H15':
        w=circle(a,b,c);o,_=w;x=line(b,b+j*(b-o),c,c+j*(c-o));d=other(lc(a,x,w),a)
        e=2*foot(d,b,c)-d;c0=2*foot(e,a,b)-e;b0=2*foot(e,a,c)-e;k=line(b,b0,c,c0)
        return {'AB':abs(a-b),'BD':abs(b-d),'AD':abs(a-d)},abs(b-k)
    if cid=='DA01':
        t=other(cc(tangent(a,c,b),tangent(a,b,c)),a)
        return {'AB':abs(a-b),'BC':abs(b-c),'CA':abs(c-a)},abs(a-t)
    if cid=='DA05':
        d=other(cc(tangent(b,c,a),tangent(b,a,c)),b);m=(b+c)/2;e=line(m,d,a,c)
        return {'BC':abs(b-c),'MD':abs(m-d)},abs(d-e)
    raise ValueError(cid)

def check(row):
    g,a=reconstruct(row['source_id'],row['private_witness']['points'])
    errors={k:float(abs(v-mp.mpf(str(row['givens'][k])))/max(1,abs(v))) for k,v in g.items()}
    errors['answer']=float(abs(a-mp.mpf(str(row['answer'])))/max(1,abs(a)))
    assert max(errors.values())<1e-7,(row['case_id'],errors)
    return {'id':row['case_id'],'relative_or_unit_errors':errors,'answer_60digit':mp.nstr(a,55)}
