"""Guard evaluation for conditional constraints."""

from typing import Any


def _is_guard_satisfied(result: Any) -> bool:
    return result is None or bool(result)
