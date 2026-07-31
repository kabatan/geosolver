"""Small source-only panel for single-prime stable Hensel coordinates."""

from __future__ import annotations

from dataclasses import dataclass
import copy
from typing import Mapping

import sympy as sp


@dataclass(frozen=True, slots=True)
class GeneratedCase:
    name: str
    category: str
    document: Mapping[str, object]
    expected: tuple[tuple[sp.Rational, ...], ...]


def _document(names, constraints, *, answer, guards=None, bounds=None):
    return {
        "task": "solve",
        "variables": {"names": list(names)},
        "construction": [],
        "constraints": list(constraints),
        "guards": list(guards or []),
        "bounds": bounds,
        "answer": answer,
        "post_process": None,
    }


def cases() -> tuple[GeneratedCase, ...]:
    return (
        GeneratedCase(
            "positive_rational_univariate", "positive",
            _document(["x"], [{"def": "3*x", "value": 2}], answer="x", bounds=[["-2", "2"]]),
            ((sp.Rational(2, 3),),),
        ),
        GeneratedCase(
            "positive_first_prime_degree_drop", "positive",
            _document(["x"], [{"def": "2*x", "value": 1}], answer="x", bounds=[["-2", "2"]]),
            ((sp.Rational(1, 2),),),
        ),
        GeneratedCase(
            "positive_rational_pair", "positive",
            _document(
                ["x", "y"],
                [{"def": "3*x", "value": 2}, {"def": "3*y", "value": -1}],
                answer="x-y", bounds=[["-2", "2"], ["-2", "2"]],
            ),
            ((sp.Rational(2, 3), sp.Rational(-1, 3)),),
        ),
        GeneratedCase(
            "positive_two_rational_branches", "positive",
            _document(
                ["x"], [{"def": "(x-1)*(x+1)", "value": 0}],
                answer="x*x", bounds=[["-2", "2"]],
            ),
            ((sp.Rational(-1),), (sp.Rational(1),)),
        ),
        GeneratedCase(
            "negative_singular", "singular",
            _document(["x"], [{"def": "x*x", "value": 0}], answer="x", bounds=[["-2", "2"]]),
            (),
        ),
        GeneratedCase(
            "negative_nonrational", "nonrational",
            _document(["x"], [{"def": "x*x", "value": 2}], answer="x*x", bounds=[["-2", "2"]]),
            (),
        ),
        GeneratedCase(
            "negative_unstable_between_moduli", "unstable",
            _document(["x"], [{"def": "3*x", "value": 5}], answer="x", bounds=[["-2", "2"]]),
            (),
        ),
    )


def source_projection(document: Mapping[str, object]) -> dict[str, object]:
    return {
        key: copy.deepcopy(document[key])
        for key in ("task", "variables", "construction", "constraints", "guards", "bounds")
    }


def permuted_pair_document() -> dict[str, object]:
    return _document(
        ["y", "x"],
        [{"def": "3*y", "value": -1}, {"def": "3*x", "value": 2}],
        answer="x-y", bounds=[["-2", "2"], ["-2", "2"]],
    )


def reversed_pair_document() -> dict[str, object]:
    value = copy.deepcopy(dict(cases()[2].document))
    value["constraints"] = list(reversed(value["constraints"]))
    return value


__all__ = [
    "GeneratedCase", "cases", "permuted_pair_document",
    "reversed_pair_document", "source_projection",
]
