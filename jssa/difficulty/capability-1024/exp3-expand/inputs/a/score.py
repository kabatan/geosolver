"""Assessment only. Existing research_runner exact keys/outcome, unchanged.

There is deliberately no execution entrypoint in this module. The explicit
official-output conversions complement, never replace, raw geometric equality.
"""
from pathlib import Path
import json
import sympy as sp
from benchmarks import research_runner as rr
from geosolver.exact import describe_exact

HERE = Path(__file__).resolve().parent


def _positive_integer(v):
    assert v.is_Integer is True and v > 0, v
    return v


def _fraction(v):
    v = sp.simplify(v)
    assert v.is_Rational is True and v > 0, v
    return v.as_numer_denom()


def _rational_part(v):
    v = sp.expand(v)
    a = sum((x for x in sp.Add.make_args(v) if x.is_Rational), sp.S.Zero)
    return a, sp.simplify(v-a)


def _pure_radical(v):
    coefficient, radical = sp.expand(v).as_coeff_Mul()
    assert coefficient.is_Rational is True and coefficient > 0
    n = sp.simplify(radical**2)
    _positive_integer(n)
    assert radical > 0 and n > 1
    assert all(e == 1 for e in sp.factorint(n).values()), 'not squarefree'
    return coefficient, n


def convert(value, rule):
    v = sp.simplify(value)
    if rule == 'fraction_sum':
        a,b = _fraction(v); out = a+b
    elif rule == 'square_fraction_sum':
        a,b = _fraction(v**2); out = a+b
    elif rule == 'denominator':
        out = _fraction(v)[1]
    elif rule == 'integer_plus_sqrt':
        a,radical = _rational_part(v)
        b = sp.simplify(radical**2)
        _positive_integer(a); _positive_integer(b)
        assert radical > 0
        out = a+b
    elif rule == 'half_sqrt_minus_integer':
        a,radical = _rational_part(2*v)
        p=sp.simplify(radical**2); q=-a
        _positive_integer(p); _positive_integer(q)
        assert radical > 0
        out = p+q
    elif rule == 'radical_fraction_sum':
        coefficient,n = _pure_radical(v)
        m,p = coefficient.as_numer_denom()
        out = m+n+p
    elif rule == 'integer_plus_radical_sum':
        p,radical = _rational_part(v)
        q,r = _pure_radical(radical)
        _positive_integer(p); _positive_integer(q)
        out = p+q+r
    elif rule == 'floor':
        out = sp.floor(v)
    elif rule == 'sqrt3_coefficient_mod1000':
        coefficient = sp.simplify(v/sp.sqrt(3))
        assert coefficient.is_Integer is True
        out = coefficient % 1000
    elif rule == 'identity':
        out = v
    else:
        raise ValueError(rule)
    assert out.is_Integer is True, out
    return out


def descriptor_expression(d):
    x=sp.Symbol('x')
    p=sp.Poly.from_list([sp.Rational(c) for c in d['minimal_polynomial']],x)
    return p.real_roots()[d['real_root_index']]


def answer_expression(answer):
    if answer['kind']=='algebraic':
        return descriptor_expression(answer['value'])
    if answer['kind']=='affine_pi':
        return descriptor_expression(answer['pi_coefficient'])*sp.pi+descriptor_expression(answer['constant'])
    raise ValueError('unsupported answer kind')


def exact_keys(values):
    return sorted({rr._canonical_json(describe_exact(str(v)).canonical_key()) for v in values})


def assess(raw, references=None):
    if references is None: references=json.loads((HERE/'references.json').read_text())
    ref=references[raw['case_id']]
    result=raw.get('solver_result') or {}
    actual=rr._answer_keys(result)
    expected=exact_keys([ref['geometric_value']])
    errors=[]; converted=[]
    for answer in result.get('answers',[]):
        try: converted.append(str(convert(answer_expression(answer),ref['output_conversion'])))
        except Exception as error: errors.append(type(error).__name__+': '+str(error))
    outcome=rr.read_run_outcome(raw)
    raw_match=actual==expected
    official_match=not errors and exact_keys(converted)==exact_keys([ref['official_output']])
    return dict(case_id=raw['case_id'],seed=raw['seed'],
                matched=bool(outcome['normal_completion'] and raw_match and official_match),
                geometric_matched=raw_match,official_output_matched=official_match,
                actual_exact_keys=actual,expected_exact_keys=expected,
                converted_outputs=converted,conversion_errors=errors,
                n_answers=len(actual),extra=len(set(actual)-set(expected)),**outcome)


def check_contract(references):
    """Synthetic descriptor controls, not a solver run or a prediction observation."""
    import copy
    for cid,ref in references.items():
        desc=describe_exact(ref['geometric_value']).model_dump()
        assert str(convert(answer_expression(desc),ref['output_conversion']))==ref['official_output'],cid
        raw=dict(case_id=cid,seed=0,solver_result=dict(status='solved',answers=[desc]))
        assert assess(raw,references)['matched'],cid
        extra=copy.deepcopy(raw)
        extra['solver_result']['answers'].append(describe_exact('1234567').model_dump())
        assert not assess(extra,references)['matched'],cid
        timeout=copy.deepcopy(raw); timeout['process']=dict(timed_out=True)
        assert not assess(timeout,references)['matched'],cid
        violation=copy.deepcopy(raw); violation['execution_contract_issues']=['synthetic violation']
        assert not assess(violation,references)['matched'],cid
        absent=dict(case_id=cid,seed=0,solver_result=dict(status='no_answer_found',answers=[]))
        assert not assess(absent,references)['matched'],cid
    cid='AIME-2001-I-07'
    collision=dict(case_id=cid,seed=0,solver_result=dict(status='solved',answers=[describe_exact('1/922').model_dump()]))
    result=assess(collision,references)
    assert result['official_output_matched'] and not result['matched']
    return dict(kind='synthetic scoring contract checks, not solver observations',solver_run=False,
                raw_reference_roundtrips=len(references),extra_answer_rejections=len(references),
                external_timeout_rejections=len(references),contract_issue_rejections=len(references),
                empty_answer_rejections=len(references),same_official_output_wrong_geometry_rejected=True,
                research_runner_modified=False,passed=True)
