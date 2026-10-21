"""Precision contracts and numerical regressions."""

import importlib
import json
import time
from collections import UserDict, UserList
from collections.abc import Mapping, Sequence

import numpy as np
import pytest
from mpmath import mp
from sympy import Float

from geosolver.engine.standard.contracts.pipeline_result import ExactIdentificationResult
from geosolver.engine.standard.exact_assembly.identify_answer import identify_answer
from geosolver.engine.standard.precision.type_guards.boundary_float_to_mpf import (
    BoundaryOrigin,
    boundary_float_to_mpf,
)
from geosolver.engine.standard.precision.type_guards.ensure_no_float import ensure_no_float
from geosolver.engine.standard.precision.type_guards.high_precision_contamination_error import (
    HighPrecisionContaminationError,
)
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.engine.standard.precision.type_guards.hp_contract import hp_contract
from geosolver.runtime.deadline import runtime_session
from geosolver.runtime.integrity import _sha256_json
from geosolver.runtime.symbolic_operations import decode_identification, encode_identification


def test_symbolic_identification_json_keeps_all_binary_digits():
    with mp.workdps(500):
        original = mp.sqrt(2) + mp.mpf("1e-450")
        result = ExactIdentificationResult(
            exact_status="unresolved",
            identification_method="fixture",
            input_precision_dps=500,
            minimal_polynomial=None,
            polynomial_degree=None,
            selected_exact_value=None,
            verification_residual=mp.mpf("1e-460"),
            numeric_fallback_value=original,
        )
        encoded = encode_identification(result)
        assert all(type(part) is int for part in encoded["numeric_fallback_value"])
        restored = decode_identification(json.loads(json.dumps(encoded)))
        assert restored.numeric_fallback_value._mpf_ == original._mpf_
        assert restored.verification_residual._mpf_ == result.verification_residual._mpf_
        assert _sha256_json(original) == _sha256_json(
            {"mpf_binary": tuple(map(int, original._mpf_))}
        )


@pytest.mark.parametrize("source,kind", [("sqrt(2)", "algebraic"), ("pi/7", "affine_pi")])
def test_high_precision_symbolic_process_round_trip(source, kind):
    with mp.workdps(250), runtime_session(time.monotonic() + 20):
        value = mp.sqrt(2) if kind == "algebraic" else mp.pi / 7
        result = identify_answer(
            answer_hp=value,
            tier="strict",
            input_precision_dps=250,
            answer_uncertainty=mp.mpf("1e-220"),
            closed_source=source,
        )
        assert result.descriptor is not None
        assert result.descriptor.kind == kind
        assert result.verification_residual is not None
        assert abs(result.verification_residual) < mp.mpf("1e-220")


def test_precision_boundary_still_rejects_float_contamination_and_restores_context():
    value = boundary_float_to_mpf(0.1, origin=BoundaryOrigin.INITIAL_POINT)
    assert value == mp.mpf(0.1)
    with high_precision_mode():
        with pytest.raises(HighPrecisionContaminationError):
            mp.mpf(0.1)
        with pytest.raises(HighPrecisionContaminationError):
            boundary_float_to_mpf(0.1, origin=BoundaryOrigin.INITIAL_POINT)
        with high_precision_mode(), pytest.raises(HighPrecisionContaminationError):
            mp.mpf(1) + 0.1
        with pytest.raises(HighPrecisionContaminationError):
            mp.mpf(0.1)
    assert mp.mpf(0.1) == value


@pytest.mark.parametrize(
    "bad",
    [
        0.1,
        np.float16("0.1"),
        np.float32("0.1"),
        np.float64("0.1"),
        np.longdouble("0.1"),
        Float("0.1"),
    ],
)
@pytest.mark.parametrize("wrap", [dict, UserDict])
def test_contamination_after_nested_alias_mutation(bad, wrap):
    nested = [mp.mpf("0.1")]
    value = wrap({"position": (nested,)})
    ensure_no_float(value, context="candidate")
    nested[0] = bad
    with pytest.raises(HighPrecisionContaminationError) as error:
        ensure_no_float(value, context="candidate")
    assert str(error.value) == (
        f"float contamination detected at candidate.position[0][0]: {type(bad).__name__}"
    )


