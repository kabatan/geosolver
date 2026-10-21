"""General rational identities for the two circles tangent to one line.

Use A=(0,0), B=(d,0), their common point X=(u,v). Circle centers
are forced by incidence and perpendicularity at A and B. Parameters are
symbolic, so these checks are not deductions from a single example.
The domain excludes vanishing denominators, tangencies and coincident points;
branch/order inequalities remain part of the individual question statements.
"""
import sympy as s
from verify_h_revision import cross, norm, pt, rot


def clean(x):
    if isinstance(x, s.MatrixBase):
        return x.applyfunc(s.factor)
    return s.factor(x)


def line(a, b, c, d):
    return clean(a + (b-a) * cross(c-a, d-c) / cross(b-a, d-c))


def second(p, direction, circle):
    return clean(p - direction * (2*p.dot(direction) + circle[0]*direction[0] + circle[1]*direction[1]) / norm(direction))


def check():
    u,v,d=s.symbols('u v d', nonzero=True, real=True)
    a,b,x=pt(0,0),pt(d,0),pt(u,v)
    r1=norm(x-a)/(2*v)
    r2=norm(x-b)/(2*v)
    o1,o2=pt(0,r1),pt(d,r2)
    w,z=pt(0,-2*r1).col_join(s.Matrix([0])),pt(-2*d,-2*r2).col_join(s.Matrix([d*d]))
    k=line(x,x+rot(x-o1),o1,o2)
    l=line(x,x+rot(x-o2),o1,o2)
    n=second(a,k-a,w)
    m=second(b,l-b,z)
    r=line(a,m,b,n)
    assert clean(cross(r-o1,o2-o1))==0

    # H07: E is the reflection of the near intersection, and X is PQ midpoint.
    far=second(x,rot((w-z)[:2,:]),w)
    c=second(x,pt(1,0),w)
    dd=second(x,pt(1,0),z)
    e=line(a,c,b,dd)
    p=line(a,far,c,dd)
    q=line(b,far,c,dd)
    assert clean(e-pt(u,-v))==s.zeros(2,1)
    assert clean(p+q-2*x)==s.zeros(2,1)
    mid=(a+b)/2
    assert clean(cross(far-mid,x-mid))==0
    assert clean((far-mid).dot(x-mid)-d*d/4)==0

    # H08: the reflection of X is on circle far,A,B, and the stated rays are isogonal.
    reflected=pt(u,-v)
    circle_outer=s.Matrix([[a[0],a[1],1],[b[0],b[1],1],[far[0],far[1],1]]).inv()*s.Matrix([-norm(a),-norm(b),-norm(far)])
    assert clean(norm(reflected)+circle_outer[0]*reflected[0]+circle_outer[1]*reflected[1]+circle_outer[2])==0
    v1,v2=reflected-far,a-far
    v3,v4=x-far,b-far
    # Directed tangent angles have opposite sign. Acute vertex fixes equal positive angles.
    assert clean(cross(v1,v2)*v3.dot(v4)+cross(v3,v4)*v1.dot(v2))==0
    print('H06 center-line concurrency, H07 reflection/midpoint/inversion, H08 cyclicity/isogonality: general rational identities PASS.')


