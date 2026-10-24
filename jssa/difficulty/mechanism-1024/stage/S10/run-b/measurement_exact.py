"""Independent exact-set grading. Never imports geosolver; runs outside measurement."""
import csv
import json
import statistics
import sys
from collections import Counter
from functools import lru_cache
from pathlib import Path

import sympy as sp
from measurement_common import load, save, sha, utc

X = sp.Symbol('x')

def primitive(poly):
    p = sp.Poly(poly, X, domain=sp.QQ).clear_denoms()[1].primitive()[1]
    return p if p.LC() > 0 else -p

@lru_cache(maxsize=None)
def algebraic_expression(text):
    # rational=True is essential: (2/9)**(1/3) denotes an exact rational power.
    e = sp.sympify(text, rational=True)
    if e.has(sp.Float) or e.free_symbols or e.is_real is False:
        raise ValueError(f'not an exact real constant: {text}')
    p = primitive(sp.minimal_polynomial(e, X))
    roots = sp.real_roots(p.as_expr(), X)
    intervals = sp.polys.polytools.intervals(p, eps=sp.Rational(1, 10**60))
    matches = []
    for i, (((a, b), _), root) in enumerate(zip(intervals, roots, strict=True)):
        if sp.simplify(e - root) == 0 or ((e >= a) is sp.true and (e <= b) is sp.true):
            matches.append(i)
    if len(matches) != 1:
        raise ValueError(f'cannot isolate exact reference: {text}')
    return (tuple(str(c) for c in p.all_coeffs()), matches[0])

@lru_cache(maxsize=None)
def expression_key(text):
    e = sp.expand(sp.sympify(text, rational=True))
    if e.has(sp.pi):
        a = sp.simplify(e.coeff(sp.pi))
        b = sp.simplify(e.subs(sp.pi, 0))
        if sp.simplify(e - a * sp.pi - b) != 0:
            raise ValueError('non affine pi reference')
        if a != 0:
            return ('affine_pi', algebraic_expression(str(a)), algebraic_expression(str(b)))
        e = b
    return ('algebraic', algebraic_expression(str(e)))

@lru_cache(maxsize=None)
def descriptor_key(coefficients, index):
    if not coefficients or isinstance(index, bool) or not isinstance(index, int):
        raise ValueError('invalid algebraic descriptor')
    coeff = [sp.Rational(c) for c in coefficients]
    p = primitive(sum(c * X**i for i, c in enumerate(reversed(coeff))))
    if p.degree() < 1 or not p.is_sqf:
        raise ValueError('invalid minimal polynomial')
    roots = sp.real_roots(p.as_expr(), X)
    if index < 0 or index >= len(roots):
        raise ValueError('invalid real root index')
    if p.is_irreducible:
        return (tuple(str(c) for c in p.all_coeffs()), index)
    # Normalize an equivalent reducible representation using its selected exact root.
    return algebraic_expression(str(roots[index]))

def descriptor(d):
    return descriptor_key(tuple(d['minimal_polynomial']), d['real_root_index'])

def answer_key(a):
    if a['kind'] == 'algebraic':
        return ('algebraic', descriptor(a['value']))
    if a['kind'] == 'affine_pi':
        coefficient, constant = descriptor(a['pi_coefficient']), descriptor(a['constant'])
        if coefficient == algebraic_expression('0'):
            return ('algebraic', constant)
        return ('affine_pi', coefficient, constant)
    raise ValueError('unknown exact answer kind')

def serial(keys):
    # Stable ordering and de-duplication; no tolerance or numerical nearest-root rule.
    return [json.loads(k) for k in sorted({json.dumps(k, separators=(',', ':')) for k in keys})]

