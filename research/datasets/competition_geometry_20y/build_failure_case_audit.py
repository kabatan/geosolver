#!/usr/bin/env python3
"""Build the case-by-case audit of strict benchmark failures.

The audit is deliberately generated from the immutable benchmark row, the
source-truth ledger, the manual DSL audit, and the DSL file itself.  Manual
cause labels below only classify the mechanism; they never replace the raw
evidence copied into the JSONL artifact.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
BENCHMARK_PATH = ROOT / "benchmark_results_180s_1core_strict_raw.json"
TRUTH_PATH = ROOT / "exact_truth.jsonl"
MANUAL_PATH = ROOT / "manual_audit.jsonl"
DSL_DIR = ROOT / "dsl"
OUT_JSONL = ROOT / "FAILURE_CASE_AUDIT_STRICT_RAW.jsonl"
OUT_MD = ROOT / "FAILURE_CASE_AUDIT_STRICT_RAW.md"


DECIMAL_NEAR = {
    "AIME-2006-I-07", "AIME-2009-I-05", "AIME-2009-II-10",
    "AIME-2011-I-14", "AIME-2013-II-04", "AIME-2013-II-08",
    "AIME-2015-II-11", "AIME-2015-II-15", "AIME-2016-I-06",
    "AIME-2022-I-03", "AIME-2022-II-11", "AIME-2023-II-09",
    "AIME-2025-II-12", "HMMT-2006-FEB-GEO-01", "HMMT-2006-FEB-GEO-03",
    "HMMT-2006-FEB-GEO-04", "HMMT-2006-FEB-GEO-06", "HMMT-2006-FEB-GEO-07",
    "HMMT-2007-FEB-GEO-02", "HMMT-2008-FEB-GEO-02", "HMMT-2008-FEB-GEO-03",
    "HMMT-2008-FEB-GEO-07", "HMMT-2010-FEB-GEO-01", "HMMT-2012-FEB-GEO-01",
    "HMMT-2013-FEB-GEO-05", "HMMT-2014-FEB-GEO-08", "HMMT-2016-FEB-GEO-04",
    "HMMT-2020-FEB-GEO-02", "HMMT-2023-FEB-GEO-01", "HMMT-2024-FEB-GEO-05",
    "HMMT-2024-FEB-GEO-07", "HMMT-2025-FEB-GEO-08", "JMO-2019-MATHNET-08ya",
    "JMO-2019-PRE-10", "JMO-2022-PRE-04",
}

TARGET_PLUS_EXTRA = {
    "AIME-2006-II-09", "AIME-2014-II-08", "AIME-2018-I-04",
    "HMMT-2007-FEB-GEO-04", "HMMT-2010-FEB-GEO-09",
    "HMMT-2014-FEB-GEO-09", "HMMT-2018-FEB-GEO-05",
    "HMMT-2024-FEB-GEO-03", "JMO-2022-PRE-12",
}
TARGET_PLUS_DECIMAL = {
    "AIME-2011-II-02", "AIME-2020-I-01", "HMMT-2013-FEB-GEO-04",
    "HMMT-2021-FEB-GEO-05", "JMO-2022-MATHNET-08z4",
}
WRONG_EXACT = {
    "HMMT-2014-FEB-GEO-10", "HMMT-2022-FEB-GEO-05",
    "HMMT-2023-FEB-GEO-02", "HMMT-2023-FEB-GEO-04",
    "HMMT-2024-FEB-GEO-10",
}
DECIMAL_WRONG = {"HMMT-2006-FEB-GEO-10", "HMMT-2015-FEB-GEO-04"}
NO_SOLUTION = {
    "AIME-2018-II-12", "AIME-2019-I-06", "AIME-2020-II-15",
    "AIME-2021-I-13", "AIME-2022-II-07", "JMO-2019-MATHNET-08yk",
    "JMO-2019-PRE-08",
}
TIMEOUT = {"AIME-2020-II-13", "JMO-2015-PRE-11"}
EXCEPTION = {"JMO-2013-PRE-08"}


def _read_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    return {
        (row.get("case_id") or row.get("dedupe_key") or row.get("problem_id")): row
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
        for row in [json.loads(line)]
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _short(value: Any, limit: int = 180) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _numeric(value: str) -> Any | None:
    # This is diagnostic-only; strict scoring never uses this value.
    try:
        from exact_scoring import _numeric as exact_numeric

        proxy = exact_numeric(str(value))
        if proxy is None:
            return None
        # Keep SymPy's 100-digit proxy; converting to float would erase the
        # small serialization/refinement error this audit is meant to show.
        return proxy
    except Exception:
        return None


def _best_relative_error(values: list[str], expected: list[str]) -> str | None:
    """Diagnostic relative error, retained at high precision.

    This is not used by strict scoring.  Returning a decimal string rather
    than a Python float is important: otherwise a 1e-17 serialization gap
    rounds to ``0.0`` and hides the very failure being audited.
    """
    try:
        import sympy as sp
        expected_numbers = [x for x in (_numeric(v) for v in expected) if x is not None]
        actual_numbers = [x for x in (_numeric(v) for v in values) if x is not None]
    except Exception:
        return None
    if not expected_numbers or not actual_numbers:
        return None
    best: Any | None = None
    for actual in actual_numbers:
        for target in expected_numbers:
            denom = max(abs(target), 1e-300)
            error = abs(actual - target) / denom
            best = error if best is None else min(best, error)
    return str(sp.N(best, 50)) if best is not None else None


def _cause_defaults(case_id: str, status: str) -> dict[str, Any]:
    if case_id == "HMMT-2014-FEB-GEO-08":
        return {
            "category": "decimal_only_refinement_error",
            "owner": "solver",
            "confidence": "confirmed",
            "cause": "numerical refinement stopped before exact root (relative error is not serialization noise)",
            "evidence_codes": ["E1", "E2"],
            "evidence_detail": (
                "answer_values はdecimal二つだけで、最良相対誤差も約1.71e-10。"
                " exact-identificationだけの表記差ではなく、solverの数値精密化誤差が残っている。"
            ),
        }
    if case_id in DECIMAL_NEAR:
        detail = (
            "Phase C の answer_values がdecimalだけで、厳密式が一つもない。"
            " identify_answer が selected_exact_value を返さない場合に "
            "run_phasec_assembly.py:135-144 が candidate.answer_hp の文字列へフォールバックする。"
            " strict scoring はdecimal-onlyを厳密解集合とは認めない。"
        )
        return {
            "category": "decimal_only_near_exact",
            "owner": "solver",
            "confidence": "confirmed",
            "cause": "exact-identification/serialization failure (decimal fallback)",
            "evidence_codes": ["E1", "E2"],
            "evidence_detail": detail,
        }
    if case_id in TARGET_PLUS_EXTRA:
        return {
            "category": "target_plus_extra_exact",
            "owner": "solver",
            "confidence": "high",
            "cause": "target was found but an extra exact branch was accepted",
            "evidence_codes": ["E1", "E3"],
            "evidence_detail": "raw Phase C set contains the audited target and at least one additional exact value; strict set equality therefore fails.",
        }
    if case_id in TARGET_PLUS_DECIMAL:
        return {
            "category": "target_exact_plus_decimal_extra",
            "owner": "solver",
            "confidence": "high",
            "cause": "target was found, but an additional non-exact numerical branch was emitted",
            "evidence_codes": ["E1", "E2"],
            "evidence_detail": "raw Phase C set contains the audited exact target plus a decimal value that is not an exact symbolic member.",
        }
    if case_id in WRONG_EXACT:
        return {
            "category": "wrong_exact_branch",
            "owner": "mixed",
            "confidence": "high",
            "cause": "an exact but semantically invalid/incorrect branch was accepted",
            "evidence_codes": ["E1", "E3"],
            "evidence_detail": "raw Phase C set contains exact values that are not in the audited exact solution set.",
        }
    if case_id in DECIMAL_WRONG:
        return {
            "category": "wrong_decimal_branch",
            "owner": "solver",
            "confidence": "high",
            "cause": "solver emitted only a numerically wrong decimal branch",
            "evidence_codes": ["E1", "E2"],
            "evidence_detail": "no exact target is present; the nearest numeric output is not the audited target.",
        }
    if case_id in NO_SOLUTION:
        return {
            "category": "no_solution",
            "owner": "solver",
            "confidence": "high",
            "cause": "no accepted Phase C candidate within the 180-second run",
            "evidence_codes": ["E1", "E4"],
            "evidence_detail": "benchmark status is no_solution and Phase C has no answer_values; the detailed mechanism is supplied by the case-specific override below.",
        }
    if case_id in TIMEOUT:
        return {
            "category": "hard_timeout",
            "owner": "solver",
            "confidence": "confirmed",
            "cause": "hard 180-second/one-core budget expired before a Phase C result",
            "evidence_codes": ["E1"],
            "evidence_detail": "benchmark status is timeout, wall_sec is approximately 180.106, and there is no Phase C output. The exact internal search substage cannot be reconstructed from the child artifact alone.",
        }
    if case_id in EXCEPTION:
        return {
            "category": "runtime_exception",
            "owner": "solver",
            "confidence": "confirmed",
            "cause": "uncaught Phase B mpmath findroot/LU TypeError",
            "evidence_codes": ["E1", "E5"],
            "evidence_detail": "benchmark error and an independent direct reproduction show None being used as a matrix index in mpmath LU_decomp during _run_findroot_closure.",
        }
    raise AssertionError(case_id)


OVERRIDES: dict[str, dict[str, Any]] = {
    "AIME-2006-II-09": {
        "owner": "dsl", "confidence": "confirmed",
        "cause": "DSL omits the internal-tangent side-of-line condition",
        "evidence_codes": ["E1", "E3", "E6"],
        "evidence_detail": "The statement says common internal tangents. DSL has only four IsTangent equations and slope-sign guards; it does not constrain the two circle centers to opposite sides of each tangent. The extra exact roots are therefore external/other tangent branches of the encoded equations.",
    },
    "AIME-2014-II-08": {
        "owner": "solver", "confidence": "confirmed",
        "cause": "strict-radius boundary branch leaked through numerical guard handling",
        "evidence_codes": ["E1", "E3"],
        "evidence_detail": "DSL explicitly has e>0 and 3e<2, yet Phase C emits exact 0 and an additional decimal branch. The exact zero is the radius-degenerate boundary, so the encoded strict guard was not respected numerically.",
    },
    "AIME-2018-I-04": {
        "owner": "solver", "confidence": "confirmed",
        "cause": "endpoint branch leaked through strict OnSegment/coordinate guards",
        "evidence_codes": ["E1", "E3"],
        "evidence_detail": "The DSL contains OnSegment and strict endpoint inequalities. The extra exact answer 10 is the endpoint/degenerate branch; the audited target 250/39 is also present. This is a solver guard-margin failure, not a missing source clause.",
    },
    "HMMT-2007-FEB-GEO-04": {
        "owner": "dsl", "confidence": "confirmed",
        "cause": "DSL omits tangent-ray and circle-outside-triangle branch conditions",
        "evidence_codes": ["E1", "E3", "E6"],
        "evidence_detail": "The source requires B,C on the two tangent rays and omega outside ABC. DSL encodes only line tangency, By>0/Cy<0 and unsigned triangle area; no OnRay(A,B/C) or outside condition is present. The extra exact 7 is a different tangent-line placement.",
    },
    "HMMT-2010-FEB-GEO-09": {
        "owner": "solver", "confidence": "high",
        "cause": "near-degenerate convex branch was promoted to exact 180",
        "evidence_codes": ["E1", "E3"],
        "evidence_detail": "DSL includes AssumeConvex, while the raw set contains 70,160 and the impossible strict-convex value 180. The 180 branch is numerical boundary leakage/identifier promotion.",
    },
    "HMMT-2014-FEB-GEO-09": {
        "owner": "solver", "confidence": "confirmed",
        "cause": "positive-radius boundary branch leaked through r4>0",
        "evidence_codes": ["E1", "E3"],
        "evidence_detail": "The DSL has AssumeGt(r4,0), but Phase C emits exact 0 together with 92/61. Zero is the radius-degenerate boundary and violates the stated guard.",
    },
    "HMMT-2018-FEB-GEO-05": {
        "owner": "solver", "confidence": "confirmed",
        "cause": "positive-area boundary branch leaked through Area>0",
        "evidence_codes": ["E1", "E3"],
        "evidence_detail": "The DSL explicitly requires theta in (0,pi) and positive quadrilateral area, but exact 0 is emitted alongside 8*sqrt(2)/9. It is a degenerate boundary branch accepted by numeric guards.",
    },
    "HMMT-2024-FEB-GEO-03": {
        "owner": "solver", "confidence": "confirmed",
        "cause": "diameter boundary branch leaked through the non-diameter guard",
        "evidence_codes": ["E1", "E3"],
        "evidence_detail": "The source excludes a diameter and the DSL contains AssumeNe(h,0), yet raw Phase C emits exact 246 (the diameter branch) and 42. The strict nonzero guard was not enforced at the accepted numerical boundary.",
    },
    "JMO-2022-PRE-12": {
        "owner": "dsl", "confidence": "confirmed",
        "cause": "DSL omits the source's acute-triangle and true-inside conditions",
        "evidence_codes": ["E1", "E3", "E6"],
        "evidence_detail": "The Japanese statement requires an acute triangle and P inside ABC. DSL guards only cx,cy,px,py>0; it has no AssumeAcute and no signed/orientation-based inside predicate. The extra exact 6 is therefore an admissible non-source branch.",
    },
    "AIME-2011-II-02": {
        "owner": "solver", "confidence": "confirmed",
        "cause": "square-side endpoint branch leaked through strict segment guards",
        "evidence_codes": ["E1", "E3"],
        "evidence_detail": "The exact target 810 is present. The extra 450 branch corresponds to E/F at endpoints (the direct diagnostic has u≈0 and t≈s), violating the source's strict interior-side placement; the decimal 810 is a duplicate serialization.",
    },
    "AIME-2020-I-01": {
        "owner": "solver", "confidence": "medium",
        "cause": "target branch found, but a degenerate/invalid numerical branch was also accepted",
        "evidence_codes": ["E1", "E2", "E3"],
        "evidence_detail": "Exact target 540/7 is present. Additional 60 and a decimal near 540/7 are emitted; direct diagnostics show a near-zero all-variable candidate with guard_ok=true, demonstrating numerical boundary leakage/branch contamination. The child artifact does not retain enough candidate-to-answer linkage to prove that the 60 value is exactly that near-zero candidate, so this case is marked medium rather than confirmed.",
    },
    "HMMT-2013-FEB-GEO-04": {
        "owner": "solver", "confidence": "high",
        "cause": "branch enumeration and exact identification produced many duplicate decimal branches and an extra exact 1",
        "evidence_codes": ["E1", "E2", "E3"],
        "evidence_detail": "The DSL encodes the two-circle intersection choice and the audited exact branch (-1+sqrt(5))/2. Raw output additionally contains exact 1 and many decimal clusters near 0.618, 1, and 1.618; this is numerical branch/exact-identification contamination rather than a missing target.",
    },
    "HMMT-2021-FEB-GEO-05": {
        "owner": "solver", "confidence": "high",
        "cause": "wrong numerical branch accepted alongside the exact target",
        "evidence_codes": ["E1", "E2", "E3"],
        "evidence_detail": "The exact target 49/400 is present, while an additional decimal 0.0025 is not equal to it (relative error 12/49). This is a solver candidate-validity/refinement failure, not a target serialization issue.",
    },
    "JMO-2022-MATHNET-08z4": {
        "owner": "solver", "confidence": "high",
        "cause": "invalid numerical branch accepted after line-search/max-iteration failures",
        "evidence_codes": ["E1", "E2", "E3"],
        "evidence_detail": "The exact target 2*sqrt(21) is present. Extra decimal 6 is accompanied by line_search_failed/max_iters/residual_too_large tags; this is a rejected-refinement branch that nevertheless entered the answer set.",
    },
    "HMMT-2014-FEB-GEO-10": {
        "owner": "solver", "confidence": "confirmed",
        "cause": "r1,t→0 degenerate boundary branch leaked through r1>0,t>0",
        "evidence_codes": ["E1", "E3", "E6"],
        "evidence_detail": "The audited decimal branch is present. Direct runtime diagnostics reproduce an additional exact 2*sqrt(65) from r1≈0 and t≈0 while guard_ok=true; both strict positivity guards are violated in the limiting branch.",
    },
    "HMMT-2022-FEB-GEO-05": {
        "owner": "dsl", "confidence": "confirmed",
        "cause": "Area guards are unsigned and do not encode D inside triangle ABC",
        "evidence_codes": ["E1", "E3", "E6"],
        "evidence_detail": "Runtime Area(Point,Point,Point) returns Abs(shoelace)/2 (basic.py:194-225). Thus all three Area>0 guards permit outside D. Direct diagnostics reproduce exact roots 1565/2±33*sqrt(1385)/2 with guard_ok=true, while the source requires D interior.",
    },
    "HMMT-2023-FEB-GEO-02": {
        "owner": "solver", "confidence": "confirmed",
        "cause": "A=B endpoint branch leaked through u>0/OnSegment",
        "evidence_codes": ["E1", "E3"],
        "evidence_detail": "Raw output contains exact 0 and the numeric target 2*sqrt(13). Exact 0 is the forbidden endpoint A=B (u=0) despite strict u>0 and OnSegment in the DSL.",
    },
    "HMMT-2023-FEB-GEO-04": {
        "owner": "solver", "confidence": "confirmed",
        "cause": "q=p coincident-point branch leaked through q>p",
        "evidence_codes": ["E1", "E3"],
        "evidence_detail": "Raw output contains exact 1 and the numeric target sqrt(5). Exact 1 is the q=p coincident-point boundary excluded by the source and DSL's q>p guard.",
    },
    "HMMT-2024-FEB-GEO-10": {
        "owner": "dsl+solver", "confidence": "confirmed",
        "cause": "inside-P is not represented by unsigned Area guards; near-degenerate branches are then accepted",
        "evidence_codes": ["E1", "E3", "E6"],
        "evidence_detail": "Area uses Abs(shoelace)/2, so the four positive-area clauses do not mean P is inside. Direct diagnostics show an outside/near-collinear candidate with guard_ok=true; Phase C emits exact 30 and several wrong numerical branches, while the target remains numeric.",
    },
    "HMMT-2006-FEB-GEO-10": {
        "owner": "solver", "confidence": "confirmed",
        "cause": "r→0 degenerate circle boundary leaked through r>0",
        "evidence_codes": ["E1", "E3", "E6"],
        "evidence_detail": "Direct runtime diagnostics reproduce r≈3.3e-9 with residual≈1.2e-9 and guard_ok=true; Phase C reports ≈1.65e-57 instead of 24. The accepted value is the zero-radius boundary, not the source configuration.",
    },
    "HMMT-2015-FEB-GEO-04": {
        "owner": "solver", "confidence": "medium",
        "cause": "no exact target branch was reached/identified; multiple approximate branches remained",
        "evidence_codes": ["E1", "E2", "E3"],
        "evidence_detail": "Raw Phase C has nine decimals from 0.4954 to 0.7296, no exact symbolic value, and tags residual_too_large+answer_missing. The closest value has relative error about 8.55e-3. The DSL/source mapping is source-faithful in the manual audit; a semantic defect is not established by this run.",
    },
    "AIME-2018-II-12": {
        "owner": "solver", "confidence": "confirmed",
        "cause": "feasible DSL instance was missed by search/refinement",
        "evidence_codes": ["E1", "E4"],
        "evidence_detail": "Phase C has 20 candidates, all rejected residual_too_large. Independent solve gives C=(8/5,56/5), D=(-8,14), satisfying all four side lengths, area equality and convexity; area=112. The DSL is feasible, so no_solution is solver-side.",
    },
    "AIME-2019-I-06": {
        "owner": "dsl", "confidence": "confirmed",
        "cause": "ly>0 guard excludes the actual convex source branch",
        "evidence_codes": ["E1", "E3", "E4"],
        "evidence_detail": "Independent construction has K=(0,0), M=(98,0), N=(98,65), L≈(20.5874,-18.9779), giving MN=65, KL=28, KO=8 and MO=90 with all convex turns positive. The DSL additionally requires ly>0, but the valid branch has ly<0; hard_infeasible is caused by this overconstraint.",
    },
    "AIME-2020-II-15": {
        "owner": "solver", "confidence": "confirmed",
        "cause": "feasible acute/scalene instance was missed by search/refinement",
        "evidence_codes": ["E1", "E4"],
        "evidence_detail": "Independent numerical solve gives A≈(3.92145,25.04529), BT=CT≈16, XY²≈717, sum≈1143 and positive acute dot products. The DSL has a valid source-faithful witness; residual_too_large is solver-side.",
    },
    "AIME-2021-I-13": {
        "owner": "solver", "confidence": "confirmed",
        "cause": "feasible externally-tangent-circle branch was missed",
        "evidence_codes": ["E1", "E4"],
        "evidence_detail": "Exact geometric witness at d=672: A=(732.5,622.0649), O=(1232.5,1525.2753), r=1000; external tangent distances are 1961 and 1625 and line AB cuts omega at central angle 120°. The DSL is feasible; answer_missing/residual_non_finite is solver-side.",
    },
    "AIME-2022-II-07": {
        "owner": "dsl", "confidence": "confirmed",
        "cause": "symmetric l1/l2 intercept construction is algebraically infeasible",
        "evidence_codes": ["E1", "E3", "E4"],
        "evidence_detail": "For l1:y=mx+b and l2:y=-mx+b to both be tangent to the radius-24 circle centered (30,0), equations imply (30m+b)^2=(-30m+b)^2, hence mb=0. With m>0, b=0, which makes distance from (0,0) to either line zero rather than 6. Therefore the DSL has no solution; the source problem itself is not infeasible.",
    },
    "JMO-2019-MATHNET-08yk": {
        "owner": "dsl", "confidence": "confirmed",
        "cause": "cx>0 guard excludes the valid AB>AC branch",
        "evidence_codes": ["E1", "E3", "E4"],
        "evidence_detail": "Independent construction gives AB≈7.0906225924=(81+9*sqrt(13))/16, AC≈3.03437741, angle A=2π/3, and DE=DI=EI=1 with AB>AC. In the DSL gauge C=(cx,cy), this valid branch has cx=-(AC)/2<0, but the DSL requires AssumeGt(cx,0). Thus no_solution is caused by an overrestrictive DSL guard.",
    },
    "JMO-2019-PRE-08": {
        "owner": "dsl", "confidence": "confirmed",
        "cause": "cx>0 guard excludes the valid AB>AC branch",
        "evidence_codes": ["E1", "E3", "E4"],
        "evidence_detail": "Same source-faithful witness as the MATHNET alias: AB≈7.0906225924, AC≈3.03437741, angle A=2π/3, and DE=DI=EI=1. The valid coordinate has cx<0, while this DSL also requires AssumeGt(cx,0); no_solution is therefore a DSL overconstraint.",
    },
    "JMO-2013-PRE-08": {
        "owner": "solver", "confidence": "confirmed",
        "cause": "uncaught mpmath findroot/LU TypeError in Phase B closure",
        "evidence_codes": ["E1", "E5"],
        "evidence_detail": "Benchmark error is TypeError(\"'>=' not supported between instances of 'NoneType' and 'int'\"). Direct reproduction traceback reaches _run_findroot_closure -> mp.findroot -> mpmath.matrices.linalg.LU_decomp -> matrices.__getitem__, where key[0] is None. The refiner catches ValueError/ZeroDivisionError only, so this aborts the case.",
    },
}


def _validate_mapping(failure_ids: set[str]) -> None:
    groups = [DECIMAL_NEAR, TARGET_PLUS_EXTRA, TARGET_PLUS_DECIMAL, WRONG_EXACT, DECIMAL_WRONG, NO_SOLUTION, TIMEOUT, EXCEPTION]
    all_grouped = set().union(*groups)
    if all_grouped != failure_ids:
        raise AssertionError(f"mapping coverage mismatch: missing={sorted(failure_ids-all_grouped)}, extra={sorted(all_grouped-failure_ids)}")
    if len(DECIMAL_NEAR) != 35:
        raise AssertionError(len(DECIMAL_NEAR))
    if set(OVERRIDES) - failure_ids:
        raise AssertionError(f"override for non-failure: {set(OVERRIDES)-failure_ids}")


def main() -> int:
    benchmark = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    truth = _read_jsonl(TRUTH_PATH)
    manual = _read_jsonl(MANUAL_PATH)
    rows = {row["case_id"]: row for row in benchmark["results"]}
    failures = {
        case_id
        for case_id, row in rows.items()
        if row.get("truth_status") == "verified"
        and row.get("status") != "reference_only"
        and row.get("strict_answer_set_exact") is not True
    }
    _validate_mapping(failures)

    audit_rows: list[dict[str, Any]] = []
    for case_id in sorted(failures):
        row = rows[case_id]
        dsl_path = DSL_DIR / f"{case_id}.json"
        dsl = json.loads(dsl_path.read_text(encoding="utf-8"))
        source = manual.get(case_id, {})
        expected = truth[case_id]["exact_answer_set"]
        values = (row.get("phasec") or {}).get("answer_values") or []
        info = _cause_defaults(case_id, row["status"])
        info.update(OVERRIDES.get(case_id, {}))
        audit_rows.append({
            "case_id": case_id,
            "status": row.get("status"),
            "wall_sec": row.get("wall_sec"),
            "seed": row.get("seed"),
            "budget_sec": benchmark.get("budget_sec"),
            "cpu_affinity": benchmark.get("cpu_affinity"),
            "truth_status": truth[case_id].get("truth_status"),
            "expected_exact_answer_set": expected,
            "raw_phasec_answer_values": values,
            "phasec_rejected_false_positive_count": (row.get("phasec") or {}).get("rejected_false_positive_count"),
            "phasec_rejection_tags": (row.get("phasec") or {}).get("rejection_tags", []),
            "benchmark_error": row.get("error"),
            "strict_answer_set_exact": row.get("strict_answer_set_exact"),
            "strict_answer_set_complete": row.get("strict_answer_set_complete"),
            "best_numeric_relative_error_diagnostic": _best_relative_error(values, expected),
            "dsl_path": str(dsl_path.relative_to(ROOT)),
            "dsl_sha256": _sha256(dsl_path),
            "dsl_variables": dsl.get("variables", {}).get("names", []),
            "dsl_construction": dsl.get("construction", []),
            "dsl_constraints": dsl.get("constraints", []),
            "dsl_guards": dsl.get("guards", []),
            "dsl_answer": dsl.get("answer"),
            "source_statement": source.get("source_statement", dsl.get("source_statement")),
            "source_statement_sha256": truth[case_id].get("source_statement_sha256"),
            "manual_clause_ledger": source.get("clause_ledger", dsl.get("clause_ledger", [])),
            **info,
        })

    OUT_JSONL.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in audit_rows),
        encoding="utf-8",
    )

    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in audit_rows:
        by_category[row["category"]].append(row)
    lines: list[str] = []
    lines += [
        "# 厳密解集合で失敗した66ケースの証拠付き監査",
        "",
        "このレポートは `benchmark_results_180s_1core_strict_raw.json` の raw Phase C 出力を、"
        "`exact_truth.jsonl` の厳密解集合、手作業監査 (`manual_audit.jsonl`)、各DSLと突合したものです。"
        "数値近似による正誤判定はしていません。全フィールドと生の長い数値列は"
        "`FAILURE_CASE_AUDIT_STRICT_RAW.jsonl` に保存しています。独立計算の再現結果は `FAILURE_CASE_INDEPENDENT_CHECKS.json`、その生成コードは `verify_failure_case_independent.py` です。",
        "",
        "## 監査対象と集計",
        "",
        f"- benchmark: `{BENCHMARK_PATH.name}`; hard timeout 180 s, jobs=1, CPU=[0], seed=7",
        "- verifiedかつrunnableな205件のうち、strict exact set failureは **66件 (32.2%)**、strict exact successは139件 (67.8%)。",
        "- strict scoringは、答えの表示形式ではなくDSLのraw targetの厳密解集合を比較する。decimal-only出力は厳密解とは認めない。",
        "- 因果の強さ: `confirmed` は生ログとDSL/ランタイムまたは独立検算で機構まで再現、`high` は生ログと制約から機構を強く特定、`medium` は失敗機構は確定するがDSL意味不備までは立証していない。",
        "",
        "| category | 件数 | 主な帰属 |",
        "|---|---:|---|",
    ]
    for cat in sorted(by_category):
        owners = ", ".join(sorted(Counter(r["owner"] for r in by_category[cat])))
        lines.append(f"| `{cat}` | {len(by_category[cat])} | {owners} |")
    lines += [
        "",
        "## 証拠コード",
        "",
        "- **E1**: benchmarkの当該row（status, wall_sec, raw `phasec.answer_values`, rejection tags, error）。",
        "- **E2**: Phase C実装。`run_phasec_assembly.py:135-144` は exact identification失敗時にdecimal `candidate.answer_hp`へフォールバックする。",
        "- **E3**: DSLのconstruction/constraints/guardsとsource statementの逐条比較。",
        "- **E4**: DSLとは独立な代入・数値解・代数証明による実行可能性/不可能性の検算。",
        "- **E5**: runtime tracebackの直接再現。",
        "- **E6**: runtime semantics（特に `Area` は `Abs(shoelace)/2`）を確認した証拠。",
        "",
        "## ケース別判定",
        "",
    ]
    for cat in sorted(by_category):
        lines += [f"### `{cat}` ({len(by_category[cat])}件)", "", "| case | status | expected | raw Phase C (excerpt) | owner / confidence | cause |", "|---|---|---|---|---|---|"]
        for row in by_category[cat]:
            raw = _short(row["raw_phasec_answer_values"], 240).replace("|", "\\|")
            exp = _short(row["expected_exact_answer_set"], 120).replace("|", "\\|")
            cause = row["cause"].replace("|", "\\|")
            lines.append(f"| `{row['case_id']}` | {row['status']} | `{exp}` | `{raw}` | {row['owner']} / {row['confidence']} | {cause} |")
        lines.append("")

    lines += [
        "## 重要な再現証拠（断定の根拠）",
        "",
        "1. `AIME-2018-II-12`: DSLに対し `C=(8/5,56/5), D=(-8,14)` を代入すると、4辺残差は約1e-15、面積等式残差は約7e-15、凸性の各turnは `[112,84,112,140]`、面積は112となる。no_solutionはDSL不可能性ではない。",
        "2. `AIME-2019-I-06`: source条件を満たす `K=(0,0), M=(98,0), N=(98,65), L≈(20.5874,-18.9779)` があり `MO=90`。DSLの `AssumeGt(ly,0)` だけがこの凸branchを排除する。hard_infeasibleはDSL過制約。",
        "3. `AIME-2020-II-15`: 独立解 `A≈(3.92145,25.04529)` で `BT=CT≈16`, `TX²+TY²+XY²≈1143`, `XY²≈717`、三角形はacute/scalene。residual_too_largeはsolverの探索/精密化失敗。",
        "4. `AIME-2021-I-13`: `d=672`, `r=1000`, `A≈(732.5,622.0649)`, `O≈(1232.5,1525.2753)` が外接接条件と120°弦条件を満たす。no_solutionはsolver側。",
        "5. `AIME-2022-II-07`: 同じbを使う `l1:y=mx+b`, `l2:y=-mx+b` を半径24円に接する条件から `mb=0`、m>0ならb=0、半径6円への接線条件と矛盾。DSL自体がsourceの三角形を表現できていない。",
        "6. `JMO-2019-MATHNET-08yk` / `JMO-2019-PRE-08`: 独立解で `AB=(81+9√13)/16≈7.0906225924`, `AC≈3.03437741`, angle A=2π/3, `DE=DI=EI=1`。このsource-faithful branchでは座標Cの `cx<0` だが、両DSLが `AssumeGt(cx,0)` を追加しているため、no_solutionはDSL過制約。",
        "7. `HMMT-2022-FEB-GEO-05`, `HMMT-2024-FEB-GEO-10`: runtime `Area` は符号を捨てるため、`Area>0` はinside条件ではない。outside/near-degenerate候補が `guard_ok=true` で再現し、wrong exact/extra branchesを説明する。",
        "8. `JMO-2013-PRE-08`: tracebackは Phase B `_run_findroot_closure` → `mp.findroot` → mpmath `LU_decomp` → `matrices.__getitem__` の None index。DSLの解集合問題ではなく未捕捉runtime bug。",
        "",
        "## 限界と結論",
        "",
        "timeout 2件 (`AIME-2020-II-13`, `JMO-2015-PRE-11`) は、180.106秒でchildが停止しPhase Cが存在しないことまでは完全に証明できるが、内部のどの探索段階が時間を使ったかはこのbenchmark artifactからは特定できない。`HMMT-2015-FEB-GEO-04` も、近似候補しか得られなかったことは確定するが、DSL意味欠落を示す独立反例は得ていない。この3件は不必要にDSLの欠陥と断定していない。",
        "",
        "監査JSONLには各ケースのDSL hash、source hash、全constraints/guards、raw値、tags、error、cause/evidence codeを保存した。独立検算JSONはsolver本体を呼ばずに、no_solutionの実行可能性・DSL代数矛盾・unsigned Area semanticsを再現する。",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "failures": len(audit_rows),
        "categories": {k: len(v) for k, v in sorted(by_category.items())},
        "jsonl": str(OUT_JSONL),
        "markdown": str(OUT_MD),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
