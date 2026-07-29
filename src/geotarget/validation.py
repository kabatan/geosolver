from __future__ import annotations

import ast
import json
import re
from copy import deepcopy
from typing import Any

from pydantic import ValidationError

from geotarget.models import V15Problem, ValidationIssue, ValidationReport

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_DANGEROUS = re.compile(
    r"(__|\b(?:import|exec|eval|open|compile|globals|locals|subprocess|os|sys)\b|[;`{}])",
    re.IGNORECASE,
)


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
        if expression.count("(") != expression.count(")"):
            issues.append(
                ValidationIssue(
                    path=path,
                    code="unbalanced_parentheses",
                    message="expression parentheses are unbalanced",
                )
            )
        try:
            ast.parse(expression, mode="eval")
        except SyntaxError as error:
            issues.append(
                ValidationIssue(
                    path=path,
                    code="expression_syntax",
                    message=f"invalid expression syntax at column {error.offset or 0}",
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
