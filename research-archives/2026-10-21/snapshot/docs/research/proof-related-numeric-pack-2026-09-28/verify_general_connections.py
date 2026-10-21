"""Researcher-only identities; never used as model-facing problem statements."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import time

import sympy as s

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
AUTHOR = ROOT/'benchmarks/humpty_configurations_v2/authoring'
sys.path.insert(0, str(AUTHOR))
import verify_additional_relations as prior


def clean(x):
    return x.applyfunc(s.factor) if isinstance(x, s.MatrixBase) else s.factor(x)


def norm(x):
    return x.dot(x)


def rot(x):
    return s.Matrix([-x[1], x[0]])


def line(a, b, c, d):
    cross = lambda x, y: s.det(s.Matrix.hstack(x, y))
    return clean(a+(b-a)*cross(c-a, d-c)/cross(b-a, d-c))


def circle(a, b, c):
    mat = s.Matrix([[p[0], p[1], 1] for p in [a,b,c]])
    return clean(mat.inv()*s.Matrix([-norm(p) for p in [a,b,c]]))


def second(p, direction, w):
    return clean(p-direction*(2*p.dot(direction)+w[:2,:].dot(direction))/norm(direction))


def diameter(a,b):
    return s.Matrix([-(a+b)[0], -(a+b)[1], a.dot(b)])


def check_seven_eight():
    u,v,d = s.symbols('u v d', real=True, nonzero=True)
    A,B,C = s.Matrix([u,v]),s.Matrix([0,0]),s.Matrix([d,0])
    O = s.Matrix([d/2,(u*u+v*v-d*u)/(2*v)])
    H = clean(A+B+C-2*O)
    wo,wh = circle(B,O,C),circle(B,H,C)
    M = second(O,rot((wo-diameter(A,O))[:2,:]),wo)
    N = second(H,rot((wh-diameter(A,H))[:2,:]),wh)
    X,Y = second(M,M-A,wo),second(N,N-A,wh)
    k = clean((X-A).dot(M-A)/norm(M-A))
    assert clean(X-A-k*(M-A)) == s.zeros(2,1)
    assert clean(Y-A-k*(N-A)) == s.zeros(2,1)
    print('PN06 / DA07: identical signed similarity factor for AX/AM and AY/AN: PASS')

    Q = clean(-wo[:2,:]-O)
    M = line(C,Q,A,A+C-B)
    N = clean(A+C-M)
    T = line(A,Q,M,N)
    assert clean(norm(T)+wo[:2,:].dot(T)+wo[2]) == 0
    assert clean((T-O).dot(T-Q)) == 0
    print('PN07 / DA08: original parallelogram intersection lies on circle BOC and OT perpendicular QT: PASS')


def main():
    started = time.monotonic()
    capture = io.StringIO()
    with contextlib.redirect_stdout(capture):
        prior.check_dumpty_core()
        prior.check_da04()
        prior.check_db02()
        check_seven_eight()
    result = {
        'status': 'pass', 'elapsed_seconds': time.monotonic()-started,
        'scope': 'General rational identities on the nondegenerate construction domain. '
                 'Positive lengths and named branches use the problem assumptions; '
                 'this is not a complete fresh proof of every statement in all 10 questions.',
        'checks': capture.getvalue().splitlines(),
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'prior_script_sha256': hashlib.sha256((AUTHOR/'verify_additional_relations.py').read_bytes()).hexdigest(),
    }
    (HERE/'review').mkdir(exist_ok=True)
    (HERE/'review/general-identities.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
