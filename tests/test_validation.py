from __future__ import annotations

import ast
import inspect
import sys

import pytest
from pydantic import ValidationError

from geotarget import SolveOptions, validate
from geotarget.dsl_contract import catalog_payload, runtime_contracts
from geotarget.engine import engine_root
from geotarget.validation import _runtime_call_issues


def test_v15_round_trip_preserves_native_shape(problem: dict) -> None:
    report = validate(problem)
    assert report.valid
    assert report.normalized_problem == problem


def test_point_on_circle_periodic_expression_is_preserved(problem: dict) -> None:
    problem["variables"]["names"] = ["t"]
    problem["construction"].append({"name": "c", "expr": "Circle(A, 1)"})
    problem["construction"].append({"name": "C", "expr": "PointOnCircle(c, t)"})
    report = validate(problem)
    assert report.valid
    assert report.normalized_problem["construction"][-1]["expr"] == "PointOnCircle(c, t)"


def test_dangerous_expression_is_rejected(problem: dict) -> None:
    problem["answer"] = "__import__('os').system('id')"
    report = validate(problem)
    assert not report.valid
    assert any(issue.code == "unsafe_expression" for issue in report.issues)


def test_malformed_expression_and_cross_namespace_collision_are_rejected(problem: dict) -> None:
    problem["variables"]["names"] = ["A"]
    problem["construction"][0]["expr"] = "Point(,)"
    report = validate(problem)
    assert not report.valid
    assert {issue.code for issue in report.issues} >= {"expression_syntax", "name_collision"}


def test_string_constraint_value_is_syntax_checked(problem: dict) -> None:
    problem["constraints"].append({"def": "Distance(A, B)", "value": "Point(,)"})
    report = validate(problem)
    assert not report.valid
    assert any(issue.path == "constraints[0].value" for issue in report.issues)


def test_empty_expressions_are_reported_without_a_misleading_parser_column(problem: dict) -> None:
    problem["guards"] = ["   "]

    report = validate(problem)

    assert not report.valid
    issues = [issue for issue in report.issues if issue.path == "guards[0]"]
    assert [(issue.code, issue.message) for issue in issues] == [
        ("empty_expression", "expression must not be empty"),
    ]


@pytest.mark.parametrize("value", [0, 179.999, float("inf"), float("nan")])
def test_time_limit_is_finite_and_at_least_180(value: float) -> None:
    with pytest.raises(ValidationError):
        SolveOptions(time_limit_seconds=value)


def test_validation_preserves_native_json_scalar_types(problem: dict) -> None:
    problem["constraints"].append({"def": "Distance(A, B)", "value": 4})

    report = validate(problem)

    assert report.valid
    assert report.normalized_problem == problem
    assert type(report.normalized_problem["constraints"][0]["value"]) is int


def test_assume_eq_guard_is_preserved_but_diagnosed(problem: dict) -> None:
    problem["guards"] = [
        "AssumeEq(Distance(A, B), sqrt(17))",
        "AssumeLt(Distance(A, B), 10)",
    ]

    report = validate(problem)

    assert report.valid
    assert report.normalized_problem == problem
    assert [(warning.path, warning.code) for warning in report.warnings] == [
        ("guards[0]", "equation_as_guard")
    ]


def test_unknown_function_is_rejected_with_case_sensitive_suggestion(problem: dict) -> None:
    problem["guards"] = ["angle(A, B, A) < pi"]

    report = validate(problem)

    assert not report.valid
    issue = next(issue for issue in report.issues if issue.code == "unknown_function")
    assert issue.path == "guards[0]"
    assert "angle" in issue.message
    assert "Angle" in issue.message


def test_unknown_and_forward_references_are_rejected(problem: dict) -> None:
    problem["construction"].insert(0, {"name": "M", "expr": "Midpoint(A, Missing)"})

    report = validate(problem)

    assert not report.valid
    unknown = [issue for issue in report.issues if issue.code == "unknown_name"]
    assert {issue.path for issue in unknown} == {"construction[0].expr"}
    assert any("「A」" in issue.message for issue in unknown)
    assert any("「Missing」" in issue.message for issue in unknown)


def test_malformed_guard_reports_one_actionable_syntax_issue(problem: dict) -> None:
    problem["guards"] = [
        "AssumeLt(Distance(A, B), Distance(A, C))",
        "Assume(Angle((K,Y,X) + Angle(le(A,I,D) = pi)",
    ]

    report = validate(problem)

    issues = [issue for issue in report.issues if issue.path == "guards[1]"]
    assert len(issues) == 1
    assert issues[0].code == "expression_syntax"
    assert "括弧が対応していません" in issues[0].message
    assert "閉じ括弧「)」が2個不足" in issues[0].message


