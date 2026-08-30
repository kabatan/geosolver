from __future__ import annotations

from geosolver.problem.catalog import runtime_contracts
from geosolver.problem.dsl_spec import dsl_spec, public_symbol_names


def test_dsl_spec_is_the_complete_public_name_source() -> None:
    spec = dsl_spec()
    names = public_symbol_names()

    assert spec.dsl_version == "1.1.0"
    assert names == frozenset(runtime_contracts())
    assert {"AreConcyclic", "Tangent", "Bound", "Midpoint", "midpoint"} <= names
    assert not any(name.startswith("MP_") for name in names)
    assert {"float", "int", "evalf"}.isdisjoint(names)


def test_every_macro_has_an_expansion_and_no_runtime_implementation() -> None:
    for symbol in dsl_spec().symbols:
        if symbol.symbol_kind != "macro":
            continue
        assert symbol.expands_to
        assert symbol.standard_implementation is None
        assert symbol.high_precision_implementation is None
