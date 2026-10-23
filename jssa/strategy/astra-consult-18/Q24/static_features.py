"""Q24 input-only features. Standard library; no evaluation/geometry/solver calls.

Expressions are parsed, never eval'ed. Counts are syntactic proxies, not degrees,
root counts, numerical ranks, basin volumes, or a success-probability estimate.
"""
import ast
from collections import Counter
from functools import lru_cache


NONLINEAR = frozenset({
    'Distance', 'Area', 'Angle', 'IsTangent', 'Circumcircle', 'Circumcenter',
    'Intersect', 'FootOfPerpendicular', 'Incenter', 'Incircle', 'Excircle',
    'Orthocenter', 'AngleBisector', 'Reflect', 'Rotate', 'Radius', 'ContactPoint',
    'IncircleContactPoint', 'PointOnCircle', 'CircleThroughPoint', 'Tangent',
    'Polar', 'Slope', 'sqrt', 'sin', 'cos', 'tan', 'atan', 'abs', 'min',
    'Perpendicular', 'Parallel', 'Collinear', 'AreConcyclic', 'Dot',
    'OnCircle', 'OnLine', 'OnSegment',
})
# These operations can introduce a denominator, a branch, or a restricted domain.
HAZARD = frozenset({
    'Circumcircle', 'Circumcenter', 'Intersect', 'FootOfPerpendicular',
    'Incenter', 'Incircle', 'Excircle', 'Orthocenter', 'AngleBisector',
    'Reflect', 'ContactPoint', 'IncircleContactPoint', 'PointOnCircle',
    'Tangent', 'Polar', 'Slope', 'sqrt', 'tan',
})
EQUALITY_PREDICATES = frozenset({
    'IsTangent', 'OnCircle', 'OnLine', 'OnSegment', 'Collinear', 'Parallel',
    'Perpendicular', 'AreConcyclic',
})
TRANSCENDENTAL = frozenset({'sin', 'cos', 'tan', 'atan'})


@lru_cache(maxsize=32768)
def parse(text):
    return ast.parse(text, mode='eval').body


def call_name(node):
    return node.func.id if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) else ''


def maximum_matching(supports):
    """Maximum equation/variable support matching, NOT a numerical rank."""
    owner = {}

    def augment(i, seen):
        for v in sorted(supports[i]):
            if v in seen:
                continue
            seen.add(v)
            if v not in owner or augment(owner[v], seen):
                owner[v] = i
                return True
        return False

    return sum(augment(i, set()) for i in range(len(supports)))


