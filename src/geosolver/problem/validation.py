from __future__ import annotations

import ast
import difflib
import json
import re
from typing import Any

from pydantic import ValidationError

from geosolver.problem.catalog import runtime_contracts, selector_values
from geosolver.problem.models import (
    GeometryProblem,
    PredicateCondition,
    RelationCondition,
    ValidationIssue,
    ValidationReport,
)

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_DANGEROUS = re.compile(
    r"(__|\b(?:import|exec|eval|open|compile|globals|locals|subprocess|os|sys)\b|[;`{}])",
    re.IGNORECASE,
)
_CONSTANTS = frozenset({"pi", "True", "False"})
_ALLOWED_AST_NODES = frozenset(
    {
        ast.Expression,
        ast.Constant,
        ast.Name,
        ast.Load,
        ast.BinOp,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
        ast.Pow,
        ast.UnaryOp,
        ast.USub,
        ast.UAdd,
        ast.Not,
        ast.Compare,
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
        ast.BoolOp,
        ast.And,
        ast.Or,
        ast.IfExp,
        ast.Call,
        ast.keyword,
        ast.Attribute,
        ast.Subscript,
        ast.Tuple,
        ast.List,
    }
)


def _issue(path: str, code: str, message: str) -> ValidationIssue:
    return ValidationIssue(path=path, code=code, message=message)


def _syntax_error_message(error: SyntaxError) -> str:
    column = error.offset or 0
    return f"式を解釈できません。{column}文字目付近を確認してください（{error.msg}）"


def _call_issues(path: str, call: ast.Call) -> list[ValidationIssue]:
    if not isinstance(call.func, ast.Name):
        return [_issue(path, "unsupported_call", "関数名を直接指定してください")]
    contracts = runtime_contracts()
    contract = contracts.get(call.func.id)
    if contract is None:
        suggestion = difflib.get_close_matches(call.func.id, sorted(contracts), n=1, cutoff=0.72)
        hint = f"。「{suggestion[0]}」の誤記ではありませんか？" if suggestion else ""
        return [
            _issue(
                path,
                "unknown_function",
                f"GeoSolver Geometry DSLに存在しない関数「{call.func.id}」です{hint}",
            )
        ]
    issues: list[ValidationIssue] = []
    if any(keyword.arg is None for keyword in call.keywords):
        issues.append(_issue(path, "argument_unpacking", "*argsと**kwargsは使用できません"))
    positional = len(call.args)
    if contract.max_positional is not None and positional > contract.max_positional:
        issues.append(_issue(path, "too_many_arguments", "位置引数が多すぎます"))
    keyword_names = [str(item.arg) for item in call.keywords if item.arg is not None]
    unknown = sorted(set(keyword_names) - contract.allowed_keywords)
    if unknown:
        issues.append(
            _issue(path, "unknown_keyword", f"存在しないkeywordです: {', '.join(unknown)}")
        )
    if call.func.id == "Intersect":
        selectors = {"n", "exclude", "near", "far"} & set(keyword_names)
        if len(selectors) > 1:
            issues.append(
                _issue(
                    path,
                    "conflicting_selectors",
                    "Intersectではn、exclude、near、farを同時に指定できません",
                )
            )
        for keyword in call.keywords:
            if keyword.arg != "n":
                continue
            if (
                not isinstance(keyword.value, ast.Constant)
                or isinstance(keyword.value.value, bool)
                or not isinstance(keyword.value.value, int)
                or keyword.value.value < 1
            ):
                issues.append(_issue(path, "invalid_selector", "nは1以上の整数です"))
    supplied = positional + len(set(keyword_names))
    if supplied < contract.min_args:
        issues.append(_issue(path, "too_few_arguments", "引数が不足しています"))
    configured_selectors = selector_values()
    for keyword in call.keywords:
        allowed = configured_selectors.get(str(keyword.arg))
        if allowed is None or not isinstance(keyword.value, ast.Constant):
            continue
        value = keyword.value.value
        if not any(type(candidate) is type(value) and candidate == value for candidate in allowed):
            issues.append(_issue(path, "invalid_selector", f"{keyword.arg}の値が不正です"))
    return issues


