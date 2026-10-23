"""Native MINPACK event tracing and preregistered mechanism interventions.

Run with PYTHONDONTWRITEBYTECODE=1 and one BLAS thread. All patches are local
to this module's process and restored in finally; src/ is never changed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from scipy.optimize import _minpack

from common import (HERE, case_context, classify, clean, feasible,
                    reference_values, smb, ExternalPipelineConfig, write_json)

ARMS = ("B", "S", "J", "N", "C", "CS")
SEED = 17007


def same(a, b):
    return np.array_equal(np.asarray(a), np.asarray(b))


class NativeTrace:
    """Infer accepted points from native jac bases/returned x, not FD probes."""

    def __init__(self, ev, width, arm):
        self.ev, self.width, self.arm = ev, width, arm
        self.events = []
        self.trials = []
        self.pending = []
        self.base = None
        self.last_fun = None
        self.base_row = None
        self.jacs = []
        self.issues = []

    def row(self, x, f):
        return {"x": np.asarray(x).tolist(), "eq_ss": float(f[:-2] @ f[:-2]),
                "guard": float(f[-2]), "hard": float(f[-1]),
                "ss": float(f @ f), "F": feasible(self.ev, x),
                "all_sentinel": bool(np.all(f == smb._NONFINITE_RESIDUAL_PENALTY))}

    def resolve(self, accepted_x, reason):
        if not self.pending:
            if self.base is not None and not same(accepted_x, self.base):
                self.issues.append("base_changed_without_pending_trial")
            return
        matched = same(self.pending[-1]["x"], accepted_x)
        unchanged = same(self.base, accepted_x)
        if not matched and not unchanged:
            self.issues.append("base_or_final_not_last_trial_or_old_base")
        for i, trial in enumerate(self.pending):
            if trial["same_coordinate"]:
                trial["decision"] = "unknown"
                trial["decision_from"] = "same_coordinate_ambiguous"
                continue
            if matched:
                trial["decision"] = "accepted" if i == len(self.pending)-1 else "rejected"
            elif unchanged:
                trial["decision"] = "rejected"
            else:
                trial["decision"] = "unknown"
            trial["decision_from"] = reason
        self.pending.clear()

    def wrap_fun(self, fun):
        def logged(x, *args):
            f = np.asarray(fun(x, *args))
            row = self.row(x, f)
            self.last_fun = row
            event = {"type": "fun", **row}
            self.events.append(event)
            if self.base is None:
                event["role"] = "initial_or_preflight"
            else:
                event["role"] = "trial"
                event["trial"] = len(self.trials)
                trial = {"index": len(self.trials), **row,
                         "base": self.base_row.copy(),
                         "same_coordinate": same(x, self.base),
                         "step_scaled": float(np.linalg.norm((x-np.asarray(self.base))/self.width)),
                         "decision": "unknown"}
                self.trials.append(trial)
                self.pending.append(trial)
            return f
        return logged

    def wrap_jac(self, jac):
        def logged(x, *args):
            self.resolve(x, "next_native_jac")
            if self.last_fun is not None and same(x, self.last_fun["x"]):
                self.base_row = self.last_fun.copy()
            elif self.base is None or not same(x, self.base):
                self.issues.append("jac_base_has_no_matching_fun")
                self.base_row = {"x": np.asarray(x).tolist(), "F": feasible(self.ev, x)}
            self.base = np.asarray(x).copy()
            J = np.asarray(jac(x, *args))
            before = J[-1].copy()
            if self.arm == "J":
                J = J.copy()
                J[-1, :] = 0.0
            event = {"type": "jac", "x": self.base.tolist(),
                     "hard_jac_raw": before.tolist(), "hard_jac_used": J[-1].tolist(),
                     "hard_jac_raw_max": float(np.max(np.abs(before))),
                     "F": self.base_row.get("F"),
                     "col_norm": np.linalg.norm(J, axis=0).tolist()}
            self.events.append(event)
            self.jacs.append(event)
            return J
        return logged

    def finish(self, ans):
        x, info, raw_status = ans
        self.resolve(x, "returned_x")
        self.raw_status = int(raw_status)
        self.nfev = int(info["nfev"])
        self.njev = int(info["njev"])

    def summary(self, full=False):
        counts = Counter(t["decision"] for t in self.trials)
        crossing = [t for t in self.trials if t["base"].get("F") and not t["F"]]
        descent = [t for t in crossing if t["eq_ss"] < t["base"].get("eq_ss", -1)]
        reject_descent = [t for t in descent if t["decision"] == "rejected"]
        accepted = [t for t in self.trials if t["decision"] == "accepted"]
        out = {"raw_info": getattr(self, "raw_status", None),
               "native_nfev": getattr(self, "nfev", None),
               "native_njev": getattr(self, "njev", None),
               "fun_calls_including_preflight": sum(e["type"] == "fun" for e in self.events),
               "jac_calls_including_preflight": len(self.jacs),
               "counts": dict(counts), "issues": self.issues,
               "same_coordinate_unknown": sum(t["same_coordinate"] for t in self.trials),
               "F_to_I_trials": len(crossing), "F_to_I_eq_descent_trials": len(descent),
               "F_to_I_eq_descent_rejected": len(reject_descent),
               "F_to_I_eq_descent_rejected_hard_increase": sum(t["hard"]**2 > t["base"]["hard"]**2 for t in reject_descent),
               "F_to_I_eq_descent_rejected_other_ss_decrease": sum(t["eq_ss"]+t["guard"]**2 < t["base"]["eq_ss"]+t["base"]["guard"]**2 for t in reject_descent),
               "accepted_I": sum(not t["F"] for t in accepted),
               "accepted_all_F": all(t["F"] for t in accepted),
               "hard_jac_raw_max": max((e["hard_jac_raw_max"] for e in self.jacs), default=0),
               "last_native_jac": self.jacs[-1] if self.jacs else None,
               "tail": self.trials[-8:]}
        if full:
            out.update(events=self.events, trials=self.trials)
        return out


def solve(context, start, k, arm, full=False):
    case, bundle, ev, raw, bounds, lo, width = context
    refs = reference_values(case["answer"])
    trace = NativeTrace(ev, width, arm)
    orig_lmder = _minpack._lmder
    orig_hard = smb._evaluate_hard_feasibility_penalty
    orig_ls = smb.least_squares
    status = {}

    def traced_lmder(*args, **kwargs):
        assert not kwargs and len(args) == 12
        args = list(args)
        args[0] = trace.wrap_fun(args[0])
        args[1] = trace.wrap_jac(args[1])
        if arm in ("S", "CS"):
            args[6] = 0.0  # ftol; xtol is args[7], unchanged
            args[8] = 0.0  # gtol
        ans = orig_lmder(*args)
        trace.finish(ans)
        if ans[2] in (6, 7, 8):
            # SciPy's public API prevents these codes at its tolerance check.
            # Keep the raw code in the trace and only adapt the return mapping.
            status["raw_info_remapped"] = int(ans[2])
            return ans[0], ans[1], {6: 1, 7: 2, 8: 4}[ans[2]]
        return ans

    def logged_ls(*args, **kwargs):
        try:
            ans = orig_ls(*args, **kwargs)
        except Exception as ex:
            status["exception"] = repr(ex)
            raise
        status.update(status=int(ans.status), message=str(ans.message), nfev=int(ans.nfev),
                      cost=float(ans.cost), optimality=float(ans.optimality))
        return ans

    _minpack._lmder = traced_lmder
    smb.least_squares = logged_ls
    if arm == "N":
        smb._evaluate_hard_feasibility_penalty = lambda **kwargs: 0.0
    elif arm in ("C", "CS"):
        smb._evaluate_hard_feasibility_penalty = lambda **kwargs: 1000.0
    telemetry = smb._SearchTelemetry()
    config = ExternalPipelineConfig.production_baseline_tier(seed=SEED, total_time_budget_sec=180).search
    t0 = time.monotonic()
    try:
        cand = smb._collect_local_start_record(
            bundle=bundle, evaluator=ev, bounds=bounds, config=config,
            seed=SEED, start_index=k, start=np.asarray(start, dtype=float),
            deadline_monotonic=t0+10.0, telemetry=telemetry)
        result = classify(ev, cand, refs)
    except (smb._SearchDeadlineExceeded, TimeoutError):
        result = {"cls": "timeout"}
    except Exception as ex:
        result = {"cls": "error", "error": repr(ex)}
    finally:
        _minpack._lmder = orig_lmder
        smb.least_squares = orig_ls
        smb._evaluate_hard_feasibility_penalty = orig_hard
    result.update(seconds=time.monotonic()-t0, evaluations=telemetry.evaluation_count,
                  optimizer=status, native=trace.summary(full))
    return clean(result)


def one_case(old):
    context = case_context(old["id"])
    records = []
    for rec in old["records"]:
        k = rec["k"]
        arms = ARMS[k % len(ARMS):] + ARMS[:k % len(ARMS)]
        new = {"k": k, "F": rec["F"], "start": rec["start"]}
        for arm in arms:
            new[arm] = solve(context, rec["start"], k, arm)
        records.append(new)
    return {"id": old["id"], "wall_group": old["wall_group"],
            "selection": old["selection"], "records": records}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("trace", "all"), required=True)
    args = parser.parse_args()
    prereg = (HERE / "preregistration-resume.md").read_bytes()
    metadata = {"preregistration_sha256": hashlib.sha256(prereg).hexdigest(),
                "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "arms": ARMS, "max_nfev": smb._LM_MAX_NFEV}
    if args.stage == "trace":
        context = case_context("AIME-2010-II-14")
        results = []
        for k in (2, 3, 5):
            old = next(r for r in context[3]["records"] if r["k"] == k)
            result = {"k": k, "start": old["start"]}
            for arm in ARMS:
                result[arm] = solve(context, old["start"], k, arm, full=True)
                n = result[arm]["native"]
                print(k, arm, result[arm]["cls"], result[arm]["optimizer"],
                      {key: n[key] for key in ("counts", "issues", "native_nfev", "fun_calls_including_preflight")}, flush=True)
            results.append(result)
        write_json(HERE / "native-aime-traces.json", {**metadata, "records": results})
    else:
        source = json.loads((HERE / "intervention.json").read_text())
        target = HERE / "mechanism-data"
        target.mkdir(exist_ok=True)
        write_json(target / "manifest.json", metadata)
        with ProcessPoolExecutor(max_workers=4) as pool:
            for result in pool.map(one_case, source):
                (target / f"{result['id']}.json").write_text(
                    json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
                print(result["id"], {a: sum(r[a]["cls"] == "hit" for r in result["records"]) for a in ARMS}, flush=True)


if __name__ == "__main__":
    main()
