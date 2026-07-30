"""Source-only generated cases; no corpus/truth inputs."""

from __future__ import annotations

from dataclasses import dataclass
import math

from connector import ConnectorProblem, Predicate, interval


@dataclass(frozen=True)
class GeneratedCase:
    name: str
    expected_authority: bool
    problem: ConnectorProblem


def cases() -> tuple[GeneratedCase, ...]:
    x, u = interval.Var(0), interval.Var(1)
    offset = 1_048_576
    root = math.sqrt(2.0)
    base = ConnectorProblem(
        variables=("x", "u"),
        source_equations=("x - 1048576 - u", "u**2 - 2"),
        target_expression="x - 1048576",
        residual_dag=(x - offset - u, u**2 - 2),
        target_dag=x - offset,
        predicates=(Predicate(u, "u", "gt0"),),
        safe_endpoint=(offset + root, root),
        trust_radius=(1.0 / 64.0, 1.0 / 64.0),
        candidate_coefficients_high_to_low=(1, 0, -2),
        descriptor_selection_interval=("1", "2"),
    )

    z = interval.Var(0)
    close_root = 1.0 + 1.0 / math.sqrt(524_288.0)
    close = ConnectorProblem(
        variables=("z",),
        source_equations=("(z - 1)**2 - 1/524288",),
        target_expression="z",
        residual_dag=((z - 1) ** 2 - 1.0 / 524_288.0,),
        target_dag=z,
        predicates=(Predicate(z - 1, "z - 1", "gt0"),),
        safe_endpoint=(close_root,),
        trust_radius=(1.0 / 1_048_576.0,),
        candidate_coefficients_high_to_low=(524288, -1048576, 524287),
        descriptor_selection_interval=("1", "501/500"),
    )

    affine = ConnectorProblem(
        **{
            **base.__dict__,
            "target_expression": "3*(x - 1048576) + 5",
            "target_dag": 3 * (x - offset) + 5,
            "candidate_coefficients_high_to_low": (1, -10, 7),
            "descriptor_selection_interval": ("9", "10"),
        }
    )

    pu, px = interval.Var(0), interval.Var(1)
    permuted_scaled = ConnectorProblem(
        variables=("u", "x"),
        source_equations=("3*(u**2 - 2)", "-5*(x - 1048576 - u)"),
        target_expression="x - 1048576",
        residual_dag=(3 * (pu**2 - 2), -5 * (px - offset - pu)),
        target_dag=px - offset,
        predicates=(Predicate(pu, "u", "gt0"),),
        safe_endpoint=(root, offset + root),
        trust_radius=(1.0 / 64.0, 1.0 / 64.0),
        candidate_coefficients_high_to_low=(1, 0, -2),
        descriptor_selection_interval=("1", "2"),
    )

    near_boundary = ConnectorProblem(
        **{
            **base.__dict__,
            "predicates": (Predicate(u**2 - 2, "u**2 - 2", "gt0"),),
        }
    )
    nonsquare = ConnectorProblem(
        **{
            **base.__dict__,
            "source_equations": ("x - 1048576 - u",),
            "residual_dag": (x - offset - u,),
        }
    )
    opaque = ConnectorProblem(
        **{
            **base.__dict__,
            "source_equations": ("x - 1048576 - u", "u"),
            "residual_dag": (x - offset - u, interval.unsupported("sin", u)),
            "opaque_callbacks": True,
        }
    )
    binding_mismatch = ConnectorProblem(
        **{
            **base.__dict__,
            "target_expression": "x - 1048575",
        }
    )

    return (
        GeneratedCase("cancellation-positive", True, base),
        GeneratedCase("close-conjugate-positive", True, close),
        GeneratedCase("affine-target-positive", True, affine),
        GeneratedCase("permutation-scale-positive", True, permuted_scaled),
        GeneratedCase("near-boundary-guard-negative", False, near_boundary),
        GeneratedCase("nonsquare-negative", False, nonsquare),
        GeneratedCase("opaque-negative", False, opaque),
        GeneratedCase("exact-binding-mismatch-negative", False, binding_mismatch),
    )


__all__ = ["GeneratedCase", "cases"]
