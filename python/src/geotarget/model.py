"""Immutable authoring model for the GeoTarget v1 problem protocol."""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import ClassVar, Literal

from geotarget.canonical import canonical_hash, canonical_json
from geotarget.identifiers import qualified_symbol, semver, sha256_id, stable_id

PROBLEM_SCHEMA_VERSION = "geotarget.problem/v1"


class ModelError(ValueError):
    """Raised when an immutable protocol model violates an ABI invariant."""


def _finite(value: float | None, *, field_name: str) -> None:
    if value is not None and not math.isfinite(value):
        raise ModelError(f"{field_name} must be finite or null")


def _positive(value: float, *, field_name: str) -> None:
    if not math.isfinite(value) or value <= 0:
        raise ModelError(f"{field_name} must be finite and positive")


@dataclass(frozen=True, slots=True)
class PluginLock:
    plugin_id: str
    version: str
    core_abi: str
    content_hash: str

    def __post_init__(self) -> None:
        from geotarget.identifiers import plugin_id

        plugin_id(self.plugin_id)
        semver(self.version)
        semver(self.core_abi, field="core_abi")
        sha256_id(self.content_hash)

    def to_dict(self) -> dict[str, object]:
        return {
            "plugin_id": self.plugin_id,
            "version": self.version,
            "core_abi": self.core_abi,
            "content_hash": self.content_hash,
        }


@dataclass(frozen=True, slots=True)
class VariableSpec:
    id: str
    type_id: str
    origin: float = 0.0
    scale: float = 1.0
    lower: float | None = None
    upper: float | None = None

    def __post_init__(self) -> None:
        stable_id(self.id, field="variable id")
        qualified_symbol(self.type_id)
        _finite(self.origin, field_name="variable origin")
        _positive(self.scale, field_name="variable scale")
        _finite(self.lower, field_name="lower bound")
        _finite(self.upper, field_name="upper bound")
        if self.lower is not None and self.upper is not None and self.lower >= self.upper:
            raise ModelError("lower bound must be strictly below upper bound")
        if self.lower is not None and self.origin < self.lower:
            raise ModelError("variable origin is below its lower bound")
        if self.upper is not None and self.origin > self.upper:
            raise ModelError("variable origin is above its upper bound")

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "id": self.id,
            "type_id": self.type_id,
            "origin": self.origin,
            "scale": self.scale,
        }
        if self.lower is not None:
            result["lower"] = self.lower
        if self.upper is not None:
            result["upper"] = self.upper
        return result


@dataclass(frozen=True, slots=True)
class NodeRef:
    node: str

    def __post_init__(self) -> None:
        stable_id(self.node, field="node reference")


@dataclass(frozen=True, slots=True)
class LiteralNode:
    id: str
    type_id: str
    _value_json: str = field(repr=False)
    kind: ClassVar[Literal["literal"]] = "literal"

    def __post_init__(self) -> None:
        stable_id(self.id)
        qualified_symbol(self.type_id)
        try:
            json.loads(self._value_json)
        except json.JSONDecodeError as exc:
            raise ModelError("literal does not contain valid canonical JSON") from exc

    @classmethod
    def from_value(cls, node_id: str, type_id: str, value: object) -> LiteralNode:
        return cls(node_id, type_id, canonical_json(value))

    @property
    def value(self) -> object:
        return json.loads(self._value_json)

    def to_dict(self) -> dict[str, object]:
        return {"kind": self.kind, "id": self.id, "type_id": self.type_id, "value": self.value}


@dataclass(frozen=True, slots=True)
class ReferenceNode:
    id: str
    variable: str
    kind: ClassVar[Literal["reference"]] = "reference"

    def __post_init__(self) -> None:
        stable_id(self.id)
        stable_id(self.variable, field="variable reference")

    def to_dict(self) -> dict[str, object]:
        return {"kind": self.kind, "id": self.id, "variable": self.variable}


