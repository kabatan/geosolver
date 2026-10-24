"""Copy completed iteration coordinates without evaluating the objective in-clock."""
import ast
import inspect
import json
import pickle
import sys
import textwrap
import time

from mpmath import mp


class Observer:
    def __init__(self):
        self.rows = []
        self.uid = None
        self.attempt = 0
        self.seq = 0

    def record(self, point, phase, attempt=0, iteration=None, stage_dps=None):
        self.rows.append(dict(source_uid=self.uid, sequence=self.seq, phase=phase,
                              attempt=attempt, iteration=iteration, dps=mp.dps, stage_dps=stage_dps,
                              point=tuple(point), monotonic=time.monotonic()))
        self.seq += 1

    def begin(self, candidate):
        from geosolver.engine.standard.precision.type_guards.boundary_float_to_mpf import boundary_float_to_mpf, BoundaryOrigin
        self.uid, self.seq = candidate.candidate_uid, 0
        self.record([boundary_float_to_mpf(v, origin=BoundaryOrigin.INITIAL_POINT)
                     for v in candidate.x_float], "initial")

    def finish(self, candidates):
        for c in candidates:
            self.record(c.x_hp, "final:" + c.candidate_uid)

    def install(self):
        from geosolver.engine.standard.refinement.mpmath_refiner import MpmathRefiner
        import mpmath.calculus.optimization as opt
        original = MpmathRefiner._run_stage
        tree = ast.parse(textwrap.dedent(inspect.getsource(original)))
        fn = tree.body[0]
        fn.decorator_list = []
        matches = [n for n in ast.walk(fn) if isinstance(n, ast.For)
                   and isinstance(n.target, ast.Name) and n.target.id == "_"]
        assert len(matches) == 1
        loop = matches[0]
        note = ast.parse('_s3_observe(current, "lm_iteration", iteration=_, stage_dps=dps)').body[0]
        loop.body = [ast.Try(body=loop.body, handlers=[], orelse=[], finalbody=[note])]
        idx = fn.body.index(loop)
        fn.body.insert(idx, ast.parse('_s3_observe(current, "lm_stage_initial", stage_dps=dps)').body[0])
        ast.fix_missing_locations(tree)
        namespace = dict(original.__globals__, _s3_observe=self.record)
        exec(compile(tree, "<S3 LM observation only>", "exec"), namespace)
        MpmathRefiner._run_stage = namespace[fn.name]
        # Wrap the original generator, retaining its original maxsteps and yields.
        classes = {c for c in opt.str2solver.values() if isinstance(c, type)} | {opt.MDNewton}
        for cls in classes:
            original_iter = cls.__iter__
            observer = self

            def observed(solver, _original=original_iter, _name=cls.__name__):
                observer.attempt += 1
                attempt = observer.attempt
                caller = sys._getframe(1)
                assemble = None
                while caller is not None:
                    if caller.f_code.co_name == "_run_rank_aware_findroot":
                        assemble = caller.f_locals.get("assemble_point")
                        break
                    caller = caller.f_back
                for index, pair in enumerate(_original(solver)):
                    point = pair[0]
                    if isinstance(point, (tuple, list, mp.matrix)):
                        point = tuple(point)
                    else:
                        point = (point,)
                    if assemble is not None:
                        point = assemble(point)
                    observer.record(point, "newton:" + _name, attempt, index)
                    yield pair

            cls.__iter__ = observed


def measure_trace(directory, arm, evaluator, refs, save, textnum):
    started = time.monotonic()
    measured = json.loads((directory / (arm + ".measure.json")).read_text())["rows"]
    usable = [r for r in measured if r.get("absolute_error") is not None]
    with mp.workdps(700):
        best = min(usable, key=lambda r: mp.mpf(r["absolute_error"])) if usable else None
    if best is None:
        save(arm + ".iteration-errors.json", {"rows": [], "missing": "best candidate unavailable"})
        return
    with (directory / (arm + ".iterations.pkl")).open("rb") as f:
        traces = pickle.load(f)
    selected = [r for r in traces if r["source_uid"] == best["source_uid"]
                and (not r["phase"].startswith("final:") or r["phase"] == "final:" + best["candidate_uid"])]
    rows = []
    from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
    with mp.workdps(700), high_precision_mode():
        for trace in selected:
            row = {k: v for k, v in trace.items() if k != "point"}
            row.update(arm=arm, best_candidate_uid=best["candidate_uid"])
            try:
                answer = evaluator.evaluate_answer_hp(trace["point"], precision=700).answer_hp
                if answer is None or not mp.isfinite(answer) or not refs:
                    raise ValueError("answer/reference unavailable")
                error = min(abs(answer-ref) for ref in refs)
                digits = min(mp.mpf(600), -mp.log10(error)) if error else mp.mpf(600)
                row.update(answer=textnum(answer), absolute_error=textnum(error), error_digits=float(str(digits)))
            except Exception as e:
                row["error"] = repr(e)
            rows.append(row)
    save(arm + ".iteration-errors.json", {"seconds": time.monotonic()-started, "rows": rows,
         "best_candidate_uid": best["candidate_uid"], "source_uid": best["source_uid"]})