def test_parentheses_inside_string_do_not_distort_syntax_hint(problem: dict) -> None:
    problem["guards"] = ['AssumeLt(1, vertex="(") +']

    report = validate(problem)

    issue = next(issue for issue in report.issues if issue.path == "guards[0]")
    assert issue.code == "expression_syntax"
    assert "括弧が対応していません" not in issue.message


def test_public_v15_function_and_previously_declared_names_are_accepted(problem: dict) -> None:
    problem["answer"] = "Angle(A, B, A) + sqrt(pi)"

    report = validate(problem)

    assert report.valid


@pytest.mark.parametrize(
    ("expression", "code"),
    [
        ("Distance(A, B, unexpected=1)", "unknown_keyword"),
        ("sqrt()", "too_few_arguments"),
        ("Angle(A, B, A)[0]", "invalid_subscript"),
        ("(lambda value: value)(1)", "unsupported_ast"),
        ("[value for value in (1,)]", "unsupported_ast"),
        ("Excenter(A, B, A, vertex='D')", "invalid_selector"),
    ],
)
def test_runtime_contract_rejects_expressions_that_fail_during_evaluation(
    problem: dict, expression: str, code: str
) -> None:
    problem["answer"] = expression

    report = validate(problem)

    assert not report.valid
    assert code in {issue.code for issue in report.issues}


def test_runtime_contract_accepts_named_arguments_and_supported_selectors(
    problem: dict,
) -> None:
    problem["construction"].append(
        {"name": "E", "expr": "Excenter(A=A, B=B, C=A, vertex='A')"}
    )
    problem["answer"] = "Distance(obj1=A, obj2=B)"

    report = validate(problem)

    assert report.valid


def test_catalog_exposes_contract_or_expansion_for_every_tool() -> None:
    catalog = catalog_payload()
    contracts = runtime_contracts()

    assert len(contracts) == len(catalog["runtime_functions"]) + sum(
        "expands_to" not in tool for tool in catalog["tools"]
    )
    for tool in catalog["tools"]:
        if "expands_to" in tool:
            assert "runtime_contract" not in tool
        else:
            assert tool["runtime_contract"] == contracts[tool["id"]].public_payload()


def test_every_direct_catalog_signature_satisfies_its_runtime_contract() -> None:
    catalog = catalog_payload()
    for entry in [*catalog["tools"], *catalog["runtime_functions"]]:
        if "runtime_contract" not in entry:
            continue
        try:
            node = ast.parse(entry["signature"], mode="eval").body
        except SyntaxError:
            continue
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id != entry["id"]:
            continue
        assert _runtime_call_issues("answer", node) == [], entry["id"]


def test_catalog_contracts_are_compatible_with_frozen_runtime_callables() -> None:
    runtime_source = engine_root() / "runtime/geosolver/src"
    sys.path.insert(0, str(runtime_source))
    from geosolver._internal.autosolve.context.geometry import (  # noqa: PLC0415
        _get_geometry_context,
    )

    context = _get_geometry_context()
    guard_language_forms = {
        "And",
        "Or",
        "Not",
        "AssumeCollinear",
        "AssumeParallel",
        "AssumePerpendicular",
        "AssumeCyclic",
    }
    for name, contract in runtime_contracts().items():
        if name in guard_language_forms:
            continue
        runtime_callable = context.get(name)
        assert callable(runtime_callable), name
        try:
            signature = inspect.signature(runtime_callable)
        except (TypeError, ValueError):
            # A few CPython builtins (notably int) expose no inspectable
            # signature, but callable presence still verifies the runtime seam.
            continue
        parameters = tuple(signature.parameters.values())
        required = sum(
            parameter.default is inspect.Parameter.empty
            and parameter.kind
            in {inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD}
            for parameter in parameters
        )
        runtime_variadic = any(
            parameter.kind is inspect.Parameter.VAR_POSITIONAL for parameter in parameters
        )
        runtime_maximum = sum(
            parameter.kind
            in {inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD}
            for parameter in parameters
        )
        assert required <= contract.min_args, name
        if not runtime_variadic and contract.max_positional is not None:
            assert contract.max_positional <= runtime_maximum, name