def _normalize_kwargs(kwargs: Mapping[str, NodeRef] | None) -> tuple[tuple[str, NodeRef], ...]:
    if kwargs is None:
        return ()
    normalized: list[tuple[str, NodeRef]] = []
    for key, value in kwargs.items():
        stable_id(key, field="keyword name")
        if not isinstance(value, NodeRef):
            raise ModelError(f"keyword {key!r} must reference a graph node")
        normalized.append((key, value))
    return tuple(sorted(normalized, key=lambda item: item[0]))


@dataclass(frozen=True, slots=True)
class CallNode:
    id: str
    operation: str
    args: tuple[NodeRef, ...] = ()
    kwargs: tuple[tuple[str, NodeRef], ...] = ()
    kind: ClassVar[Literal["call"]] = "call"

    def __post_init__(self) -> None:
        stable_id(self.id)
        qualified_symbol(self.operation)
        normalized = _normalize_kwargs(dict(self.kwargs))
        if len(normalized) != len(self.kwargs):
            raise ModelError("duplicate call keyword")
        object.__setattr__(self, "kwargs", normalized)

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "id": self.id,
            "operation": self.operation,
            "args": [item.node for item in self.args],
            "kwargs": {key: value.node for key, value in self.kwargs},
        }


@dataclass(frozen=True, slots=True)
class SelectNode:
    id: str
    choice: NodeRef
    selector: str
    args: tuple[NodeRef, ...] = ()
    kwargs: tuple[tuple[str, NodeRef], ...] = ()
    kind: ClassVar[Literal["select"]] = "select"

    def __post_init__(self) -> None:
        stable_id(self.id)
        qualified_symbol(self.selector)
        normalized = _normalize_kwargs(dict(self.kwargs))
        if len(normalized) != len(self.kwargs):
            raise ModelError("duplicate selector keyword")
        object.__setattr__(self, "kwargs", normalized)

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "id": self.id,
            "choice": self.choice.node,
            "selector": self.selector,
            "args": [item.node for item in self.args],
            "kwargs": {key: value.node for key, value in self.kwargs},
        }


type GraphNode = LiteralNode | ReferenceNode | CallNode | SelectNode


@dataclass(frozen=True, slots=True)
class RelationBinding:
    node: NodeRef
    scale_override: float | None = None

    def __post_init__(self) -> None:
        if self.scale_override is not None:
            _positive(self.scale_override, field_name="relation scale_override")

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {"node": self.node.node}
        if self.scale_override is not None:
            result["scale_override"] = self.scale_override
        return result


@dataclass(frozen=True, slots=True)
class GuardBinding:
    node: NodeRef
    strict: bool = True
    scale_override: float | None = None

    def __post_init__(self) -> None:
        if self.scale_override is not None:
            _positive(self.scale_override, field_name="guard scale_override")

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {"node": self.node.node, "strict": self.strict}
        if self.scale_override is not None:
            result["scale_override"] = self.scale_override
        return result


@dataclass(frozen=True, slots=True)
class DomainBinding:
    node: NodeRef
    strict: bool = True

    def to_dict(self) -> dict[str, object]:
        return {"node": self.node.node, "strict": self.strict}


def _node_dependencies(node: GraphNode) -> tuple[NodeRef, ...]:
    if isinstance(node, CallNode):
        return (*node.args, *(value for _, value in node.kwargs))
    if isinstance(node, SelectNode):
        return (node.choice, *node.args, *(value for _, value in node.kwargs))
    return ()


