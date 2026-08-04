#!/usr/bin/env python3
import json
import sys
import time
from fractions import Fraction
import sympy as sp

from geosolver._internal.pipeline.contracts import ExternalPipelineConfig
from geosolver._internal.pipeline.orchestration.run_external_pipeline import run_external_pipeline


path, seed, budget = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
problem = json.load(open(path, encoding="utf-8"))

# Some source-faithful records intentionally retain a figure-dependent clause
# that the current geometric IR cannot express without inventing coordinates.
# Keep these in the corpus and report them explicitly instead of letting an
# unconstrained numerical search manufacture a spurious answer.
if problem.get("solver_coverage", "").startswith("reference_only"):
    print(json.dumps({
        "status": "reference_only",
        "selected_answer": None,
        "reported_answer": None,
        "accepted_answers": [],
        "accepted_count": 0,
        "elapsed_sec": 0.0,
        "phasec": {"accepted_count": 0, "answer_values": [], "rejected_false_positive_count": 0, "rejection_tags": ["source_clause_not_in_current_ir"]},
    }, ensure_ascii=False))
    raise SystemExit(0)


def _source_reported_answer(problem, summary, selected):
    """Apply the small presentation transforms used by this dataset.

    The frozen solver deliberately returns the geometric scalar before the
    contest's ``p+q``/``100a+b`` answer formatting.  Applying those explicit
    JSON post-process snippets here keeps the geometric definition untouched
    while making benchmark output comparable with the published answer.
    """
    code = (problem.get("post_process") or "").strip()
    if not code or selected is None:
        return None
    values = (summary.get("phasec", {}) or {}).get("answer_values", [])
    # Phase C may retain both a high-precision decimal fallback and an exact
    # symbolic identification.  For a presentation transform, prefer the
    # symbolic form; selecting the decimal first can make nsimplify return a
    # large rational approximation and hide an otherwise valid AIME answer.
    if "radical_mode=" in code:
        raw = next(
            (value for value in values if "sqrt" in str(value) or "√" in str(value)),
            values[0] if values else selected,
        )
    else:
        raw = values[0] if values else selected
    text = str(raw).strip()
    try:
        compact = code.replace(" ", "")
        if "radical_mode=" in code:
            mode = code.split("radical_mode=", 1)[1].split()[0].strip(";,#")
            basis = []
            if "basis=" in code:
                basis_text = code.split("basis=", 1)[1].split()[0].strip(";,#")
                basis = [sp.sqrt(int(item)) for item in basis_text.split(",") if item]
            expr = sp.nsimplify(text, basis) if basis else sp.nsimplify(text)
            expr = sp.radsimp(sp.expand(expr))
            terms = sp.Add.make_args(expr)
            rat = sp.Rational(0)
            radical_terms = []
            for term in terms:
                if term.is_Rational:
                    rat += term
                    continue
                coeff, rest = term.as_coeff_Mul()
                if rest.is_Pow and rest.exp == sp.Rational(1, 2) and rest.base.is_Integer:
                    radical_terms.append((sp.Rational(coeff), int(rest.base)))
                else:
                    raise ValueError("unsupported radical form")
            if mode == "p_minus_q_plus_r_minus_s_over2":
                coeffs = {2: sp.Rational(0), 3: sp.Rational(0), 6: sp.Rational(0)}
                for coeff, radicand in radical_terms:
                    if radicand not in coeffs:
                        raise ValueError("unsupported radical basis")
                    coeffs[radicand] += coeff
                value = (coeffs[2] - coeffs[3] + coeffs[6] - rat) / 2
                if value.q != 1:
                    raise ValueError("nonintegral requested combination")
                return int(value)
            if mode not in {"radical_sum", "sqrt_difference_sum"} and len(radical_terms) != 1:
                raise ValueError("expected one radical")
            if mode == "radical_sum":
                if rat != 0:
                    raise ValueError("not a sum of square roots")
                # A source expression written as sqrt(a)+sqrt(b) may be
                # normalized by the solver as c*sqrt(r).  Recover the
                # square-free radicand of each term as c^2*r before adding.
                return sum((abs(int(c)) ** 2) * int(r) for c, r in radical_terms if c.q == 1)
            coeff, radicand = radical_terms[0]
            if mode == "single_sqrt_sum":
                if rat != 0 or coeff.q != 1:
                    raise ValueError("not m*sqrt(n)")
                return abs(int(coeff.p)) + radicand
            if mode == "linear_sqrt_sum":
                if coeff.q != 1 or rat.q != 1:
                    raise ValueError("not p+q*sqrt(r)")
                return abs(int(rat.p)) + abs(int(coeff.p)) + radicand
            if mode == "p_plus_q_plus_r":
                # Source form x=p-q*sqrt(r), with integer p,q and
                # square-free r.  The sign in the expression is irrelevant
                # to the requested sum, but preserve both integer
                # coefficients instead of assuming q=1.
                if coeff.q != 1 or rat.q != 1 or coeff == 0:
                    raise ValueError("not p-q*sqrt(r)")
                return abs(int(rat.p)) + abs(int(coeff.p)) + radicand
            if mode == "m_minus_n_sqrt_k":
                if coeff.q != 1 or rat.q != 1:
                    raise ValueError("not m-n*sqrt(k)")
                return abs(int(rat.p)) + abs(int(coeff.p)) * radicand
            if mode == "m_minus_sqrt_n":
                if coeff.q != 1 or rat.q != 1:
                    raise ValueError("not m-sqrt(n)")
                return abs(int(rat.p)) + (abs(int(coeff.p)) ** 2) * radicand
            if mode == "quadratic_radical_radicand":
                # AIME form p +/- q*sqrt(r); the requested answer is the
                # square-free radicand r, not the value of the length itself.
                # The solver may keep the presentation's rational scale
                # (for example (231-3*sqrt(989))/10).  The requested value is
                # still the radicand, so only the presence of one nonzero
                # square-root term matters here.
                if coeff == 0:
                    raise ValueError("not p+q*sqrt(r)")
                return radicand
            if mode == "sqrt_m_minus_n":
                # AIME form sqrt(m)-n.  The solver may normalize this as
                # coeff*sqrt(radicand)+rat; recover m+n without changing the
                # geometric definition.
                if coeff.q != 1 or rat.q != 1:
                    raise ValueError("not sqrt(m)-n")
                if coeff == 0 or int(rat.p) >= 0:
                    raise ValueError("not sqrt(m)-n")
                return (abs(int(coeff.p)) ** 2) * radicand + abs(int(rat.p))
            if mode == "sqrt_coefficient":
                # AIME form n*sqrt(k); the requested answer is n.
                if rat != 0 or coeff.q != 1:
                    raise ValueError("not n*sqrt(k)")
                return abs(int(coeff.p))
            if mode == "m_over_sqrt_n_sum":
                # AIME form m/sqrt(n), with m,n coprime.  Normalize the
                # solver's coeff*sqrt(radicand)/denom representation and
                # return m+n = coeff + denom^2/radicand.
                if rat != 0 or coeff == 0:
                    raise ValueError("not m/sqrt(n)")
                denom = int(coeff.q)
                numer = abs(int(coeff.p))
                if denom <= 0 or numer <= 0 or denom * denom % radicand != 0:
                    raise ValueError("not m/sqrt(n)")
                n_value = denom * denom // radicand
                return numer + n_value
            if mode == "hundred_a_plus_b":
                if coeff.q != 1 or rat.q != 1:
                    raise ValueError("not a-b*sqrt(k)")
                return 100 * abs(int(rat.p)) + abs(int(coeff.p)) * radicand
            if mode == "pqr_sum":
                if rat != 0:
                    raise ValueError("not p*sqrt(q)/r")
                return abs(int(coeff.p)) + radicand + int(coeff.q)
            if mode == "rational_plus_sqrt_sum":
                if coeff != 1 or rat.q != 1:
                    raise ValueError("not p+sqrt(q)")
                return abs(int(rat.p)) + radicand
            if mode == "sqrt_difference_sum":
                # Source form sqrt(a)-sqrt(b), allowing integer multiples of
                # square roots in the solver's normalized expression.
                if rat != 0 or len(radical_terms) != 2:
                    raise ValueError("not a difference of two square roots")
                values = []
                for term_coeff, term_radicand in radical_terms:
                    if term_coeff.q != 1:
                        raise ValueError("nonintegral radical coefficient")
                    values.append(int(term_coeff) ** 2 * int(term_radicand))
                return sum(values)
            if mode == "m_sqrt_n_minus_p_over_q":
                # AIME form (m*sqrt(n)-p)/q.  Normalize the rational and
                # radical coefficients to their common denominator first;
                # unlike rational_minus_sqrt_sum, the radical coefficient m
                # is not squared in this presentation.
                denom = sp.ilcm(int(rat.q), int(coeff.q))
                m_num = int(coeff * denom)
                p_num = int(-rat * denom)
                if m_num <= 0 or p_num <= 0 or denom <= 0:
                    raise ValueError("not m*sqrt(n)-p over q")
                return m_num + radicand + p_num + denom
            if mode == "rational_minus_sqrt_sum":
                # Source form (a-sqrt(b))/c.  Recover b from the normalized
                # integer radical coefficient; this mode is intentionally
                # distinct from p_plus_q_plus_r_plus_s below, whose source
                # gives the coefficient q separately.
                denom = sp.ilcm(int(rat.q), int(coeff.q))
                rational_num = int(rat * denom)
                radical_num = abs(int(coeff * denom))
                return abs(rational_num) + radical_num * radical_num * int(radicand) + int(denom)
            if mode == "p_plus_q_plus_r_plus_s":
                # Source form (p-q*sqrt(r))/s, where q is an explicit
                # positive integer and the requested value is p+q+r+s.
                denom = sp.ilcm(int(rat.q), int(coeff.q))
                rational_num = int(rat * denom)
                radical_num = abs(int(coeff * denom))
                return abs(rational_num) + radical_num + int(radicand) + int(denom)
            raise ValueError("unknown radical mode")
        if "formatter.to_fraction" in code:
            if "/" in text and "sqrt" not in text and "√" not in text:
                frac = Fraction(text)
            else:
                frac = Fraction(str(selected)).limit_denominator(10_000_000)
            if "%1000" in compact:
                return (frac.numerator + frac.denominator) % 1000
            if "100*f.numerator+f.denominator" in compact:
                return 100 * frac.numerator + frac.denominator
            if "100*a+b" in compact or "100*frac.numerator+frac.denominator" in compact:
                return 100 * frac.numerator + frac.denominator
            if "f.numerator-f.denominator" in compact:
                return frac.numerator - frac.denominator
            if "f.numerator+f.denominator" in compact:
                return frac.numerator + frac.denominator
            return str(frac)
    except (ValueError, ZeroDivisionError):
        return None
    return None
t0 = time.monotonic()
try:
    config = ExternalPipelineConfig.production_baseline_tier(seed=seed, total_time_budget_sec=budget)
    result = run_external_pipeline(problem, pipeline_config=config)
    summary = result.summary if isinstance(result.summary, dict) else {}
    selected = result.selected_answer
    reported = _source_reported_answer(problem, summary, selected)
    phasec = summary.get("phasec", {}) if isinstance(summary, dict) else {}
    print(json.dumps({
        "status": str(result.status),
        "selected_answer": str(selected) if selected is not None else None,
        "reported_answer": str(reported) if reported is not None else None,
        "accepted_answers": [str(x) for x in result.accepted_answers],
        "accepted_count": int(getattr(result, "accepted_count", len(result.accepted_answers))),
        "elapsed_sec": time.monotonic() - t0,
        "phasec": phasec,
    }, ensure_ascii=False))
except Exception as exc:
    print(json.dumps({"status": "exception", "error": repr(exc), "elapsed_sec": time.monotonic() - t0}, ensure_ascii=False))
