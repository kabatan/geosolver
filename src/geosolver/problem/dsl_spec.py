"""Typed access to the versioned Geometry DSL specification."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DslSymbolSpec(_StrictModel):
    name: str
    aliases: tuple[str, ...] = ()
    symbol_kind: Literal["function", "macro"]
    signature: str
    min_args: int = Field(ge=0)
    max_positional: int | None = Field(default=None, ge=0)
    parameters: tuple[str, ...] = ()
    allowed_keywords: frozenset[str] = frozenset()
    variadic: bool = False
    input_types: dict[str, str] = Field(default_factory=dict)
    output_type: Literal["object", "scalar", "boolean"]
    positions: frozenset[Literal["construction", "constraint", "guard", "target"]]
    semantic_kind: Literal["object", "measurement", "residual", "boolean"]
    domain: tuple[str, ...] = ()
    error_codes: tuple[str, ...] = ()
    standard_implementation: str | None = None
    high_precision_implementation: str | None = None
    branches: tuple[str, ...] = ()
    authoring_status: str
    category: str
    label_ja: str
    notes_ja: str = ""
    expands_to: str | None = None

    @model_validator(mode="after")
    def validate_symbol(self) -> DslSymbolSpec:
        if self.max_positional is not None and self.max_positional < self.min_args:
            raise ValueError("max_positional must not be smaller than min_args")
        if not self.allowed_keywords.issubset(self.parameters):
            raise ValueError("allowed_keywords must be declared parameters")
        if self.symbol_kind == "macro":
            if not self.expands_to:
                raise ValueError("macro must define expands_to")
            if (
                self.standard_implementation is not None
                or self.high_precision_implementation is not None
            ):
                raise ValueError("macro must not name runtime implementations")
        elif not self.standard_implementation or not self.high_precision_implementation:
            raise ValueError("function must name standard and high-precision implementations")
        return self

    def public_contract(self) -> dict[str, Any]:
        return {
            "min_args": self.min_args,
            "max_positional": self.max_positional,
            "parameters": list(self.parameters),
            "allowed_keywords": sorted(self.allowed_keywords),
            "variadic": self.variadic,
            "result_kind": "scalar" if self.output_type in {"scalar", "boolean"} else "object",
        }


class DslSpecDocument(_StrictModel):
    schema_version: Literal[1]
    dsl_version: str
    semantics: Literal["nondegenerate_euclidean_2d"]
    selector_values: dict[str, tuple[Any, ...]] = Field(default_factory=dict)
    categories: list[dict[str, str]] = Field(default_factory=list)
    symbols: tuple[DslSymbolSpec, ...]
    internal_symbols: tuple[str, ...] = ()

    @model_validator(mode="after")
    def unique_names(self) -> DslSpecDocument:
        names: set[str] = set()
        for symbol in self.symbols:
            for name in (symbol.name, *symbol.aliases):
                if name in names:
                    raise ValueError(f"duplicate DSL symbol or alias: {name}")
                names.add(name)
        return self


@lru_cache(maxsize=1)
def dsl_spec() -> DslSpecDocument:
    payload = json.loads(
        files("geosolver.problem").joinpath("dsl-spec.json").read_text(encoding="utf-8")
    )
    return DslSpecDocument.model_validate(payload)


@lru_cache(maxsize=1)
def symbols_by_name() -> dict[str, DslSymbolSpec]:
    result: dict[str, DslSymbolSpec] = {}
    for symbol in dsl_spec().symbols:
        result[symbol.name] = symbol
        result.update({alias: symbol for alias in symbol.aliases})
    return result


def public_symbol_names() -> frozenset[str]:
    return frozenset(symbols_by_name())