def _expression_issues(
    path: str,
    expression: str,
    available_names: set[str],
) -> tuple[list[ValidationIssue], ast.Expression | None]:
    issues: list[ValidationIssue] = []
    if not expression.strip():
        return [_issue(path, "empty_expression", "式を入力してください")], None
    if len(expression) > 16_384:
        issues.append(_issue(path, "too_long", "式が16384文字を超えています"))
    if _DANGEROUS.search(expression):
        issues.append(_issue(path, "unsafe_expression", "使用できない文字列を含んでいます"))
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as error:
        issues.append(_issue(path, "expression_syntax", _syntax_error_message(error)))
        return issues, None
    unsupported = next(
        (node for node in ast.walk(tree) if type(node) not in _ALLOWED_AST_NODES), None
    )
    if unsupported is not None:
        issues.append(
            _issue(path, "unsupported_ast", f"使用できない式要素です: {type(unsupported).__name__}")
        )
    if any(
        isinstance(node, ast.Attribute) and node.attr.startswith("_") for node in ast.walk(tree)
    ):
        issues.append(_issue(path, "private_attribute", "_で始まる属性は使用できません"))
    call_names: set[ast.Name] = set()
    for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
        if isinstance(call.func, ast.Name):
            call_names.add(call.func)
        issues.extend(_call_issues(path, call))
    unknown_names = sorted(
        {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node not in call_names
            and node.id not in available_names
            and node.id not in _CONSTANTS
        }
    )
    issues.extend(
        _issue(path, "unknown_name", f"未定義、または定義前の名前「{name}」です")
        for name in unknown_names
    )
    return issues, tree


def validate(problem: GeometryProblem | dict[str, Any]) -> ValidationReport:
    try:
        parsed = (
            problem
            if isinstance(problem, GeometryProblem)
            else GeometryProblem.model_validate(problem)
        )
    except ValidationError as error:
        return ValidationReport(
            valid=False,
            issues=[
                _issue(
                    ".".join(str(part) for part in item["loc"]),
                    str(item["type"]),
                    str(item["msg"]),
                )
                for item in error.errors(include_url=False)
            ],
        )

    issues: list[ValidationIssue] = []
    if not parsed.id.strip():
        issues.append(_issue("id", "empty", "idを入力してください"))
    construction_names = [item.name for item in parsed.constructions]
    if len(parsed.variables) != len(set(parsed.variables)):
        issues.append(_issue("variables", "duplicate", "変数名が重複しています"))
    if len(construction_names) != len(set(construction_names)):
        issues.append(_issue("constructions", "duplicate", "作図名が重複しています"))
    overlap = sorted(set(parsed.variables) & set(construction_names))
    if overlap:
        issues.append(
            _issue("variables", "name_collision", f"名前が重複しています: {', '.join(overlap)}")
        )
    for index, name in enumerate([*parsed.variables, *construction_names]):
        if not _IDENTIFIER.fullmatch(name):
            issues.append(_issue(f"identifiers[{index}]", "identifier", f"不正な名前です: {name}"))

    scope = set(parsed.variables)
    for index, construction in enumerate(parsed.constructions):
        path = f"constructions[{index}].expression"
        found, _tree = _expression_issues(path, construction.expression, scope)
        issues.extend(found)
        scope.add(construction.name)

    complete_scope = set(parsed.variables) | set(construction_names)
    for index, condition in enumerate(parsed.conditions):
        if isinstance(condition, RelationCondition):
            issues.extend(
                _expression_issues(f"conditions[{index}].left", condition.left, complete_scope)[0]
            )
            if isinstance(condition.right, str):
                issues.extend(
                    _expression_issues(
                        f"conditions[{index}].right", condition.right, complete_scope
                    )[0]
                )
        elif isinstance(condition, PredicateCondition):
            issues.extend(
                _expression_issues(
                    f"conditions[{index}].predicate", condition.predicate, complete_scope
                )[0]
            )
    target_issues, target_tree = _expression_issues("target", parsed.target, complete_scope)
    issues.extend(target_issues)
    if target_tree is not None and isinstance(target_tree.body, ast.Call):
        call = target_tree.body
        if isinstance(call.func, ast.Name):
            contract = runtime_contracts().get(call.func.id)
            if contract is not None and contract.result_kind != "scalar":
                issues.append(
                    _issue("target", "target_not_scalar", "targetはscalar式にしてください")
                )

    normalized = parsed.model_dump(mode="json")
    try:
        json.dumps(normalized, allow_nan=False)
    except ValueError as error:
        issues.append(_issue("$", "non_finite", str(error)))
    if not issues:
        from geosolver.problem.compiler import ProblemCompileError, compile_problem

        try:
            compile_problem(parsed)
        except ProblemCompileError as error:
            issues.append(_issue(error.path, error.code, str(error)))
    return ValidationReport(
        valid=not issues,
        issues=issues,
        normalized_problem=normalized if not issues else None,
    )
