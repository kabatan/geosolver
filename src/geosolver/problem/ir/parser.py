"""
IR Parser and Validation

JSON/Dict形式のIRを読み込み、検証してIRSpecオブジェクトを生成する。
"""

import ast
import json
import re
from typing import Any, Dict, List, Optional, Tuple, Union, Sequence

from geosolver.problem.ir.schema import IRSpec, IRVariableSpec, IRConstruction
from geosolver.problem.ir.errors import IRValidationError
from geosolver.problem.ir.compiler import validate_expr_safety, extract_names
from geosolver.problem.ir.parser_helpers import (
    parse_construction,
    parse_constraints_and_values,
    parse_guards,
)

# ---------------------------------------------------------------------------
# Validation Logic (Migrated from aimo_ir.py)
# ---------------------------------------------------------------------------

_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

def _ensure_identifier(name: str, *, where: str) -> None:
    if not isinstance(name, str) or not name:
        raise IRValidationError(f"{where}: name must be non-empty string")
    if not _NAME_RE.fullmatch(name):
        raise IRValidationError(f"{where}: invalid identifier: {name!r}")

def _as_list(value: Any, *, where: str) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    raise IRValidationError(f"{where}: must be a list")

def _parse_bounds(bounds: Any, n: int) -> Optional[List[Optional[Tuple[float, float]]]]:
    if bounds is None:
        return None
    if not isinstance(bounds, list):
        raise IRValidationError("bounds: must be list or null")
    # Shorthand: [lo, hi] applied to all variables
    if (
        len(bounds) == 2
        and not isinstance(bounds[0], (list, tuple, dict))
        and not isinstance(bounds[1], (list, tuple, dict))
    ):
        try:
            lo_global = float(bounds[0])
            hi_global = float(bounds[1])
        except Exception as e:
            raise IRValidationError(f"bounds: failed to parse lo/hi: {e}") from e
        if not (lo_global < hi_global):
            raise IRValidationError("bounds: must satisfy lo < hi")
        return [(lo_global, hi_global) for _ in range(n)]
    # nチェックは省略（変数の数がコンテキストによるため）

    out: List[Optional[Tuple[float, float]]] = []
    for i, b in enumerate(bounds):
        if b is None:
            out.append(None)
            continue
        if (
            isinstance(b, (list, tuple))
            and len(b) == 2
        ):
            try:
                lo_raw, hi_raw = b[0], b[1]
                # 簡単のためfloat変換のみ
                lo = float(lo_raw)
                hi = float(hi_raw)
            except Exception as e:
                raise IRValidationError(f"bounds[{i}]: failed to parse lo/hi: {e}") from e
            if not (lo < hi):
                raise IRValidationError(f"bounds[{i}]: must satisfy lo < hi")
            out.append((lo, hi))
            continue
        raise IRValidationError(f"bounds[{i}]: must be [lo, hi] or null")

    return out

def load_ir(obj: Union[str, Dict[str, Any]]) -> IRSpec:
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
    if task not in ("solve", "optimize"):
        raise IRValidationError("task must be 'solve' or 'optimize'")

    variables_raw = data.get("variables")
    if not isinstance(variables_raw, dict):
        raise IRValidationError("variables must be an object")

    names = variables_raw.get("names")
    n = variables_raw.get("n") # type: ignore

    if names is not None:
        if not isinstance(names, list) or not all(isinstance(x, str) for x in names):
            raise IRValidationError("variables.names must be list[str]")
        for nm in names:
            _ensure_identifier(nm, where="variables.names")

    if n is not None:
        if not isinstance(n, int):
            raise IRValidationError("variables.n must be int")

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
    if not v_list:
        v_list = inferred_v
    
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
