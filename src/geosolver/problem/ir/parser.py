"""
IR Parser and Validation

JSON/Dict形式のIRを読み込み、検証してIRSpecオブジェクトを生成する。
"""

import json
import math
import re
from typing import Any

from geosolver.problem.ir.compiler import validate_expr_safety
from geosolver.problem.ir.errors import IRValidationError
from geosolver.problem.ir.parser_helpers import (
    parse_constraints_and_values,
    parse_construction,
    parse_guards,
)
from geosolver.problem.ir.schema import IRSpec, IRVariableSpec

# ---------------------------------------------------------------------------
# Validation Logic (Migrated from aimo_ir.py)
# ---------------------------------------------------------------------------

_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _ensure_identifier(name: str, *, where: str) -> None:
    if not isinstance(name, str) or not name:
        raise IRValidationError(f"{where}: name must be non-empty string")
    if not _NAME_RE.fullmatch(name):
        raise IRValidationError(f"{where}: invalid identifier: {name!r}")


def _as_list(value: Any, *, where: str) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    raise IRValidationError(f"{where}: must be a list")


def _parse_bounds(bounds: Any, n: int) -> list[tuple[Any, Any] | None] | None:
    if bounds is None:
        return None
    if not isinstance(bounds, list):
        raise IRValidationError("bounds: must be list or null")
    # Shorthand: [lo, hi] applied to all variables
    if (
        len(bounds) == 2
        and not isinstance(bounds[0], list | tuple | dict)
        and not isinstance(bounds[1], list | tuple | dict)
    ):
        bounds = [bounds for _ in range(n)]
    if len(bounds) != n:
        raise IRValidationError("bounds: length must equal variable count")

    out: list[tuple[float, float] | None] = []
    for i, b in enumerate(bounds):
        if b is None:
            out.append(None)
            continue
        if isinstance(b, list | tuple) and len(b) == 2:
            try:
                lo_raw, hi_raw = b[0], b[1]
                lo = None if lo_raw is None else float(lo_raw)
                hi = None if hi_raw is None else float(hi_raw)
            except Exception as e:
                raise IRValidationError(f"bounds[{i}]: failed to parse lo/hi: {e}") from e
            if any(value is not None and not math.isfinite(value) for value in (lo, hi)):
                raise IRValidationError(f"bounds[{i}]: finite endpoints required")
            if lo is not None and hi is not None and lo > hi:
                raise IRValidationError(f"bounds[{i}]: must satisfy lo <= hi")
            out.append((lo_raw, hi_raw))
            continue
        raise IRValidationError(f"bounds[{i}]: must be [lo, hi] or null")

    return out


def load_ir(obj: str | dict[str, Any]) -> IRSpec:
    """Load and validate IR."""

    if isinstance(obj, str):
        try:
            data = json.loads(obj)
        except Exception as e:
            raise IRValidationError(f"IR JSON parse error: {e}") from e
    elif isinstance(obj, dict):
        data = obj
    else:
        raise IRValidationError("IR must be dict or JSON string")

    task = data.get("task")
    if task != "solve":
        raise IRValidationError("only task='solve' is implemented")
    if data.get("maximize") not in (None, False) or data.get("post_process") not in (None, ""):
        raise IRValidationError("maximize and post_process are not implemented")

    variables_raw = data.get("variables")
    if not isinstance(variables_raw, dict):
        raise IRValidationError("variables must be an object")

    names = variables_raw.get("names")
    n = variables_raw.get("n")  # type: ignore

    if names is not None:
        if not isinstance(names, list) or not all(isinstance(x, str) for x in names):
            raise IRValidationError("variables.names must be list[str]")
        for nm in names:
            _ensure_identifier(nm, where="variables.names")

    if n is not None and (type(n) is not int or n < 0):
        raise IRValidationError("variables.n must be a nonnegative int")
    if names is not None and len(set(names)) != len(names):
        raise IRValidationError("duplicate variable name")
    if names is not None and n is not None and len(names) != n:
        raise IRValidationError("variables.n disagrees with names")

    # IRVariableSpec生成
    var_spec = IRVariableSpec(names=list(names) if names is not None else None, n=n)

    m = data.get("m")
    if m is not None and not isinstance(m, int):
        raise IRValidationError("m must be int or null")

    # bounds (prefer top-level, but accept variables.bounds for backward compatibility)
    bounds_source = data.get("bounds")
    if bounds_source is None and isinstance(variables_raw, dict):
        bounds_source = variables_raw.get("bounds")
    bounds = _parse_bounds(bounds_source, n=len(var_spec.resolved_names()))

    v_raw = data.get("v")
    # vのパースは後回し（数値か文字列か不明なため）
    # ここではRawデータのまま保持できないので、とりあえずリストとして読み取る
    v_list = _as_list(v_raw, where="v") if v_raw is not None else []

    # Construction
    construction_raw = _as_list(data.get("construction"), where="construction")
    construction = parse_construction(construction_raw)

    # Constraints
    constraints_raw = _as_list(data.get("constraints"), where="constraints")

    constraints, inferred_v = parse_constraints_and_values(constraints_raw)

    # vの決定
    if v_raw is None:
        v_list = inferred_v
    if len(v_list) != len(constraints):
        raise IRValidationError("v length must equal constraint count")
    if m is not None and m != len(constraints):
        raise IRValidationError("m disagrees with constraint count")
    all_names = var_spec.resolved_names() + [item.name for item in construction]
    if len(set(all_names)) != len(all_names):
        raise IRValidationError("duplicate variable or construction name")

    # Guards
    guards_raw = _as_list(data.get("guards"), where="guards")
    guards = parse_guards(guards_raw)

    answer_expr = data.get("answer")
    if answer_expr is not None:
        validate_expr_safety(str(answer_expr))
        answer_expr = str(answer_expr).strip()

    objective_expr = data.get("objective")
    if objective_expr is not None:
        validate_expr_safety(str(objective_expr))
        objective_expr = str(objective_expr).strip()

    return IRSpec(
        task=task,
        variables=var_spec,
        m=m,
        bounds=bounds,
        v=v_list,
        construction=construction,
        constraints=constraints,
        guards=guards,
        answer_expr=answer_expr,
        post_process=data.get("post_process"),
        objective_expr=objective_expr,
        maximize=bool(data.get("maximize", False)),
    )
