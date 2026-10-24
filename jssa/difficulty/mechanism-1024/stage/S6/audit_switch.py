"""Static source evidence only. No imported product modules or subprocesses."""
import ast
from prepare_common import IMPL, save, sha, source_manifest


def main():
    manifest = source_manifest()
    wanted = {
        'engine/standard/refinement/s3_tangency.py': ['tangency_mode', 'distance_radius_sources'],
        'engine/standard/refinement/mpmath_refiner.py': [
            '_smooth_zero_constraint_residuals', '_select_rank_revealing_subsystem',
            '_run_findroot_closure', '_zero_constraint_plans', '_is_zero_target',
            '_residual_vector_for_stage', '_run_stage', '_apply_post_lm_closure_polish'],
        'engine/standard/refinement/analytic_jacobian.py': ['derivative_plan', '_plan', 'compile_jacobian'],
        'engine/standard/evaluation/final_verifier.py': ['verify_final_candidate', '_variable_scales'],
        'engine/standard/evaluation/verification_numerics.py': [
            '_smooth_zero_equation', 'prepare_equations', 'linearization', 'correction', 'differentiate'],
        'engine/standard/evaluation/ir_evaluator.py': ['verification_equations'],
        'engine/standard/problem/analysis_plan.py': ['integer_specs', 'mathematical_bounds_at_precision'],
        'engine/standard/orchestration/assemble_exact_results.py': ['_verify_revision', 'assemble_exact_results'],
        'engine/standard/orchestration/run_external_pipeline.py': [
            '_run_pipeline_stage', '_complete_pipeline_stage', '_run_ordered_search_attempts',
            '_should_select_fallback_attempt'],
        'engine/standard/exact_assembly/identify_answer.py': ['identify_answer'],
        'geometry/mp/signed_tangency.py': ['signed_tangency'],
        'runtime/symbolic_operations.py': ['dispatch'],
    }
    records = {}
    for relative, names in wanted.items():
        p = IMPL / relative
        source = p.read_text()
        tree = ast.parse(source)
        functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name in names]
        assert set(names) == {n.name for n in functions}, (relative, names)
        records[relative] = dict(sha256=sha(p), functions=[
            dict(name=n.name, line=n.lineno, end_line=n.end_lineno,
                 source=ast.get_source_segment(source, n),
                 call_sites=[dict(line=c.lineno, call=ast.unparse(c.func))
                             for c in ast.walk(n) if isinstance(c, ast.Call)])
            for n in functions])
    occurrences = []
    for p in sorted(IMPL.rglob('*.py')):
        if '__pycache__' in p.parts:
            continue
        for i, line in enumerate(p.read_text().splitlines(), 1):
            if any(token in line for token in ['GEOSOLVER_S3_TANGENCY_MODE',
                                               'tangency_mode(', 'refinement_jacobian']):
                occurrences.append(dict(path=str(p.relative_to(IMPL)), line=i, text=line))
    save('switch-scope-evidence.json', dict(source_hash=manifest['source_hash'],
        method='AST/text reads only; graph resolution is reviewed in switch-scope.md; import is distinguished from runtime call',
        functions=records, switch_and_dispatch_occurrences=occurrences,
        solver_executed=False, final_verification_executed=False))
    print('S6 static switch evidence recorded')


if __name__ == '__main__':
    main()
