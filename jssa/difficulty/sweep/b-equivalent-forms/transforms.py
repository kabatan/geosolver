"""Syntax-based, domain-preserving input transformations.

Squared lengths require both sides to be nonnegative by syntax or an original
guard. Angle transformations only apply to two expressions in [0, pi].
Tangency rewrites currently cover a genuine Line and Circle, not arcs.
"""
from __future__ import annotations
import ast
import copy
import math

def node(source):
    return ast.parse(str(source), mode='eval').body

def call(n, name=None, arity=None):
    return (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and (name is None or n.func.id == name)
            and (arity is None or len(n.args) == arity) and not n.keywords)

def constant(n):
    if isinstance(n, ast.Constant) and type(n.value) in (int, float):
        return n.value
    if isinstance(n, ast.Name) and n.id == 'pi':
        return math.pi
    if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
        v = constant(n.operand)
        return None if v is None else (-v if isinstance(n.op, ast.USub) else v)
    if call(n, 'sqrt', 1):
        v = constant(n.args[0])
        return math.sqrt(v) if v is not None and v >= 0 else None
    if isinstance(n, ast.BinOp):
        a, b = constant(n.left), constant(n.right)
        if a is not None and b is not None:
            try:
                if isinstance(n.op, ast.Add): return a+b
                if isinstance(n.op, ast.Sub): return a-b
                if isinstance(n.op, ast.Mult): return a*b
                if isinstance(n.op, ast.Div): return a/b
                if isinstance(n.op, ast.Pow): return a**b
            except (ArithmeticError, ValueError): pass
    return None

def resolve(n, definitions):
    seen = set()
    while isinstance(n, ast.Name) and n.id in definitions and n.id not in seen:
        seen.add(n.id)
        n = node(definitions[n.id])
    return n

def angle(n):
    return call(n, 'Angle', 3)

def angle_value(n):
    c = constant(n)
    return angle(n) or (c is not None and 0 <= c <= math.pi)

def positive_names(d):
    return {c['left'] for c in d['conditions']
            if c.get('operator') in ('>', '>=') and constant(node(c['right'])) == 0}

def nonnegative(n, positives):
    c = constant(n)
    if c is not None: return c >= 0
    if isinstance(n, ast.Name): return n.id in positives
    if call(n) and n.func.id in ('Distance', 'Length', 'Radius'): return True
    if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Mult, ast.Div)):
        return nonnegative(n.left, positives) and nonnegative(n.right, positives)
    return False

def tangent_pair(n, definitions):
    if not call(n, 'IsTangent', 2): return None
    for a, b in (n.args, n.args[::-1]):
        line = resolve(a, definitions)
        circle = resolve(b, definitions)
        if call(line, 'Line') and len(line.args) in (2, 3) and call(circle) and circle.func.id in (
            'Circle', 'Circumcircle', 'Incircle', 'Excircle', 'NinePointCircle'):
            return ast.unparse(a), ast.unparse(b), line
    return None

def applicable(d):
    defs = {c['name']: c['expression'] for c in d['constructions']}
    pos = positive_names(d)
    found = {'angle': [], 'length': [], 'tangent': []}
    for i, c in enumerate(d['conditions']):
        if c.get('operator') != '=': continue
        l, r = node(c['left']), node(c['right'])
        if (angle(l) or angle(r)) and angle_value(l) and angle_value(r): found['angle'].append(i)
        if ('Distance(' in ast.unparse(l) + ast.unparse(r)
                and nonnegative(l, pos) and nonnegative(r, pos)):
            found['length'].append(i)
        if constant(r) == 0 and tangent_pair(l, defs): found['tangent'].append(i)
    return found

def vector_cos(n):
    if not angle(n): return f'cos({ast.unparse(n)})', []
    a, b, c = map(ast.unparse, n.args)
    return (f'Dot(Vector({b},{a}),Vector({b},{c}))/(Distance({b},{a})*Distance({b},{c}))',
            [{'left': f'Distance({b},{a})', 'operator': '>', 'right': 0},
             {'left': f'Distance({b},{c})', 'operator': '>', 'right': 0}])

