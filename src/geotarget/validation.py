from __future__ import annotations

import ast
import difflib
import json
import re
from copy import deepcopy
from functools import lru_cache
from typing import Any

from pydantic import ValidationError

from geotarget.dsl_contract import runtime_contracts, selector_values
from geotarget.models import V15Problem, ValidationIssue, ValidationReport

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_DANGEROUS = re.compile(
    r"(__|\b(?:import|exec|eval|open|compile|globals|locals|subprocess|os|sys)\b|[;`{}])",
    re.IGNORECASE,
)

_V15_CONSTANTS = frozenset({"pi"})

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


@lru_cache(maxsize=1)
def _v15_functions() -> frozenset[str]:
    return frozenset(runtime_contracts())


def _function_suggestion(name: str, functions: frozenset[str]) -> str | None:
    case_match = next(
        (candidate for candidate in functions if candidate.casefold() == name.casefold()),
        None,
    )
    if case_match is not None:
        return case_match
    matches = difflib.get_close_matches(name, sorted(functions), n=1, cutoff=0.72)
    return matches[0] if matches else None


def _issue(path: str, code: str, message: str) -> ValidationIssue:
    return ValidationIssue(path=path, code=code, message=message)


def _runtime_call_issues(path: str, call: ast.Call) -> list[ValidationIssue]:
    if not isinstance(call.func, ast.Name):
        return []
    contract = runtime_contracts().get(call.func.id)
    if contract is None:
        return []
    issues: list[ValidationIssue] = []
    if any(keyword.arg is None for keyword in call.keywords):
        issues.append(
            _issue(
                path,
                "argument_unpacking",
                f"{call.func.id}では*argsや**kwargsを使用できません",
            )
        )
    positional_count = len(call.args)
    if (
        contract.max_positional is not None
        and positional_count > contract.max_positional
    ):
        issues.append(
            _issue(
                path,
                "too_many_arguments",
                f"{call.func.id}の位置引数が多すぎます（最大{contract.max_positional}個）",
            )
        )
    keywords = [keyword for keyword in call.keywords if keyword.arg is not None]
    keyword_names = [str(keyword.arg) for keyword in keywords]
    unknown = sorted(set(keyword_names) - contract.allowed_keywords)
    if unknown:
        issues.append(
            _issue(
                path,
                "unknown_keyword",
                f"{call.func.id}に存在しないkeywordです: {', '.join(unknown)}",
            )
        )
    duplicates = sorted(
        {
            name
            for name in keyword_names
            if name in contract.parameters[:positional_count]
            or keyword_names.count(name) > 1
        }
    )
    if duplicates:
        issues.append(
            _issue(
                path,
                "duplicate_argument",
                f"{call.func.id}の引数が重複しています: {', '.join(duplicates)}",
            )
        )
    supplied_count = positional_count + len(set(keyword_names))
    if supplied_count < contract.min_args:
        issues.append(
            _issue(
                path,
                "too_few_arguments",
                f"{call.func.id}には少なくとも{contract.min_args}個の引数が必要です",
            )
        )
    available_slots = set(contract.parameters) | set(contract.allowed_keywords)
    if (
        not contract.variadic
        and available_slots
        and supplied_count > len(available_slots)
        and not unknown
    ):
        issues.append(
            _issue(path, "too_many_arguments", f"{call.func.id}の引数が多すぎます")
        )
    configured_selectors = selector_values()
    for keyword in keywords:
        allowed_values = configured_selectors.get(str(keyword.arg))
        if allowed_values is None or not isinstance(keyword.value, ast.Constant):
            continue
        value = keyword.value.value
        if not any(
            type(candidate) is type(value) and candidate == value
            for candidate in allowed_values
        ):
            issues.append(
                _issue(
                    path,
                    "invalid_selector",
                    f"{keyword.arg}の値がV15で許可されていません",
                )
            )
    return issues