@dataclass(frozen=True, slots=True)
class ProblemSpecV1:
    plugin_locks: tuple[PluginLock, ...]
    variables: tuple[VariableSpec, ...]
    graph: tuple[GraphNode, ...]
    relations: tuple[RelationBinding, ...]
    guards: tuple[GuardBinding, ...]
    domains: tuple[DomainBinding, ...]
    target: NodeRef
    schema_version: ClassVar[str] = PROBLEM_SCHEMA_VERSION

    def __post_init__(self) -> None:
        plugin_ids = [item.plugin_id for item in self.plugin_locks]
        if len(plugin_ids) != len(set(plugin_ids)):
            raise ModelError("duplicate plugin lock")
        variable_ids = [item.id for item in self.variables]
        if len(variable_ids) != len(set(variable_ids)):
            raise ModelError("duplicate variable id")
        node_ids = [item.id for item in self.graph]
        if len(node_ids) != len(set(node_ids)):
            raise ModelError("duplicate node id")

        known_plugins = set(plugin_ids)
        known_variables = set(variable_ids)
        seen_nodes: set[str] = set()
        for node in self.graph:
            if isinstance(node, LiteralNode):
                self._check_plugin_owner(node.type_id, known_plugins)
            elif isinstance(node, ReferenceNode):
                if node.variable not in known_variables:
                    raise ModelError(f"reference uses unknown variable: {node.variable!r}")
            elif isinstance(node, CallNode):
                self._check_plugin_owner(node.operation, known_plugins)
            elif isinstance(node, SelectNode):
                self._check_plugin_owner(node.selector, known_plugins)
            for ref in _node_dependencies(node):
                if ref.node not in seen_nodes:
                    raise ModelError(
                        f"node {node.id!r} has a non-topological reference to {ref.node!r}"
                    )
            seen_nodes.add(node.id)

        roles = [binding.node.node for binding in self.relations]
        roles.extend(binding.node.node for binding in self.guards)
        roles.extend(binding.node.node for binding in self.domains)
        roles.append(self.target.node)
        for node_id in roles:
            if node_id not in seen_nodes:
                raise ModelError(f"semantic role references unknown node: {node_id!r}")
        if len(roles) != len(set(roles)):
            raise ModelError("relation, guard, domain and target roles must be disjoint")

    @staticmethod
    def _check_plugin_owner(qualified: str, known_plugins: set[str]) -> None:
        owner, _ = qualified_symbol(qualified)
        if owner not in known_plugins:
            raise ModelError(f"symbol belongs to an unknown plugin: {qualified!r}")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "plugin_locks": [item.to_dict() for item in self.plugin_locks],
            "variables": [item.to_dict() for item in self.variables],
            "graph": [item.to_dict() for item in self.graph],
            "relations": [item.to_dict() for item in self.relations],
            "guards": [item.to_dict() for item in self.guards],
            "domains": [item.to_dict() for item in self.domains],
            "target": self.target.node,
        }

    def canonical_json(self) -> str:
        return canonical_json(self.to_dict())

    def content_hash(self) -> str:
        return canonical_hash(self.to_dict())


