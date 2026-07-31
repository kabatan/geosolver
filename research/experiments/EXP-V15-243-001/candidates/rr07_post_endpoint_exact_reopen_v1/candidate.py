"""Disposable post-endpoint exact RR-07 SSS/Heron inverse.

This module consumes exact invariants already emitted after HP.  It does not
parse or compile source DSL.  A caller supplies the untouched replay function;
both reflection branches must pass that replay before either can be retained.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
from typing import Callable, Mapping, Sequence


SCHEMA = "geotarget.rr07-post-endpoint-exact-reopen/v1"
ACTIONS = ("CONTACT_AT_A_ON_AB", "CONTACT_AT_A_ON_AC", "CONTACT_AT_B_ON_BC")


class Inapplicable(ValueError):
    pass


def _qq(value: object) -> Fraction:
    if isinstance(value, bool):
        raise Inapplicable("BOOLEAN_INVARIANT")
    try:
        result = value if isinstance(value, Fraction) else Fraction(str(value))
    except (ValueError, ZeroDivisionError) as error:
        raise Inapplicable("NONRATIONAL_EXACT_INVARIANT") from error
    return result


@dataclass(frozen=True)
class Radical:
    coefficient: Fraction
    radicand: Fraction

    def __post_init__(self) -> None:
        if self.radicand <= 0:
            raise Inapplicable("NONPOSITIVE_RADICAND")

    @property
    def square(self) -> Fraction:
        return self.coefficient * self.coefficient * self.radicand

    def negated(self) -> "Radical":
        return Radical(-self.coefficient, self.radicand)

    def record(self) -> dict[str, str]:
        return {
            "coefficient": str(self.coefficient),
            "sqrt_radicand": str(self.radicand),
        }


@dataclass(frozen=True)
class Branch:
    base_left: tuple[Fraction, Fraction]
    base_right_x: Radical
    apex_x: Radical
    apex_y: Radical

    def record(self) -> dict[str, object]:
        return {
            "base_left": [str(self.base_left[0]), str(self.base_left[1])],
            "base_right": [self.base_right_x.record(), "0"],
            "apex": [self.apex_x.record(), self.apex_y.record()],
        }


@dataclass(frozen=True)
class Reconstruction:
    action: str
    side_a: Fraction
    side_b: Fraction
    side_c: Fraction
    tangent: Fraction
    cx_factor: Fraction
    cy_squared: Fraction
    heron_discriminant: Fraction
    branches: tuple[Branch, Branch]


def reconstruct(
    *,
    side_a: object,
    side_b: object,
    side_c: object,
    tangent: object,
    action: str,
) -> Reconstruction:
    """Invert one exact tangent relation and retain both SSS reflections.

    The action determines which named vertex/side was normalized upstream; it
    never changes the algebra.  In its local normalization the exact relation
    is ``a = b + c - 2t`` and the base has length ``c``.
    """

    if action not in ACTIONS:
        raise Inapplicable("UNKNOWN_SOURCE_TYPED_ACTION")
    a, b, c, t = map(_qq, (side_a, side_b, side_c, tangent))
    if min(a, b, c, t) <= 0:
        raise Inapplicable("NONPOSITIVE_SIDE_OR_TANGENT")
    if a != b + c - 2 * t:
        raise Inapplicable("TANGENT_LENGTH_IDENTITY_MISMATCH")
    if not (a + b > c and a + c > b and b + c > a):
        raise Inapplicable("NONSTRICT_TRIANGLE")

    a2, b2, c2 = a * a, b * b, c * c
    numerator = b2 + c2 - a2
    # Cx = numerator/(2*c) = (numerator/(2*c^2))*sqrt(c^2).
    cx_factor = numerator / (2 * c2)
    cx_squared = numerator * numerator / (4 * c2)
    cy_squared = b2 - cx_squared
    heron = 4 * b2 * c2 - numerator * numerator
    if cy_squared <= 0 or heron <= 0 or heron != 4 * c2 * cy_squared:
        raise Inapplicable("HERON_STRICT_REALITY_FAILED")

    base = Radical(Fraction(1), c2)
    apex_x = Radical(cx_factor, c2)
    positive_y = Radical(Fraction(1), cy_squared)
    branches = (
        Branch((Fraction(0), Fraction(0)), base, apex_x, positive_y),
        Branch((Fraction(0), Fraction(0)), base, apex_x, positive_y.negated()),
    )
    return Reconstruction(
        action=action,
        side_a=a,
        side_b=b,
        side_c=c,
        tangent=t,
        cx_factor=cx_factor,
        cy_squared=cy_squared,
        heron_discriminant=heron,
        branches=branches,
    )


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()


def replay_both_reflections(
    reconstruction: Reconstruction,
    *,
    source_sha256: str,
    endpoint_sha256: str,
    replay: Callable[[Mapping[str, object]], Mapping[str, object]],
) -> dict[str, object]:
    """Require untouched exact replay for each branch; never claim completeness."""

    if len(source_sha256) != 64 or len(endpoint_sha256) != 64:
        raise Inapplicable("SOURCE_OR_ENDPOINT_DIGEST_MALFORMED")
    accepted = []
    for ordinal, branch in enumerate(reconstruction.branches):
        request = {
            "schema_version": SCHEMA,
            "source_sha256": source_sha256,
            "endpoint_float64_sha256": endpoint_sha256,
            "action": reconstruction.action,
            "reflection_ordinal": ordinal,
            "exact_triangle": branch.record(),
            "source_parser_or_compiler_modified": False,
        }
        response = replay(request)
        valid = bool(
            isinstance(response, Mapping)
            and response.get("source_sha256") == source_sha256
            and response.get("endpoint_float64_sha256") == endpoint_sha256
            and response.get("reflection_ordinal") == ordinal
            and response.get("construction_exact") is True
            and response.get("constraints_exact") is True
            and response.get("guards_and_definedness_exact") is True
            and response.get("raw_target_link_exact") is True
            and response.get("untouched_source_replay") is True
            and response.get("source_parser_or_compiler_modified") is False
        )
        if valid:
            accepted.append(
                {
                    "reflection_ordinal": ordinal,
                    "replay_signature_sha256": _digest(dict(response)),
                }
            )
    return {
        "schema_version": SCHEMA,
        "status": "PROOF_READY_PREJOIN" if accepted else "NO_REPLAYED_BRANCH",
        "source_sha256": source_sha256,
        "endpoint_float64_sha256": endpoint_sha256,
        "action": reconstruction.action,
        "reflection_branch_count": 2,
        "accepted_reflection_count": len(accepted),
        "accepted": accepted,
        "both_reflections_enumerated": True,
        "authority_pass": False,
        "target_release": False,
        "target_set_completeness_claim": False,
        "source_parser_or_compiler_modified": False,
        "truth_case_family_target_count_outcome_routing": False,
    }


def exact_squared_distances(value: Reconstruction) -> tuple[Fraction, Fraction, Fraction]:
    """Return BC^2, CA^2, AB^2 directly from reconstructed coordinates."""

    branch = value.branches[0]
    ab2 = branch.base_right_x.square
    ac2 = branch.apex_x.square + branch.apex_y.square
    bc2 = (
        (branch.base_right_x.coefficient - branch.apex_x.coefficient) ** 2
        * branch.base_right_x.radicand
        + branch.apex_y.square
    )
    return bc2, ac2, ab2