def _ast_contract_issues(path: str, tree: ast.Expression) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    unsupported = next(
        (node for node in ast.walk(tree) if type(node) not in _ALLOWED_AST_NODES),
        None,
    )
    if unsupported is not None:
        issues.append(
            _issue(
                path,
                "unsupported_ast",
                f"V15で使用できない式要素です: {type(unsupported).__name__}",
            )
        )
    private_attribute = next(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute) and node.attr.startswith("_")
        ),
        None,
    )
    if private_attribute is not None:
        issues.append(
            _issue(path, "private_attribute", "_で始まる属性は使用できません")
        )
    contracts = runtime_contracts()
    for subscript in (
        node for node in ast.walk(tree) if isinstance(node, ast.Subscript)
    ):
        value = subscript.value
        if (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and (contract := contracts.get(value.func.id)) is not None
            and contract.result_kind == "scalar"
        ):
            issues.append(
                _issue(
                    path,
                    "invalid_subscript",
                    f"scalarを返す{value.func.id}には添字を使用できません",
                )
            )
    return issues


def _semantic_expression_issues(
    *, path: str, tree: ast.Expression, available_names: set[str]
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    issues.extend(_ast_contract_issues(path, tree))
    functions = _v15_functions()
    call_names: set[ast.Name] = set()
    for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
        if not isinstance(call.func, ast.Name):
            issues.append(
                ValidationIssue(
                    path=path,
                    code="unsupported_call",
                    message="V15の関数は、関数名を直接指定して呼び出してください",
                )
            )
            continue
        call_names.add(call.func)
        if call.func.id not in functions:
            suggestion = _function_suggestion(call.func.id, functions)
            hint = f"。「{suggestion}」の誤記ではありませんか？" if suggestion else ""
            issues.append(
                ValidationIssue(
                    path=path,
                    code="unknown_function",
                    message=f"V15に存在しない関数「{call.func.id}」です{hint}",
                )
            )
            continue
        issues.extend(_runtime_call_issues(path, call))

    unknown_names = sorted(
        {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node not in call_names
            and node.id not in available_names
            and node.id not in _V15_CONSTANTS
        }
    )
    for name in unknown_names:
        issues.append(
            ValidationIssue(
                path=path,
                code="unknown_name",
                message=f"未定義、または定義前に参照された名前「{name}」です",
            )
        )
    return issues


def _syntax_error_message(expression: str, error: SyntaxError) -> str:
    # Parentheses inside selector strings (for example vertex="A") are data,
    # not V15 grouping.  Ignore quoted text so the recovery hint never sends
    # the user looking for a bracket that is not actually structural.
    opening = 0
    closing = 0
    quote = ""
    escaped = False
    for character in expression:
        if quote:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = ""
            continue
        if character in {'"', "'"}:
            quote = character
        elif character == "(":
            opening += 1
        elif character == ")":
            closing += 1
    if opening != closing:
        if opening > closing:
            difference = opening - closing
            detail = f"閉じ括弧「)」が{difference}個不足しています"
        else:
            difference = closing - opening
            detail = f"閉じ括弧「)」が{difference}個多すぎます"
        return (
            f"括弧が対応していません（「(」{opening}個／「)」{closing}個）。"
            f"{detail}。自動補完で式の一部が重複した可能性もあるため、"
            "この条件を開いて式を入力し直してください"
        )
    column = error.offset or 0
    return f"式を解釈できません。{column}文字目付近を確認してください（{error.msg}）"


def _expressions(problem: V15Problem) -> list[tuple[str, str]]:
    values = [
        (f"construction[{index}].expr", item.expr)
        for index, item in enumerate(problem.construction)
    ]
    values.extend(
        (f"constraints[{index}].def", item.definition)
        for index, item in enumerate(problem.constraints)
    )
    values.extend(
        (f"constraints[{index}].value", item.value)
        for index, item in enumerate(problem.constraints)
        if isinstance(item.value, str)
    )
    values.extend((f"guards[{index}]", item) for index, item in enumerate(problem.guards))
    values.append(("answer", problem.answer))
    if problem.post_process:
        values.append(("post_process", problem.post_process))
    return values


def validate(problem: V15Problem | dict[str, Any]) -> ValidationReport:
    try:
        parsed = problem if isinstance(problem, V15Problem) else V15Problem.model_validate(problem)
    except ValidationError as error:
        issues = [
            ValidationIssue(
                path=".".join(str(part) for part in item["loc"]),
                code=str(item["type"]),
                message=str(item["msg"]),
            )
            for item in error.errors(include_url=False)
        ]
        return ValidationReport(valid=False, issues=issues)

    issues: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    names = parsed.variables.names
    if len(names) != len(set(names)):
        issues.append(
            ValidationIssue(
                path="variables.names", code="duplicate", message="variable names must be unique"
            )
        )
    construction_names = [item.name for item in parsed.construction]
    if len(construction_names) != len(set(construction_names)):
        issues.append(
            ValidationIssue(
                path="construction", code="duplicate", message="construction names must be unique"
            )
        )
    overlap = sorted(set(names) & set(construction_names))
    if overlap:
        issues.append(
            ValidationIssue(
                path="variables.names",
                code="name_collision",
                message=f"variables and construction names overlap: {', '.join(overlap)}",
            )
        )
    for index, name in enumerate([*names, *construction_names]):
        if not _IDENTIFIER.fullmatch(name):
            issues.append(
                ValidationIssue(
                    path=f"identifiers[{index}]",
                    code="identifier",
                    message=f"invalid identifier: {name}",
                )
            )
    parsed_trees: dict[str, ast.Expression] = {}
    for path, expression in _expressions(parsed):
        if not expression.strip():
            issues.append(
                ValidationIssue(
                    path=path,
                    code="empty_expression",
                    message="expression must not be empty",
                )
            )
            continue
        if len(expression) > 16_384:
            issues.append(
                ValidationIssue(
                    path=path, code="too_long", message="expression exceeds 16384 characters"
                )
            )
        if _DANGEROUS.search(expression):
            issues.append(
                ValidationIssue(
                    path=path,
                    code="unsafe_expression",
                    message="expression contains a forbidden token",
                )
            )
        try:
            parsed_trees[path] = ast.parse(expression, mode="eval")
        except SyntaxError as error:
            issues.append(
                ValidationIssue(
                    path=path,
                    code="expression_syntax",
                    message=_syntax_error_message(expression, error),
                )
            )

    # Resolve names with the same declaration order as champion: a construction
    # may use variables and earlier constructions, never a future declaration.
    construction_scope = set(names)
    for index, item in enumerate(parsed.construction):
        path = f"construction[{index}].expr"
        if tree := parsed_trees.get(path):
            issues.extend(
                _semantic_expression_issues(
                    path=path, tree=tree, available_names=construction_scope
                )
            )
        construction_scope.add(item.name)

    complete_scope = set(names) | set(construction_names)
    for path, _expression in _expressions(parsed):
        if path.startswith("construction["):
            continue
        if tree := parsed_trees.get(path):
            issues.extend(
                _semantic_expression_issues(
                    path=path, tree=tree, available_names=complete_scope
                )
            )
    for index, guard in enumerate(parsed.guards):
        try:
            node = ast.parse(guard, mode="eval").body
        except SyntaxError:
            continue
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "AssumeEq"
            and len(node.args) == 2
            and not node.keywords
        ):
            warnings.append(
                ValidationIssue(
                    path=f"guards[{index}]",
                    code="equation_as_guard",
                    message=(
                        "AssumeEqは厳密な採用条件であり、数値最適化の方程式には"
                        "追加されません。通常の等式はconstraintsへ移し、AssumeEqは"
                        "意図的な厳密分岐・採用判定にだけ使用してください。"
                    ),
                )
            )
    # Validation must not become a source transformation. In particular,
    # Pydantic's ``float | str`` parsing turns JSON integers into floats; that
    # changed the source SHA seen by champion's exact replay authority. Preserve
    # every caller-provided JSON scalar and use the model only for validation.
    native = parsed.native_document() if isinstance(problem, V15Problem) else deepcopy(problem)
    # This catches non-finite values while retaining the original wire shape.
    try:
        json.dumps(native, allow_nan=False)
    except ValueError as error:
        issues.append(ValidationIssue(path="$", code="non_finite", message=str(error)))
    return ValidationReport(
        valid=not issues,
        issues=issues,
        warnings=warnings,
        normalized_problem=native if not issues else None,
    )
