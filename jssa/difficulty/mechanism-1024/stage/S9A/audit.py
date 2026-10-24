"""Read-only source/receipt audit; never launches a solver or reads quality."""
import ast
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def file_hashes(root):
    return {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts}


s = json.loads((OUT / 'source-hashes.json').read_text())
m = json.loads((OUT / 'pre-smoke-hashes.json').read_text())
c = json.loads((OUT / 'configs.json').read_text())
for p, expected in m['files_sha256'].items():
    assert sha(OUT / p) == expected, p
for root_key, files_key in [('base_source', 'base_files_sha256'),
                            ('patched_source', 'patched_files_sha256'),
                            ('frozen_source', 'frozen_files_sha256')]:
    assert file_hashes(Path(s[root_key])) == s[files_key], root_key
for p, value in s['protected_files'].items():
    contents = [(Path(s[k]) / p).read_bytes() for k in ['base_source', 'patched_source', 'frozen_source']]
    assert contents[0] == contents[1] == contents[2]
    assert sha(Path(s['patched_source']) / p) == value['sha256']

# Substitute only the three new flags=false, then compare the default stage AST.
relative = 'src/geosolver/engine/standard/refinement/mpmath_refiner.py'

def stage(root):
    tree = ast.parse((Path(root) / relative).read_text())
    return next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == '_run_stage')


class DefaultStage(ast.NodeTransformer):
    def visit_If(self, node):
        if (isinstance(node.test, ast.Call) and isinstance(node.test.func, ast.Name)
                and node.test.func.id == 'ablated' and node.test.args[0].value == 'NEWTON_ONLY'):
            return []
        if (isinstance(node.test, ast.UnaryOp) and isinstance(node.test.op, ast.Not)
                and isinstance(node.test.operand, ast.Name) and node.test.operand.id == 'fixed_damping'):
            return [self.visit(n) for n in node.body]
        return self.generic_visit(node)

    def visit_Assign(self, node):
        if any(isinstance(n, ast.Name) and n.id == 'fixed_damping' for n in node.targets):
            return []
        return self.generic_visit(node)

    def visit_IfExp(self, node):
        if (isinstance(node.test, ast.Call) and isinstance(node.test.func, ast.Name)
                and node.test.func.id == 'ablated' and node.test.args[0].value == 'ZERO_LM_DAMPING'):
            return self.visit(node.orelse)
        return self.generic_visit(node)


assert ast.dump(stage(s['base_source']), include_attributes=False) == ast.dump(
    DefaultStage().visit(stage(s['patched_source'])), include_attributes=False)
for p in Path(s['patched_source']).rglob('*.py'):
    ast.parse(p.read_text(), filename=str(p))

rows = {arm: json.loads((OUT / 'smoke' / (arm + '.json')).read_text()) for arm in c['arms']}
for arm, row in rows.items():
    assert row['environment'] == c['arms'][arm]
    assert row['calls'].get('_run_stage') == 1
    assert row['process_state'] == 'stage_call_returned'
    assert row['quality_fields_recorded'] is False
    for forbidden in ['answer', 'residual_norm', 'converged', 'correct_digits', 'phase_history', 'x_hp']:
        assert forbidden not in row
assert rows['R0']['calls']['compute_levenberg_marquardt_step'] > 0
assert rows['R0']['adaptive_lambda_update_lines'] > 0
assert rows['R1']['lambda_values'] == ['0.0']
assert rows['R2']['lambda_values'] == ['1.0e-6']
for arm in ['R1', 'R2']:
    assert rows[arm]['calls']['compute_levenberg_marquardt_step'] > 0
    assert rows[arm]['adaptive_lambda_update_lines'] == 0
assert rows['R3']['calls'].get('compute_levenberg_marquardt_step', 0) == 0
assert rows['R3']['calls'].get('run_line_search', 0) == 0
assert rows['R3']['calls']['_run_findroot_closure'] == 1
assert rows['R3']['newton_linear_step_attempts'] > 0
jobs = json.loads((OUT / 'smoke/driver.json').read_text())
assert len(jobs['jobs']) == 4 and jobs['max_parallel'] == 1
assert all(j['returncode'] == 0 and not j['outer_timeout'] and j['process_seconds'] < 10 for j in jobs['jobs'])
report = dict(source_files_unchanged_after_smoke=True, protected_files_byte_identical=len(s['protected_files']),
              r0_default_stage_ast_identical_to_base=True, patched_python_ast_parse_passed=True,
              routing_and_damping_observations_passed=True,
              original_driver_assertions_passed=False,
              original_driver_failure="assert len(rows['R0']['lambda_values']) > 1",
              limitation='Only one LM direction call per arm was observed. R0 adaptive update line was executed, but a second linear solve using the updated lambda was not observed. No repeat was run.',
              quality_inspected=False, measurement_run=False, retries=0,
              smoke_calls_per_arm={arm: row['calls']['_run_stage'] for arm, row in rows.items()})
(OUT / 'smoke/checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(report, ensure_ascii=False))
