"""Guard-penalty construction helpers."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from geosolver.problem.ir.compiler import safe_eval_expr

from .evaluate import _evaluate_guards


@dataclass(frozen=True)
class GuardPenalty:
    guards: Sequence[Callable[[dict[str, Any]], bool] | str]
    weight: float

    def __call__(self, context: dict[str, Any]) -> float:
        violations = _evaluate_guards(
            self.guards,
            context,
            options={"return_violations": True, "evaluator": safe_eval_expr},
        )
        count = len(violations) if isinstance(violations, list) else int(not violations[0])
        if count <= 0:
            return 0.0
        penalty = float(self.weight) * float(count)
        context.setdefault("_guard_violations", violations)
        context["_guard_penalty"] = penalty
        return penalty


def _create_guard_penalty(
    guards: Sequence[Callable[[dict[str, Any]], bool] | str],
    weight: float = 1.0,
) -> Callable[[dict[str, Any]], float]:
    """Create penalty function that counts violated guards."""
    return GuardPenalty(guards=guards, weight=float(weight))