def features(dsl):
    variables = set(dsl['variables'])
    expressions = {c['name']: parse(str(c['expression'])) for c in dsl.get('constructions', [])}
    env, visiting = {}, set()

    def describe(node):
        if isinstance(node, ast.Name):
            if node.id in variables:
                return frozenset({node.id}), 0, 0
            if node.id in expressions:
                return resolve(node.id)
            return frozenset(), 0, 0
        if isinstance(node, ast.Call):
            children = list(node.args) + [k.value for k in node.keywords]
        else:
            children = list(ast.iter_child_nodes(node))
        vals = [describe(c) for c in children]
        deps = frozenset().union(*(v[0] for v in vals))
        nd = max((v[1] for v in vals), default=0)
        hd = max((v[2] for v in vals), default=0)
        nonlinear, hazard = flags(node, deps)
        return deps, nd + nonlinear, hd + hazard

    def flags(node, deps):
        if not deps:
            return 0, 0
        name = call_name(node)
        nl, hz = int(name in NONLINEAR), int(name in HAZARD)
        if isinstance(node, ast.BinOp):
            left, right = describe(node.left)[0], describe(node.right)[0]
            if isinstance(node.op, ast.Mult) and left and right:
                nl = 1
            if isinstance(node.op, ast.Div) and right:
                nl = hz = 1
            if isinstance(node.op, ast.Pow):
                if not (isinstance(node.right, ast.Constant) and node.right.value in (0, 1)):
                    nl = 1
                if not (isinstance(node.right, ast.Constant) and isinstance(node.right.value, int) and node.right.value >= 0):
                    hz = 1
        return nl, hz

    def resolve(name):
        if name not in env:
            if name in visiting:
                raise ValueError('cyclic construction: ' + name)
            visiting.add(name)
            env[name] = describe(expressions[name])
            visiting.remove(name)
        return env[name]

    conditions = dsl.get('conditions', [])
    roots, supports, eq_nodes, guard_nodes = [], [], [], []
    n_eq = 0

    def predicate_leaves(node):
        if call_name(node) == 'And':
            for arg in node.args:
                yield from predicate_leaves(arg)
        else:
            yield node

    for cond in conditions:
        if 'predicate' in cond:
            node = parse(str(cond['predicate']))
            roots.append(node)
            for leaf in predicate_leaves(node):
                if call_name(leaf) in EQUALITY_PREDICATES:
                    supports.append(describe(leaf)[0])
                    eq_nodes.append(leaf)
                    n_eq += 1
                else:
                    guard_nodes.append(leaf)
        else:
            left, right = parse(str(cond['left'])), parse(str(cond['right']))
            roots.extend([left, right])
            if cond.get('operator') == '=':
                supports.append(describe(left)[0] | describe(right)[0])
                eq_nodes.extend([left, right])
                n_eq += 1
            else:
                guard_nodes.extend([left, right])
    target = parse(str(dsl['target']))
    roots.append(target)
    active_names = set()

    def add_ancestors(node):
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and sub.id in expressions and sub.id not in active_names:
                active_names.add(sub.id)
                add_ancestors(expressions[sub.id])

    for node in roots:
        add_ancestors(node)
    trees = roots + [expressions[n] for n in sorted(active_names)]
    calls, active_calls = Counter(), Counter()
    nonlinear_gates = hazard_gates = division_gates = dynamic_trig = 0
    for node in trees:
        for sub in ast.walk(node):
            deps = describe(sub)[0]
            name = call_name(sub)
            if name:
                calls[name] += 1
                if deps:
                    active_calls[name] += 1
                    dynamic_trig += int(name in TRANSCENDENTAL)
            nl, hz = flags(sub, deps)
            nonlinear_gates += nl
            hazard_gates += hz
            division_gates += int(isinstance(sub, ast.BinOp) and isinstance(sub.op, ast.Div) and bool(describe(sub.right)[0]))
    matching = maximum_matching(supports)
    out = {
        'd': len(variables), 'construction_count': len(expressions),
        'active_constructions': len(active_names), 'condition_count': len(conditions),
        'equation_slots': n_eq, 'active_equation_slots': sum(bool(s) for s in supports),
        'support_matching': matching, 'unmatched_variables': len(variables) - matching,
        'nonlinear_gates': nonlinear_gates, 'hazard_gates': hazard_gates,
        'nonlinear_depth': max((describe(n)[1] for n in roots), default=0),
        'hazard_depth': max((describe(n)[2] for n in roots), default=0),
        'active_tangent': active_calls['IsTangent'], 'active_angle': active_calls['Angle'],
        'active_distance': active_calls['Distance'], 'active_area': active_calls['Area'],
        'variable_denominators': division_gates, 'dynamic_trig': dynamic_trig,
        'integer_predicates': calls['IsInteger'],
        'target_depends': len(describe(target)[0]),
        'calls': dict(sorted(calls.items())), 'active_calls': dict(sorted(active_calls.items())),
        'equation_supports': [sorted(s) for s in supports],
    }
    # No roots, starts, bounds inference, floating coordinates, or solver imports.
    return out


RULE_NAMES = ('R0_dimension', 'R1_mechanism', 'R2_conservative')


def predict(f, rule):
    if rule not in RULE_NAMES:
        raise ValueError(rule)
    if f['d'] == 0:
        return {'local': 'no_search', 'exact': 'no_search', 'direction': 'none'}
    if rule == 'R0_dimension':
        local = 'easy' if f['d'] <= 2 else ('hard' if f['d'] >= 5 else 'abstain')
        exact = 'fast' if f['d'] <= 2 else ('costly' if f['d'] >= 5 else 'abstain')
    else:
        if f['active_tangent'] or f['d'] >= 5:
            local = 'hard'
        elif rule == 'R2_conservative' and f['d'] >= 3 and f['hazard_depth'] >= 2:
            local = 'hard'
        elif f['d'] <= 2 and (f['hazard_gates'] == 0 if rule == 'R2_conservative' else f['hazard_depth'] <= 1):
            local = 'easy'
        else:
            local = 'abstain'
        if f['dynamic_trig'] or f['integer_predicates']:
            exact = 'out_of_scope'
        elif f['unmatched_variables']:
            exact = 'enumeration_mismatch'
        elif f['nonlinear_gates'] >= 12 or f['nonlinear_depth'] >= 4:
            exact = 'costly'
        elif f['d'] <= 2 and f['nonlinear_gates'] <= 4:
            exact = 'fast'
        else:
            exact = 'abstain'
    direction = 'none'
    if local == 'easy' and exact == 'costly':
        direction = 'exact_costly_local_easy'
    elif local == 'easy' and exact == 'enumeration_mismatch':
        direction = 'enumeration_mismatch_local_easy'
    elif local == 'hard' and exact == 'fast':
        direction = 'exact_fast_local_hard'
    return {'local': local, 'exact': exact, 'direction': direction}
