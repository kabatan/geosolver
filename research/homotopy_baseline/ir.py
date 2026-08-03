"""JSON-safe intermediate representation for the homotopy baseline."""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any


@dataclass(frozen=True)
class Monomial:
    exponents: tuple[int, ...]
    numerator: int
    denominator: int = 1

    def json(self) -> dict[str, Any]:
        return {
            "exponents": list(self.exponents),
            "numerator": self.numerator,
            "denominator": self.denominator,
        }


@dataclass(frozen=True)
class Polynomial:
    """A rational-coefficient multivariate polynomial."""

    terms: tuple[Monomial, ...]

    def json(self) -> dict[str, Any]:
        return {"terms": [term.json() for term in self.terms]}


@dataclass(frozen=True)
class SignCondition:
    polynomial: Polynomial
    relation: str
    source: str = ""

    def json(self) -> dict[str, Any]:
        return {
            "polynomial": self.polynomial.json(),
            "relation": self.relation,
            "source": self.source,
        }


@dataclass(frozen=True)
class Admission:
    mode: str
    supported: bool
    stage: str
    reasons: tuple[str, ...] = ()
    calls: tuple[str, ...] = ()
    variable_count: int = 0
    equation_count: int = 0
    branch_count: int = 1

    def json(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "supported": self.supported,
            "stage": self.stage,
            "reasons": list(self.reasons),
            "calls": list(self.calls),
            "variable_count": self.variable_count,
            "equation_count": self.equation_count,
            "branch_count": self.branch_count,
        }


@dataclass
class Compilation:
    """A complete rational polynomial formulation and its guards."""

    source_sha256: str
    mode: str
    variables: tuple[str, ...]
    equations: list[Polynomial]
    inequalities: list[SignCondition]
    target_variable: str
    target_expression: Polynomial
    admission: Admission
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def dimension(self) -> int:
        return len(self.variables)

    def json(self) -> dict[str, Any]:
        return {
            "schema_version": "geotarget.homotopy-baseline.polynomial/v1",
            "source_sha256": self.source_sha256,
            "mode": self.mode,
            "variables": list(self.variables),
            "equations": [equation.json() for equation in self.equations],
            "inequalities": [condition.json() for condition in self.inequalities],
            "target_variable": self.target_variable,
            "target_expression": self.target_expression.json(),
            "admission": self.admission.json(),
            "metadata": self.metadata,
        }


def fraction_to_pair(value: Fraction) -> tuple[int, int]:
    return int(value.numerator), int(value.denominator)