class ProblemBuilder:
    """Generic graph builder with no geometry-specific numerical semantics."""

    def __init__(self, *, plugins: Iterable[PluginLock] = ()) -> None:
        self._plugins: dict[str, PluginLock] = {}
        self._variables: dict[str, VariableSpec] = {}
        self._graph: dict[str, GraphNode] = {}
        self._relations: list[RelationBinding] = []
        self._guards: list[GuardBinding] = []
        self._domains: list[DomainBinding] = []
        self._target: NodeRef | None = None
        self._counters: dict[str, int] = {}
        for plugin in plugins:
            self.lock_plugin(plugin)

    def _next_id(self, prefix: str) -> str:
        index = self._counters.get(prefix, 0) + 1
        self._counters[prefix] = index
        return f"{prefix}_{index:04d}"

    def _add_node(self, node: GraphNode) -> NodeRef:
        if node.id in self._graph:
            raise ModelError(f"duplicate node id: {node.id!r}")
        self._graph[node.id] = node
        return NodeRef(node.id)

    def _ref(self, value: NodeRef) -> NodeRef:
        if not isinstance(value, NodeRef):
            raise ModelError("graph arguments must be NodeRef values; add literals explicitly")
        if value.node not in self._graph:
            raise ModelError(f"reference does not belong to this builder: {value.node!r}")
        return value

    def _qualified(self, value: str) -> str:
        owner, _ = qualified_symbol(value)
        if owner not in self._plugins:
            raise ModelError(f"symbol belongs to an unlocked plugin: {value!r}")
        return value

    def lock_plugin(self, plugin: PluginLock) -> ProblemBuilder:
        previous = self._plugins.get(plugin.plugin_id)
        if previous is not None and previous != plugin:
            raise ModelError(f"conflicting lock for plugin {plugin.plugin_id!r}")
        self._plugins[plugin.plugin_id] = plugin
        return self

    def variable(
        self,
        variable_id: str,
        *,
        type_id: str,
        node_id: str | None = None,
        origin: float = 0.0,
        scale: float = 1.0,
        lower: float | None = None,
        upper: float | None = None,
    ) -> NodeRef:
        self._qualified(type_id)
        variable = VariableSpec(variable_id, type_id, origin, scale, lower, upper)
        if variable.id in self._variables:
            raise ModelError(f"duplicate variable id: {variable.id!r}")
        self._variables[variable.id] = variable
        return self._add_node(ReferenceNode(node_id or variable.id, variable.id))

    def literal(self, value: object, *, type_id: str, node_id: str | None = None) -> NodeRef:
        self._qualified(type_id)
        literal_id = node_id or self._next_id("literal")
        return self._add_node(LiteralNode.from_value(literal_id, type_id, value))

    def call(
        self,
        operation: str,
        *args: NodeRef,
        node_id: str | None = None,
        kwargs: Mapping[str, NodeRef] | None = None,
    ) -> NodeRef:
        checked_args = tuple(self._ref(value) for value in args)
        checked_kwargs = {
            key: self._ref(value) for key, value in (kwargs.items() if kwargs is not None else ())
        }
        return self._add_node(
            CallNode(
                node_id or self._next_id("call"),
                self._qualified(operation),
                checked_args,
                _normalize_kwargs(checked_kwargs),
            )
        )

    def select(
        self,
        choice: NodeRef,
        selector: str,
        *args: NodeRef,
        node_id: str | None = None,
        kwargs: Mapping[str, NodeRef] | None = None,
    ) -> NodeRef:
        checked_kwargs = {
            key: self._ref(value) for key, value in (kwargs.items() if kwargs is not None else ())
        }
        return self._add_node(
            SelectNode(
                node_id or self._next_id("select"),
                self._ref(choice),
                self._qualified(selector),
                tuple(self._ref(value) for value in args),
                _normalize_kwargs(checked_kwargs),
            )
        )

    def relation(self, node: NodeRef, *, scale_override: float | None = None) -> ProblemBuilder:
        self._relations.append(RelationBinding(self._ref(node), scale_override))
        return self

    def guard(
        self,
        node: NodeRef,
        *,
        strict: bool = True,
        scale_override: float | None = None,
    ) -> ProblemBuilder:
        self._guards.append(GuardBinding(self._ref(node), strict, scale_override))
        return self

    def domain(self, node: NodeRef, *, strict: bool = True) -> ProblemBuilder:
        self._domains.append(DomainBinding(self._ref(node), strict))
        return self

    def target(self, node: NodeRef) -> ProblemBuilder:
        if self._target is not None:
            raise ModelError("a scalar ProblemSpecV1 has exactly one target")
        self._target = self._ref(node)
        return self

    def build(self) -> ProblemSpecV1:
        if self._target is None:
            raise ModelError("target() must be called before build()")
        return ProblemSpecV1(
            plugin_locks=tuple(sorted(self._plugins.values(), key=lambda item: item.plugin_id)),
            variables=tuple(self._variables.values()),
            graph=tuple(self._graph.values()),
            relations=tuple(self._relations),
            guards=tuple(self._guards),
            domains=tuple(self._domains),
            target=self._target,
        )
