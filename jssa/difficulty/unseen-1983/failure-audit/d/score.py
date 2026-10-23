"""Existing exact-key scoring plus the pre-fixed official-output conversion."""
from __future__ import annotations
import json
from pathlib import Path
import sympy as sp
from benchmarks import research_runner as rr
from geosolver.exact import describe_exact

HERE=Path(__file__).resolve().parent
REFERENCES=json.loads((HERE/"references.json").read_text())

def descriptor_expression(d):
    x=sp.Symbol("x")
    poly=sp.Poly.from_list([sp.Rational(c) for c in d["minimal_polynomial"]],x)
    return poly.real_roots()[d["real_root_index"]]

def answer_expression(answer):
    if answer["kind"]=="algebraic":
        return descriptor_expression(answer["value"])
    if answer["kind"]=="affine_pi":
        return descriptor_expression(answer["pi_coefficient"])*sp.pi+descriptor_expression(answer["constant"])
    raise ValueError("unknown exact answer kind")

def convert(value,rule):
    value=sp.simplify(value)
    if rule in {"numerator_plus_denominator","100_numerator_plus_denominator"}:
        if value.is_Rational is not True or value<=0:
            raise ValueError("expected a positive exact rational")
        a,b=value.as_numer_denom()
        return a+b if rule=="numerator_plus_denominator" else 100*a+b
    if rule=="integer_plus_sqrt":
        terms=sp.Add.make_args(sp.expand(value))
        a=sum((t for t in terms if t.is_Rational),sp.S(0))
        radical=sp.simplify(value-a)
        b=sp.simplify(radical**2)
        if a.is_Integer is not True or b.is_Integer is not True or b<0 or radical<0:
            raise ValueError("not a+sqrt(b) with integer a,b and nonnegative square root")
        return a+b
    if rule=="floor_1000":
        out=sp.floor(1000*value)
    elif rule=="radians_to_degrees":
        out=sp.simplify(180*value/sp.pi)
    elif rule=="identity":
        out=value
    else:
        raise ValueError(rule)
    if out.is_Integer is not True:
        raise ValueError("official output is not an exact integer")
    return out

def keys(values):
    return sorted({rr._canonical_json(describe_exact(str(v)).canonical_key()) for v in values})

def assess(raw):
    cid=raw["case_id"]
    ref=REFERENCES[cid]
    result=raw.get("solver_result") or {}
    actual=rr._answer_keys(result)
    expected=keys([ref["geometric_value"]])
    converted=[]
    errors=[]
    expressions=[]
    for answer in result.get("answers",[]):
        try:
            value=answer_expression(answer)
            expressions.append(str(value))
            converted.append(str(convert(value,ref["output_conversion"])))
        except Exception as error:
            errors.append(type(error).__name__+": "+str(error))
    outcome=rr.read_run_outcome(raw)
    output_matched=not errors and keys(converted)==keys([ref["official_output"]])
    raw_matched=actual==expected
    return {"case_id":cid,"seed":raw["seed"],"matched":bool(outcome["normal_completion"] and raw_matched and output_matched),
            "geometric_matched":raw_matched,"official_output_matched":output_matched,
            "actual_exact_keys":actual,"expected_exact_keys":expected,
            "answer_expressions":expressions,"converted_outputs":converted,"conversion_errors":errors,
            "geometric_reference":ref["geometric_value"],"official_reference":ref["official_output"],
            "n_answers":len(actual),"extra":len(set(actual)-set(expected)),
            "diag_numeric":(result.get("diagnostics") or {}).get("numeric_feasible"),
            "diag_identified":(result.get("diagnostics") or {}).get("exact_identified"),
            **outcome}

def validate_conversions():
    for cid,ref in REFERENCES.items():
        answer=describe_exact(ref["geometric_value"]).model_dump()
        assert str(convert(answer_expression(answer),ref["output_conversion"]))==ref["official_output"],cid
        raw={"case_id":cid,"seed":0,"solver_result":{"status":"solved","answers":[answer]}}
        assert assess(raw)["matched"],cid
        raw["solver_result"]["answers"].append(describe_exact("1234567").model_dump())
        assert not assess(raw)["matched"],cid
    # Same official m+n must not let a wrong geometric value pass.
    raw={"case_id":"AIME-1985-09","seed":0,"solver_result":{"status":"solved","answers":[describe_exact("1/48").model_dump()]}}
    checked=assess(raw)
    assert checked["official_output_matched"] and not checked["matched"]
    return {"reference_roundtrips":len(REFERENCES),"extra_answer_controls_rejected":len(REFERENCES),
            "same_m_plus_n_wrong_geometric_answer_rejected":True}
