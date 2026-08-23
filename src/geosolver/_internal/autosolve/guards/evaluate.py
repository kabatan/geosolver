"""Guard evaluation for conditional constraints."""

from collections.abc import Callable, Sequence
from typing import Any


def _is_guard_satisfied(result: Any) -> bool:
    return result is None or bool(result)


def _guard_violations(
    guards: Sequence[Callable[[dict[str, Any]], bool] | str],
    context: dict[str, Any],
    options: dict[str, Any] | None = None,
) -> list[str]:
    evaluator = None if options is None else options.get("evaluator")
    violations: list[str] = []
    for index, guard in enumerate(guards):
        try:
            if callable(guard):
                ok = _is_guard_satisfied(guard(context))
            elif isinstance(guard, str) and callable(evaluator):
                ok = _is_guard_satisfied(evaluator(guard, context))
            else:
                violations.append(f"guard[{index}] unsupported guard type")
                continue
            if not ok:
                violations.append(f"guard[{index}] returned False")
        except Exception as exc:
            violations.append(f"guard[{index}] raised: {exc}")
    return violations


def _evaluate_guards(
    guards: Sequence[Callable[[dict[str, Any]], bool] | str],
    context: dict[str, Any],
    options: dict[str, Any] | None = None,
) -> list[str] | tuple[bool, str]:
    """Evaluate guards and optionally return violations-list contract.

    options:
      - return_violations: True  -> return list[str] of violations
      - evaluator: callable(expr, context) for string guard expressions
    """
    violations = _guard_violations(guards, context, options)
    if options and options.get("return_violations"):
        return violations
    if violations:
        return False, violations[0]
    return True, ""
