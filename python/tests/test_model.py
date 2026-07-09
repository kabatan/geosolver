from __future__ import annotations

from dataclasses import FrozenInstanceError
from itertools import permutations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from geotarget import (
    ModelError,
    PluginLock,
    ProblemBuilder,
    ProblemSpecV1,
    canonical_hash,
    validate_document,
)

HASH = "sha256:" + "1" * 64
PLUGIN_ID = "11111111-1111-4111-8111-111111111111/example.geometry"


def plugin(plugin_id: str = PLUGIN_ID) -> PluginLock:
    return PluginLock(plugin_id, "1.2.3", "1.0.0", HASH)


def build_problem(keyword_order: tuple[str, ...] = ("left", "right")) -> ProblemSpecV1:
    builder = ProblemBuilder(plugins=(plugin(),))
    x = builder.variable("x", type_id=f"{PLUGIN_ID}::Real", lower=-10.0, upper=10.0, scale=2.0)
    left = builder.literal(1.0, type_id=f"{PLUGIN_ID}::Real", node_id="one")
    right = builder.literal(2.0, type_id=f"{PLUGIN_ID}::Real", node_id="two")
    values = {"left": left, "right": right}
    result = builder.call(
        f"{PLUGIN_ID}::combine",
        x,
        node_id="combined",
        kwargs={key: values[key] for key in keyword_order},
    )
    target = builder.call(f"{PLUGIN_ID}::target_value", result, node_id="target_value")
    builder.relation(result, scale_override=2.0)
    builder.guard(left, strict=True)
    builder.domain(right, strict=False)
    builder.target(target)
    return builder.build()


def test_authoring_model_is_frozen_and_uses_exactly_four_node_kinds() -> None:
    spec = build_problem()
    kinds = {node.kind for node in spec.graph}
    assert kinds == {"reference", "literal", "call"}
    assert not hasattr(spec, "__dict__")
    with pytest.raises(FrozenInstanceError):
        spec.target = spec.target  # type: ignore[misc]

    builder = ProblemBuilder(plugins=(plugin(),))
    x = builder.variable("x", type_id=f"{PLUGIN_ID}::Real")
    choice = builder.call(f"{PLUGIN_ID}::choices", x, node_id="choices")
    selected = builder.select(
        choice,
        f"{PLUGIN_ID}::near",
        x,
        node_id="selected",
    )
    builder.target(selected)
    branch_spec = builder.build()
    assert {node.kind for node in branch_spec.graph} == {"reference", "call", "select"}


def test_kwargs_are_canonicalized_before_hashing() -> None:
    first = build_problem(("left", "right"))
    second = build_problem(("right", "left"))
    assert first.canonical_json() == second.canonical_json()
    assert first.content_hash() == second.content_hash()
    assert first.content_hash() == canonical_hash(first.to_dict())
    assert validate_document(first.to_dict()) == "geotarget.problem/v1"


@given(st.sampled_from(tuple(permutations(("left", "right")))))
def test_hash_is_stable_for_all_keyword_insertions(order: tuple[str, str]) -> None:
    assert build_problem(order).content_hash() == build_problem().content_hash()


def test_open_world_plugin_ids_are_accepted_when_locked() -> None:
    custom_id = "22222222-2222-4222-8222-222222222222/custom-geometry.v7"
    custom = plugin(custom_id)
    builder = ProblemBuilder(plugins=(custom,))
    x = builder.variable("x", type_id=f"{custom_id}::Real")
    result = builder.call(f"{custom_id}::opaque_iteration", x)
    builder.target(result)
    assert validate_document(builder.build().to_dict()) == "geotarget.problem/v1"


def test_unknown_plugin_and_cross_builder_references_are_rejected() -> None:
    builder = ProblemBuilder(plugins=(plugin(),))
    x = builder.variable("x", type_id=f"{PLUGIN_ID}::Real")
    with pytest.raises(ModelError, match="unlocked plugin"):
        builder.call("33333333-3333-4333-8333-333333333333/another::operation", x)

    other = ProblemBuilder(plugins=(plugin(),))
    alien = other.variable("alien", type_id=f"{PLUGIN_ID}::Real")
    with pytest.raises(ModelError, match="does not belong"):
        builder.call(f"{PLUGIN_ID}::operation", alien)


def test_duplicate_ids_and_missing_target_are_rejected() -> None:
    builder = ProblemBuilder(plugins=(plugin(),))
    builder.variable("x", type_id=f"{PLUGIN_ID}::Real")
    with pytest.raises(ModelError, match="duplicate node"):
        builder.literal(1, type_id=f"{PLUGIN_ID}::Real", node_id="x")
    with pytest.raises(ModelError, match=r"target\(\)"):
        builder.build()