@pytest.mark.parametrize("container", [dict, UserDict])
def test_mapping_replacement_is_rechecked(container):
    value = container(x=mp.mpf(1))
    ensure_no_float(value, context="ctx")
    value.update(x=2.0)
    with pytest.raises(HighPrecisionContaminationError, match=r"ctx.x: float"):
        ensure_no_float(value, context="ctx")


def test_no_error_path_is_formatted_on_success():
    class Key:
        calls = 0

        def __str__(self):
            self.calls += 1
            return "key"

    key = Key()
    value = {key: [mp.mpf(1)]}
    ensure_no_float(value, context="ctx")
    assert key.calls == 0
    value[key][0] = 1.0
    with pytest.raises(HighPrecisionContaminationError, match=r"ctx.key\[0\]"):
        ensure_no_float(value, context="ctx")
    assert key.calls == 1


def test_builtin_scalar_fast_path_skips_generic_type_tests(monkeypatch):
    module = importlib.import_module(ensure_no_float.__module__)

    def forbidden(*args):
        raise AssertionError("generic isinstance on a known exact scalar type")

    value = {"x": [mp.mpf(1), 1, True, "text", b"text", bytearray(), None, lambda: None]}
    monkeypatch.setattr(module, "isinstance", forbidden, raising=False)
    ensure_no_float(value, context="ctx")


def test_subclasses_and_custom_sequences_are_not_trusted_as_scalars():
    class IntegerSequence(int, Sequence):
        def __len__(self):
            return 1

        def __getitem__(self, index):
            if index:
                raise IndexError
            return 0.5

    class FloatSubclass(float):
        pass

    class TupleSubclass(tuple):
        pass

    for value in (IntegerSequence(1), FloatSubclass(1), TupleSubclass((0.5,)), UserList([0.5])):
        with pytest.raises(HighPrecisionContaminationError):
            ensure_no_float(value, context="custom")


def test_virtual_mapping_registration_is_not_hidden_by_type_cache():
    class LaterMapping:
        def items(self):
            return [("bad", 1.0)]

    value = LaterMapping()
    ensure_no_float(value, context="ctx")
    Mapping.register(LaterMapping)
    with pytest.raises(HighPrecisionContaminationError, match="ctx.bad"):
        ensure_no_float(value, context="ctx")


def test_custom_metaclass_cannot_impersonate_atomic_type():
    class Meta(type):
        def __hash__(cls):
            return hash(int)

        def __eq__(cls, other):
            return True

    class FloatSubclass(float, metaclass=Meta):
        pass

    with pytest.raises(HighPrecisionContaminationError):
        ensure_no_float(FloatSubclass(1), context="scalar")


def test_contract_rechecks_both_entry_and_exit_at_every_precision():
    result = {"answer": [mp.mpf(1)]}

    @hp_contract(input_names=("values",))
    def evaluate(values):
        return result

    with pytest.raises(HighPrecisionContaminationError, match="high_precision_mode"):
        evaluate([mp.mpf(1)])
    for precision in (80, 120, 180):
        with mp.workdps(precision), high_precision_mode():
            result["answer"][0] = mp.mpf(1)
            assert evaluate([mp.mpf(1)]) is result
            with pytest.raises(HighPrecisionContaminationError, match=r"input:values\[0\]"):
                evaluate([1.0])
            result["answer"][0] = 1.0
            with pytest.raises(HighPrecisionContaminationError, match=r"output.answer\[0\]"):
                evaluate([mp.mpf(1)])


def test_first_contaminated_path_and_mapping_key_contract_are_preserved():
    ensure_no_float({0.5: mp.mpf(1)}, context="keys-are-not-values")
    with pytest.raises(HighPrecisionContaminationError, match=r"ctx.first\[1\]: float"):
        ensure_no_float({"first": [mp.mpf(0), 1.0], "second": Float(2)}, context="ctx")
