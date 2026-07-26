"""Internal solution formatting helpers used by compatibility API."""

from __future__ import annotations

from typing import Any


def get_solution_str(info: dict[str, Any], idx: int = 0, precision: int | None = None) -> list[str]:
    """Return solution values as formatted strings."""
    hp_solutions = info.get("hp_solutions")
    if hp_solutions is None or idx >= len(hp_solutions):
        sol = info["all_solutions"][idx]
        return [f"{val:.15f}" for val in sol]

    try:
        from mpmath import mp, nstr

        prec = precision or int(info["precision_achieved"]) + 5
        mp.dps = prec + 5
        hp_sol = hp_solutions[idx]
        return [nstr(val, prec) for val in hp_sol]
    except ImportError:
        sol = info["all_solutions"][idx]
        return [f"{val:.15f}" for val in sol]


def get_hp_values(info: dict[str, Any], idx: int = 0) -> list[Any]:
    """Return high-precision values when available, otherwise float solution values."""
    hp_solutions = info.get("hp_solutions")
    if hp_solutions is None or idx >= len(hp_solutions):
        return info["all_solutions"][idx]
    return hp_solutions[idx]
