"""Fix groups without search, candidate generation, refinement or evaluation.

Reuse S3 candidate-index-0 exact byte/formula evidence. Else execute only
audited AST/string helpers extracted from pinned source; no geosolver imports.
"""
import ast
import copy
import csv
import hashlib
import json
import re
from fractions import Fraction
from functools import lru_cache

from prepare_common import IMPL, OUT, REPO, STAGE, identity, save, sha, source_manifest


def syntax_helpers():
    ns = dict(ast=ast, copy=copy, hashlib=hashlib, re=re,
              Fraction=Fraction, lru_cache=lru_cache)
    used = {}

    class NoProductImports(ast.NodeTransformer):
        def visit_ImportFrom(self, node):
            assert node.module.startswith('geosolver.'), ast.unparse(node)
            return None  # Dependencies are the same extracted pure functions.

    requested = {
        'problem/expression_source.py': ['annotate_source', 'source_expression'],
        'engine/standard/problem/zero_test_source.py': ['rational_constant', 'zero_test_call'],
        'engine/standard/problem/tangency_contacts.py': ['_parse', 'contact_tangency_source', 'distance_contact_sources'],
        'engine/standard/refinement/s3_tangency.py': ['distance_radius_sources'],
        'engine/standard/refinement/mpmath_refiner.py': ['_zero_constraint_plans'],
    }
    for relative, names in requested.items():
        path = IMPL / relative
        tree = ast.parse(path.read_text())
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        assert {n.name for n in nodes} == set(names)
        used[relative] = dict(sha256=sha(path), functions=[
            dict(name=n.name, line=n.lineno, end_line=n.end_lineno,
                 source=ast.get_source_segment(path.read_text(), n)) for n in nodes])
        module = NoProductImports().visit(ast.Module(body=nodes, type_ignores=[]))
        exec(compile(ast.fix_missing_locations(module), str(path), 'exec'), ns)
    # Exactly the zero predicate of _is_zero_target for DSL JSON scalar values.
    # No mpmath import/arithmetic. String zero handling is intentionally literal.
    ns['_is_zero_target'] = lambda x: x.strip() == '0' if isinstance(x, str) else x == 0
    ns['_BINARY_ARITY'] = 2
    return ns, used


def syntax_evidence(dsl, helpers):
    constructions = tuple((c['name'], c['expression']) for c in dsl['constructions'])
    # The only construction-contract rewrite in these inputs is exclude->far.
    # contact_tangency_source's Intersect proof uses positional args only, so
    # that rewrite cannot change it. Incidence lowering adds determinant rows,
    # never IsTangent/Distance/OnCircle/OnLine incidence proofs.
    assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                   and n.func.id in {'Tangent', 'TangentLine'}
                   for _, expr in constructions for n in ast.walk(ast.parse(expr, mode='eval')))
    for c in dsl['conditions']:
        if 'predicate' in c:
            tree = ast.parse(c['predicate'], mode='eval')
            assert not any(isinstance(n, ast.Eq) or
                           isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                           and n.func.id in {'Eq', 'AssumeEq'}
                           for n in ast.walk(tree)), 'logical equality lowering needs a new audit'
    equalities = tuple((c['left'], str(c['right'])) for c in dsl['conditions']
                       if c.get('operator') == '=')
    # Numeric JSON RHS is preserved by the adapter; string RHS stays a string.
    targets = tuple(c['right'] for c in dsl['conditions'] if c.get('operator') == '=')
    constraints = tuple(left for left, _ in equalities)
    plans = helpers['_zero_constraint_plans'](constraints, targets)
    rows = []
    for index, (kind, (left, right)) in plans.items():
        if kind == 'istangent':
            source = helpers['contact_tangency_source'](left, right, constructions, equalities)
            rows.append(dict(equality_index=index, lhs=constraints[index],
                             contact_source=source))
    distance_t2 = helpers['distance_contact_sources'](constructions, equalities)
    distance_t1 = helpers['distance_radius_sources'](constructions, equalities)
    no_contact = not any(r['contact_source'] is not None for r in rows) and not distance_t2
    # A noncontact Distance=radius rewrite can still differ between T1/T2.
    # Preserve this fact instead of claiming that absence alone proves equality.
    distance_same = distance_t1 == distance_t2
    return dict(method='syntax-only exact pinned contact helpers; no coordinates or candidates evaluated',
                no_T2_contact_expression=no_contact,
                equalities=[dict(index=i, lhs=a, rhs=b) for i, (a, b) in enumerate(equalities)],
                IsTangent_rows=rows, T2_distance_contact_sources=distance_t2,
                T1_distance_radius_sources=distance_t1,
                distance_replacements_identical=distance_same,
                formula_identity_proven=no_contact and distance_same,
                applies_to='all points, hence also candidate index 0 (even when no saved first candidate exists)',
                lowering_audit='no Tangent/TangentLine constructions or logical equality guards; Intersect exclude->far is immaterial to positional-argument incidence proof; added OnSegment determinant rows are mode-independent')