def rewrite(d, arm):
    out = copy.deepcopy(d)
    changes = []
    eligible = applicable(d)
    defs = {c['name']: c['expression'] for c in d['constructions']}
    if arm == 'base': return out, changes
    if arm.startswith('repeat_first_') or arm == 'repeat_all_32':
        eq = [c for c in d['conditions'] if c.get('operator') == '=']
        n = 32 if arm == 'repeat_all_32' else int(arm.rsplit('_', 1)[1])
        rows = eq if arm == 'repeat_all_32' else eq[:1]
        out['conditions'] += copy.deepcopy(rows * (n-1))
        return out, [{'kind': arm, 'added_equalities': len(rows)*(n-1)}]
    if arm.startswith('dummy_') or arm == 'unused_points_32':
        n = int(arm.rsplit('_', 1)[1])
        names = set(d['variables']) | set(defs)
        assert all(f'q43bDummy{j}' not in names and f'q43bT{j}' not in names for j in range(n))
        for j in range(n):
            p, v = f'q43bDummy{j}', f'q43bT{j}'
            if arm == 'unused_points_32':
                out['constructions'].append({'name': p, 'expression': f'Point({100+j}, {200+j})'})
            else:
                out['variables'].append(v)
                out['constructions'].append({'name': p, 'expression': f'Point({v}, 0)'})
                out['conditions'] += [{'left': f'Distance({p}, Point(0,0))', 'operator': '=', 'right': 1},
                                      {'left': v, 'operator': '>', 'right': 0}]
        return out, [{'kind': arm, 'added_points': n, 'added_variables': 0 if arm == 'unused_points_32' else n}]
    for i, cond in enumerate(out['conditions'][:]):
        if cond.get('operator') != '=': continue
        l, r = node(cond['left']), node(cond['right'])
        if arm in ('form_cos', 'form_vector', 'form_tan') and i in eligible['angle']:
            if arm == 'form_vector':
                left, lg = vector_cos(l); right, rg = vector_cos(r)
                out['conditions'] += lg + rg
            elif arm == 'form_cos':
                left, right = f'cos({ast.unparse(l)})', f'cos({ast.unparse(r)})'
            else:
                left = f'tan((({ast.unparse(l)})-pi/2)/2)'
                right = f'tan((({ast.unparse(r)})-pi/2)/2)'
            out['conditions'][i] = {'left': left, 'operator': '=', 'right': right}
            changes.append({'condition': i, 'kind': arm, 'family': 'angle'})
        elif arm in ('form_cos', 'form_vector') and i in eligible['length']:
            def squared(n):
                if arm == 'form_vector' and call(n, 'Distance', 2):
                    a, b = map(ast.unparse, n.args)
                    # Dot only applies to points. Other distance types retain square form.
                    point_funcs = {'Point','Midpoint','Center','PointOnSegment','PointOnLine',
                                   'PointOnCircle','FootOfPerpendicular','Intersect','Centroid',
                                   'Incenter','Circumcenter','Orthocenter','ContactPoint','Reflect','Rotate'}
                    if all(call(resolve(x, defs)) and resolve(x, defs).func.id in point_funcs for x in n.args):
                        return f'Dot(Vector({a},{b}),Vector({a},{b}))'
                return f'({ast.unparse(n)})**2'
            out['conditions'][i] = {'left': squared(l), 'operator': '=', 'right': squared(r)}
            changes.append({'condition': i, 'kind': arm, 'family': 'length'})
        elif arm in ('form_cos', 'form_vector') and i in eligible['tangent']:
            line_source, circle_source, line = tangent_pair(l, defs)
            if arm == 'form_cos':
                left = f'Distance(Center({circle_source}),{line_source})'
                right = f'Radius({circle_source})'
            elif len(line.args) == 2:
                p, q = map(ast.unparse, line.args)
                v = f'Vector({p},{q})'; w = f'Vector(Center({circle_source}),{p})'
                left = f'(2*Dot({v},{w}))**2-4*Dot({v},{v})*(Dot({w},{w})-Radius({circle_source})**2)'
                right = '0'
            else:
                a, b, c = map(ast.unparse, line.args)
                left = (f'Radius({circle_source})**2*(({a})**2+({b})**2)'
                        f'-(({a})*Center({circle_source}).x+({b})*Center({circle_source}).y+({c}))**2')
                right = '0'
            out['conditions'][i] = {'left': left, 'operator': '=', 'right': right}
            changes.append({'condition': i, 'kind': arm, 'family': 'tangent'})
    return out, changes

ARMS = ('base', 'form_cos', 'form_vector', 'form_tan',
        'repeat_first_2', 'repeat_first_8', 'repeat_first_32', 'repeat_all_32',
        'unused_points_32', 'dummy_1', 'dummy_8', 'dummy_32')
