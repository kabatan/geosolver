#!/usr/bin/env python3
"""Shared construction primitives for v2 authoring verifiers.

Pure Python, complex Cartesian coordinates. Extracted from the retired v1
authoring script ``humpty_configurations_v1/authoring/verify_dumpty_a.py`` so
the v2 datasets no longer depend on the v1 tree. These are floating-point
authoring helpers, not proofs or exact numeric-label generators.
"""
import cmath
import math

TOL = 1e-8


def dot(a, b):
    return (a.conjugate() * b).real


def cross(a, b):
    return (a.conjugate() * b).imag


def near(a, b=0, tol=TOL):
    assert abs(a-b) <= tol * max(1, abs(a), abs(b)), (a, b)


def line(a, b, c, d):
    u, v = b-a, d-c
    assert abs(cross(u, v)) > 1e-10
    return a + u * cross(c-a, v) / cross(u, v)


def circle(a, b, c):
    o = line((a+b)/2, (a+b)/2+(b-a)*1j,
             (a+c)/2, (a+c)/2+(c-a)*1j)
    r = abs(o-a)
    near(abs(o-b), r)
    near(abs(o-c), r)
    return o, r


def tangent_circle(a, b, p):
    """Circle through p tangent to the entire line ab at a."""
    n = (b-a)*1j
    assert abs(dot(n, p-a)) > 1e-10
    o = a + n * abs(p-a)**2 / (2*dot(n, p-a))
    near(abs(o-p), abs(o-a))
    near(dot(o-a, b-a), 0)
    return o, abs(o-a)


def lc(a, b, c):
    o, r = c
    u = b-a
    t = dot(o-a, u) / abs(u)**2
    h2 = r*r - abs(a+t*u-o)**2
    assert h2 > 1e-10, ("not two intersections", h2)
    d = math.sqrt(h2 / abs(u)**2)
    return [a+(t-d)*u, a+(t+d)*u]


def cc(c, d):
    o, r = c
    p, s = d
    v = abs(p-o)
    assert v > 1e-10
    u = (p-o)/v
    t = (r*r-s*s+v*v)/(2*v)
    h2 = r*r-t*t
    assert h2 > 1e-10, ("not two intersections", h2)
    h = math.sqrt(h2)
    return [o+t*u+1j*u*h, o+t*u-1j*u*h]


def other(points, known):
    near(min(abs(p-known) for p in points), 0)
    return max(points, key=lambda p: abs(p-known))


def foot(p, a, b):
    return a + (b-a)*dot(p-a, b-a)/abs(b-a)**2


def unit(z):
    return z/abs(z)


def sides(a, b, c):
    return {"a": abs(b-c), "b": abs(c-a), "c": abs(a-b)}


def triangle(a=5+12j, b=0j, c=14+0j):
    o, r = circle(a, b, c)
    h = a+b+c-2*o
    return a, b, c, o, r, (b+c)/2, h


def tangent_pair(a, b, c):
    w1, w2 = tangent_circle(a, c, b), tangent_circle(a, b, c)
    return w1, w2, other(cc(w1, w2), a)


def inside_triangle(p, a, b, c):
    signs = [cross(b-a, p-a), cross(c-b, p-b), cross(a-c, p-c)]
    return min(signs) > 1e-8 or max(signs) < -1e-8


def minor_point(a, b, o, t):
    theta = cmath.phase((b-o)/(a-o))
    return o + (a-o)*cmath.exp(1j*t*theta)


def on_minor(p, a, b, o):
    delta = cmath.phase((b-o)/(a-o))
    theta = cmath.phase((p-o)/(a-o))
    return 1e-8 < theta/delta < 1-1e-8


def choose_minor(points, a, b, o):
    found = [p for p in points if on_minor(p, a, b, o)]
    assert len(found) == 1
    return found[0]


def sq(a, b):
    return abs(a-b)**2