def main():
    manifest = source_manifest()  # abort on changed implementation
    helpers, used = syntax_helpers()
    targets = json.loads((OUT / 'targets.json').read_text())['targets']
    check_path = STAGE / 'S3/switch-check.json'
    checks = json.loads(check_path.read_text())
    assert checks['source_hash'] == manifest['source_hash']
    checks = {identity(c['case_id']): c for c in checks['cases']}
    classification_path = STAGE / 'S5/classification.csv'
    with classification_path.open(newline='') as f:
        classification = {identity(c['case_id']): c for c in csv.DictReader(f)}
    explicit = {identity(c) for c in ['AIME-2018-II-14', 'JMO-2013-PRE-05',
                                     'JMO-2024-PRE-06', 'HMMT-2023-FEB-GEO-07']}
    p_cases = {k for k, c in classification.items() if c['type'] == 'P'}
    records, groups = [], {k: [] for k in ['接点効果群', '同式群', 'その他']}
    for t in targets:
        key = t['identity']
        assert sha(REPO / t['dsl_path']) == t['sha256']
        if key in checks:
            c = checks[key]
            assert c['candidate_index'] == 0
            def formulas(mode):
                return [(r['constraint_index'], r['observed']) for r in c['modes'][mode]['constraints']]
            equal = c['T1_T2_residual_vector_bytes_identical'] and formulas('T1') == formulas('T2')
            evidence = dict(method='S3/check_stage1.py existing candidate-index-0 byte and formula comparison',
                candidate_index=0, candidate_uid=c['candidate_uid'],
                initial_pickle_sha256=c['initial_pickle_sha256'], dps=c['dps'],
                residual_bytes_identical=c['T1_T2_residual_vector_bytes_identical'],
                formulas_identical=formulas('T1') == formulas('T2'),
                modes=c['modes'])
        else:
            evidence = syntax_evidence(json.loads((REPO / t['dsl_path']).read_text()), helpers)
            # Requested syntax criterion. Also record stricter formula identity.
            equal = evidence['no_T2_contact_expression']
        effect = key in explicit or key in p_cases
        group = '接点効果群' if effect else '同式群' if equal else 'その他'
        groups[group].append(t['case_id'])
        records.append(dict(case_id=t['case_id'], identity=key, group=group,
            contact_effect_reason=('S5 classification.csv type=P' if key in p_cases else
                                   'explicit preregistration-13 contact case' if key in explicit else None),
            same_formula_criterion=equal, evidence=evidence))
    save('groups.json', dict(stage='S6 preparation only', target_count=len(targets),
        priority=['接点効果群', '同式群', 'その他'],
        rule='接点効果群=S5 type P + four explicit IDs; 同式群=existing index-0 T1/T2 residual bytes and observed formulas equal OR syntax has no T2 contact equation; effect group takes priority',
        script_sha256=sha(OUT / 'classify_groups.py'),
        source_files_sha256={str(p.relative_to(REPO)): sha(p) for p in
            [classification_path, check_path, STAGE / 'S3/check_stage1.py', OUT / 'targets.json']},
        source_hash=manifest['source_hash'], group_counts={k:len(v) for k,v in groups.items()},
        groups=groups, cases=records))
    save('grouping-evidence.json', dict(extracted_syntax_helpers=used,
        caveat='No new numerical byte check: S3 uses saved first-candidate evidence; syntax proof is independent of candidate availability. No target values, errors, sigma or run results consulted.',
        syntax_formula_discrepancies=[r['case_id'] for r in records
            if r['evidence'].get('no_T2_contact_expression') and not r['evidence']['formula_identity_proven']],
        solver_executed=False, refinement_executed=False, seeds_executed=[]))
    save('source-hashes.json', manifest)
    print('S6 groups:', {k:len(v) for k,v in groups.items()})


if __name__ == '__main__':
    main()