def check_dumpty_core():
    u,v,d=s.symbols('u v d', nonzero=True, real=True)
    a,b,c=pt(u,v),pt(0,0),pt(d,0)
    def tangent_circle(p,q,direction):
        mat=s.Matrix.vstack((2*(q-p)).T,direction.T)
        o=clean(mat.inv()*s.Matrix([norm(q)-norm(p),p.dot(direction)]))
        return s.Matrix([-2*o[0],-2*o[1],2*o.dot(p)-norm(p)])
    w=tangent_circle(a,b,c-a)
    z=tangent_circle(a,c,b-a)
    q=second(a,rot((w-z)[:2,:]),w)
    m=(b+c)/2
    o=pt(d/2,(u*u+v*v-d*u)/(2*v))
    assert clean(4*norm(a-q)*norm(a-m)-norm(a-b)*norm(a-c))==0
    assert clean(norm(a-q)**2-norm(b-q)*norm(c-q))==0
    assert clean((q-a).dot(q-o))==0
    print('Dumpty core: AQ*AM=AB*AC/2, AQ^2=BQ*CQ, and AQ perpendicular OQ: general identities PASS.')

    # DB15 / DA11: the original altitude foot and Q determine the median of DEF.
    altitude_foot=pt(u,0)
    e,f=(a+c)/2,(a+b)/2
    assert clean(cross(q-altitude_foot,(e+f)/2-altitude_foot))==0

    # DB12: construct an arbitrary parallel grid, not the claimed fixed point.
    t=s.symbols('t', real=True)
    moving=b+t*(c-b)
    e=line(moving,moving+b-a,a,c)
    f=line(moving,moving+c-a,a,b)
    mat=s.Matrix([[a[0],a[1],1],[e[0],e[1],1],[f[0],f[1],1]])
    coeff=clean(mat.inv()*s.Matrix([-norm(a),-norm(e),-norm(f)]))
    assert clean(norm(q)+coeff[0]*q[0]+coeff[1]*q[1]+coeff[2])==0
    print('DB15/DA11 midpoint collinearity and DB12 parallel-grid fixed point: general identities PASS.')

    # DA15: intersections of the median with the two side bisectors.
    mid_ab,mid_ac=(a+b)/2,(a+c)/2
    d1=line(a,m,mid_ab,mid_ab+rot(b-a))
    e1=line(a,m,mid_ac,mid_ac+rot(c-a))
    f1=line(b,d1,c,e1)
    assert clean(f1-q)==s.zeros(2,1)
    assert clean(4*norm(f1-(a+o)/2)-norm(a-o))==0
    print('DA15: the constructed intersection equals Dumpty and is on the midpoint circle: general identities PASS.')


def check_db16():
    c,u,v,t=s.symbols('c u v t', nonzero=True, real=True)
    a,b,p_c=pt(0,0),pt(c,0),pt(u,v)
    side_b,side_c=norm(a-p_c),norm(a-b)
    symmedian_foot=clean((side_b*b+side_c*p_c)/(side_b+side_c))
    p=t*symmedian_foot
    def center(x,y):
        return clean(s.Matrix.vstack((2*x).T,(2*y).T).inv()*s.Matrix([norm(x),norm(y)]))
    o,o1,o2=center(b,p_c),center(p,b),center(p_c,p)
    assert clean(cross((o1+o2)/2,o))==0
    print('DB16: midpoint of the two constructed centers lies on AO: general identity PASS.')


def check_db01():
    h,b,c=s.symbols('h b c', nonzero=True, real=True)
    # With P,Q internal, BP*CQ=AP*AQ is exactly AP/AB+AQ/AC=1.
    r=clean((h*h+b*b)*(h*h+c*c)/(2*h*(2*h*h+b*b+c*c)))
    j=pt(0,h-r)
    ox,oy=(b+c)/2,(h*h+b*c)/(2*h)
    uy=clean((oy*oy-(c-b)**2/4)/(2*oy))
    center=pt(ox,uy)
    outer_r=clean((oy*oy+(c-b)**2/4)/(2*oy))
    # h>0 and acute A give oy>0, so both displayed radii are positive.
    assert clean(norm(center-j)-(r+outer_r)**2)==0
    print('DB01: the product-selected circle is externally tangent to circle BOC: general identity PASS.')


