"""S4 reference function; only 200 -> 300 digit acceptance changed."""
from s4_helpers import *
def make_reference(item,bundle,evaluator,folder):
    if item['selection'] is None:
        return dict(status='reference_unavailable',reason='S1両構成に凍結版の最終検証通過候補なし')
    from geosolver.runtime.deadline import runtime_session
    from geosolver.engine.standard.refinement.mpmath_refiner import MpmathRefiner, _run_findroot_closure, _convert_problem_bounds
    from geosolver.engine.standard.interpreter.answer import _eval_exact_to_mpf
    deadline=time.monotonic()+180
    with mp.workdps(700):
        references=[_eval_exact_to_mpf(s,700) for s in item['reference_expressions']]
    if not all(v is not None and mp.isfinite(v) for v in references):
        return dict(status='reference_unavailable',reason='独立参照式を評価できず')
    with mp.workdps(180), high_precision_mode(), runtime_session(deadline):
        values=[mp.mpf(s) for s in item['selection']['values']]
        verification=verify_final_candidate(evaluator=evaluator,values=values)
        witness=dict(verified=verification.verified,status=verification.status,
                     precision_dps=verification.precision_dps,values=[num(v,710) for v in verification.values])
        save(folder/'verification.json',witness)
    if not verification.verified:
        return dict(status='reference_unavailable',reason='固定した候補の再検証不通過',verification=witness)
    with mp.workdps(620),high_precision_mode(),runtime_session(deadline):
        closed=_run_findroot_closure(evaluator=evaluator,start_point=list(verification.values),
            bounds=_convert_problem_bounds(bundle),dps=620,target_residual=mp.mpf('1e-580'),
            solver_tolerance=mp.mpf('1e-1160'),max_steps=1240,deadline_monotonic=deadline,
            residual_fn=partial(MpmathRefiner()._residual_vector_for_stage,bundle,evaluator,smooth_zero_constraints=True),
            one_sided_at_cusp=any('Angle(' in str(c) for c in bundle.spec.constraints))
        if closed is None:
            return dict(status='reference_unavailable',reason='凍結版の一度の620桁closureが残差基準に到達せず',verification=witness)
        coordinates=[num(v,620) for v in closed[0]]
        point=[mp.mpf(s) for s in coordinates]
        residual=evaluator.evaluate_hp_residual(point,precision=620)
        norm=mp.sqrt(mp.fsum(v*v for v in residual.residual_vector))
        hard=evaluator.evaluate_hp_hard_feasibility(point,precision=620,include_margins=True)
        ev=evaluator.evaluate_answer_hp(point,precision=620)
        result=dict(coordinates=coordinates,var_names=list(bundle.var_names),original_residual_norm=num(norm,40),
            hard_feasible=bool(hard.hard_feasible),evaluation_status=ev.evaluation_status.value,
            refinement_dps=620,stored_significant_digits=620,verification=witness)
        if not hard.hard_feasible or ev.answer_hp is None or norm>mp.mpf('1e-580'):
            return result|dict(status='reference_unavailable',reason='保存座標のhard/residual/target門を通らず')
    with mp.workdps(700),high_precision_mode():
        answer=evaluator.evaluate_answer_hp([mp.mpf(s) for s in coordinates],precision=700).answer_hp
        ref=min(references,key=lambda v:abs(v-answer))
        error=abs(answer-ref); relative=error/max(1,abs(ref))
        result.update(answer=num(answer,700),reference=num(ref,700),absolute_error=num(error,50),
            relative_error=num(relative,50),absolute_digits=num(-mp.log10(error) if error else mp.inf,30))
        if not mp.isfinite(answer) or error>mp.mpf('1e-300') or relative>mp.mpf('1e-300'):
            return result|dict(status='reference_unavailable',reason='目標値と独立参照値の300桁一致を確認できず')
    return result|dict(status='ok')

