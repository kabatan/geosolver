"""Experiment-only probe: when the primary search finishes and refinement starts, refine the SAME candidates
with and without the signed/smooth residual rewrite (GEOSOLVER_ABLATE_NO_SIGNED_TANGENCY), record digits and time,
then continue the normal pipeline with the default (rewrite on) result."""
import json
import os
import sys
import time

OUT = os.environ.get("TANGENCY_PROBE_OUT")
if OUT:
    try:
        import mpmath as mp
        import geosolver.engine.standard.orchestration.run_external_pipeline as m

        _orig = m.run_refinement
        _state = {"done": False}

        def _summ(res, seconds, deadline_hit):
            rows = []
            for c in res.candidates:
                try:
                    r = mp.mpf(c.residual_norm_hp)
                    digits = float(-mp.log10(r)) if r > 0 else None
                except Exception:
                    digits = None
                rows.append(
                    {
                        "candidate_id": int(c.candidate_id),
                        "status": str(c.refinement_status),
                        "residual_digits": digits,
                        "hard_feasible": bool(getattr(c, "hard_feasible", False)),
                    }
                )
            return {
                "seconds": seconds,
                "attempted": res.attempted_count,
                "converged": res.converged_count,
                "hard_feasible": res.hard_feasible_count,
                "deadline_hit": deadline_hit,
                "candidates": rows,
            }

        def _wrapped(**kw):
            if _state["done"]:
                return _orig(**kw)
            _state["done"] = True
            budget = float(os.environ.get("TANGENCY_PROBE_VARIANT_SEC", "90"))
            out = {"n_input_candidates": len(kw["search_result"].candidates)}
            order = os.environ.get("TANGENCY_PROBE_ORDER", "off_first")
            variants = [("without_signed_rewrite", True), ("with_signed_rewrite", False)]
            if order == "on_first":
                variants.reverse()
            out["order"] = order
            final = None
            for name, off in variants:
                if off:
                    os.environ["GEOSOLVER_ABLATE_NO_SIGNED_TANGENCY"] = "1"
                else:
                    os.environ.pop("GEOSOLVER_ABLATE_NO_SIGNED_TANGENCY", None)
                args = dict(kw)
                args["deadline_monotonic"] = time.monotonic() + budget
                t0 = time.perf_counter()
                res = None
                try:
                    res = _orig(**args)
                    out[name] = _summ(res, time.perf_counter() - t0, time.monotonic() >= args["deadline_monotonic"])
                except Exception as e:
                    out[name] = {"error": repr(e)}
                if not off and res is not None:
                    final = res
            os.environ.pop("GEOSOLVER_ABLATE_NO_SIGNED_TANGENCY", None)
            with open(OUT, "w") as f:
                json.dump(out, f)
            return final if final is not None else _orig(**kw)

        m.run_refinement = _wrapped
    except Exception as e:  # never break the solver
        sys.stderr.write("probe install failed: %r\n" % (e,))