def check_db02():
    u,v,d=s.symbols('u v d', nonzero=True, real=True)
    a,b,c=pt(u,v),pt(0,0),pt(d,0)
    # Rotate AB by angle C and AC by -angle B; common normalizing
    # factors do not affect the direction of these angle-defined lines.
    p=line(a,a+pt(u*u+v*v-d*u,-d*v),b,c)
    q=line(a,a+pt(d*u-u*u-v*v,-d*v),b,c)
    m,n=2*p-a,2*q-a
    x=line(b,m,c,n)
    oy=(u*u+v*v-d*u)/(2*v)
    assert clean(norm(x)-d*x[0]-2*oy*x[1])==0
    assert clean(norm(x-b)*norm(a-c)-norm(x-c)*norm(a-b))==0
    print('DB02: the reflected-ray intersection is on the circumcircle with BX/CX=AB/AC: general identities PASS.')


def check_db13():
    h,b,c,w=s.symbols('h b c w', nonzero=True, real=True)
    a=pt(0,h)
    o=pt((b+c)/2,(h*h+b*c)/(2*h))
    e=pt(c/2,h/2)
    center=pt((b+c)/4,w)
    big_r2=norm(a-o)
    small_r2=norm(e-center)
    dd=norm(center-o)
    equation=clean((big_r2+small_r2-dd)**2-4*big_r2*small_r2)
    known=(o[1]+h)/2  # the other solution is the homothetic circle touching at A
    assert clean(equation.subs(w,known))==0
    quotient=clean(equation/(w-known))
    roots=s.solve(quotient,w)
    assert len(roots)==1
    center=clean(center.subs(w,roots[0]))
    small_r2,dd=norm(e-center),norm(center-o)
    contact=clean(o+2*big_r2/(big_r2+dd-small_r2)*(center-o))
    g=pt((b+c)/3,h/3)
    assert clean(cross(contact,g))==0  # altitude foot is (0,0)
    assert clean(norm(contact-o)-big_r2)==0
    print('DB13: the non-A tangency point is collinear with centroid and altitude foot: general identity PASS.')


def check_db04():
    c,d,t=s.symbols('c d t', nonzero=True, real=True)
    a=pt(0,0)
    # Rotate axes to the internal/external bisectors of angle CAD.
    cc,dd=pt(c*(1-t*t),2*c*t),pt(d*(1-t*t),-2*d*t)
    def tc(q,direction):
        o=clean(s.Matrix.vstack((2*q).T,direction.T).inv()*s.Matrix([norm(q),0]))
        return s.Matrix([-2*o[0],-2*o[1],0])
    w,z=tc(dd,cc),tc(cc,dd)
    b=second(a,rot((w-z)[:2,:]),w)
    e,f=second(a,pt(1,0),w),second(a,pt(1,0),z)
    x,y=second(a,pt(0,1),w),second(a,pt(0,1),z)
    k=(x+y)/2
    coeff=clean(s.Matrix([[b[0],b[1],1],[e[0],e[1],1],[f[0],f[1],1]]).inv()*s.Matrix([-norm(b),-norm(e),-norm(f)]))
    o=-coeff[:2,:]/2
    radius2=norm(o-e)
    assert clean((o[1]-k[1])**2-radius2)==0
    print('DB04: the perpendicular bisector of XY is tangent to circle BEF: general identity PASS.')


def check_da04():
    d,p,h=s.symbols('d p h', nonzero=True, real=True)
    a,b,pnt=pt(0,0),pt(d,0),pt(p,0)
    o=pt(d/2,h)
    o1=clean(a+p/d*(o-a))
    o2=clean(b+(d-p)/d*(o-b))
    w=s.Matrix([-2*o1[0],-2*o1[1],0])
    z=s.Matrix([-2*o2[0],-2*o2[1],2*o2.dot(b)-norm(b)])
    q=second(pnt,rot((w-z)[:2,:]),w)
    assert clean((q-o).dot(q-pnt))==0
    print('DA04: the second inner-circle intersection is the outer chord midpoint: general identity PASS.')


if __name__=='__main__':
    check()
    check_dumpty_core()
    check_da04()
    check_db16()
    check_db01()
    check_db02()
    check_db13()
    check_db04()
