from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

import sympy as sp

import candidate as implementation
import run_generated as generated
from candidate import (
    PolynomialSource,
    TargetProposal,
    compile_qf_nra,
    prove,
    prove_semantic_document,
)


def test_generated_gate() -> None:
    result = generated.run()
    assert result["decision"] == "GO_D0"
    assert result["positive_activation_count"] >= 2
    assert result["negative_false_accept_count"] == 0
    assert result["metamorphic_pass_count"] == 3


def test_regular_witness_is_exact_and_replayed() -> None:
    regular, proposal, *_ = generated.generated()
    result = prove(regular, proposal)
    assert result["authority_pass"] is True
    assert result["independent_replay"]["pass"] is True
    assert result["model_descriptors"]["x"]["kind"] == "AlgebraicNumRef"


def test_positive_dimensional_irrelevant_coordinate_is_explicit() -> None:
    *_, source, proposal, _division, _division_p = generated.generated()
    result = prove(source, proposal)
    assert result["authority_pass"] is True
    assert result["irrelevant_free_variables"] == ["y"]
    assert result["model_descriptors"]["y"] == {
        "kind": "Rational", "numerator": 0, "denominator": 1
    }


def test_relevant_positive_dimensional_fiber_fails_closed() -> None:
    x, y = sp.symbols("x y", real=True)
    source = PolynomialSource(("x", "y"), (x**2 - 2,), y > 0, x, label="relevant-free-y")
    proposal = TargetProposal((1, 0, -2), 1, Fraction(1), Fraction(2))
    result = prove(source, proposal)
    assert result["authority_pass"] is False
    assert "POSITIVE_DIMENSIONAL" in result["reason"]


def test_division_definedness_is_in_formula_and_replay() -> None:
    *_, source, proposal = generated.generated()
    formula = compile_qf_nra(source, proposal)
    assert formula.definedness
    result = prove(source, proposal)
    assert result["authority_pass"] is True
    assert result["independent_replay"]["division_definedness"] is True


def test_wrong_descriptor_and_strict_boundary_are_not_proved() -> None:
    regular, proposal, *_ = generated.generated()
    wrong = replace(proposal, polynomial_high_to_low=(1, 0, -7))
    assert prove(regular, wrong)["authority_pass"] is False
    x, y = sp.symbols("x y", real=True)
    boundary = PolynomialSource(("x", "y"), (x, y), x > 0, x)
    linear = TargetProposal((1, 0), 0, Fraction(-1), Fraction(1))
    assert prove(boundary, linear)["authority_pass"] is False


def test_transcendental_is_not_proved() -> None:
    x, y = sp.symbols("x y", real=True)
    source = PolynomialSource(("x", "y"), (sp.sin(x), y), sp.true, x)
    proposal = TargetProposal((1, 0), 0, Fraction(-1), Fraction(1))
    result = prove(source, proposal)
    assert result["authority_pass"] is False
    assert "UNSUPPORTED" in result["reason"]


def test_nonsquarefree_proposal_is_not_proved() -> None:
    regular, _proposal, *_ = generated.generated()
    repeated = TargetProposal((1, -2, 1), 0, Fraction(0), Fraction(2))
    result = prove(regular, repeated)
    assert result["authority_pass"] is False
    assert result["reason"] == "PROPOSAL_NOT_SQUARE_FREE"


def test_backend_timeout_is_not_proved(monkeypatch) -> None:
    regular, proposal, *_ = generated.generated()

    def expire(*_args, **_kwargs):
        raise implementation.BackendTimeout("generated timeout")

    monkeypatch.setattr(implementation.sp, "groebner", expire)
    result = prove(regular, proposal)
    assert result["authority_pass"] is False
    assert result["reason"] == "TIMEOUT"


def test_frozen_semantic_frontend_and_untouched_replay_are_mandatory() -> None:
    x = sp.Symbol("x", real=True)
    document = {
        "variables": {"names": ["x"]},
        "construction": [],
        "constraints": [{"def": "x*x", "value": "2"}],
        "guards": ["AssumeGt(x,0)"],
        "answer": "x",
        "post_process": "",
    }
    proposal = TargetProposal((1, 0, -2), 1, Fraction(1), Fraction(2))
    result = prove_semantic_document(document, proposal)
    assert result["authority_pass"] is True
    assert result["semantic_frontend"]["reused_frozen_lift"] is True
    assert result["independent_replay"]["untouched_source_dsl_replay"] is True
