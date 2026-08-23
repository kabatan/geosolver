"""Guard handler registry metadata."""

from __future__ import annotations

COMPARE_GUARD_NAMES: tuple[str, ...] = (
    "AssumeGt",
    "AssumeGe",
    "AssumeLt",
    "AssumeLe",
    "AssumeEq",
    "AssumeNe",
)

RESIDUAL_GUARD_TEMPLATES: dict[str, str] = {
    "AssumeCollinear": "Collinear({0}, {1}, {2})",
    "AssumeParallel": "Parallel({0}, {1})",
    "AssumePerpendicular": "Perpendicular({0}, {1})",
    "AssumeCyclic": "AreConcyclic({0}, {1}, {2}, {3})",
    "AssumeOrder": "OnLine({0}, {1}, {2}, ordered=True)",
}

TRIANGLE_CLASS_GUARDS: dict[str, str] = {
    "AssumeAcute": "acute",
    "AssumeRight": "right",
    "AssumeObtuse": "obtuse",
}


def is_compare_guard(name: str) -> bool:
    return name in COMPARE_GUARD_NAMES


def get_residual_guard_template(name: str) -> str | None:
    return RESIDUAL_GUARD_TEMPLATES.get(name)


def get_triangle_class(name: str) -> str | None:
    return TRIANGLE_CLASS_GUARDS.get(name)
