"""Exact binary transport works with Python and GMP integer mantissas."""

import json
import time

import pytest
from mpmath import mp

from geosolver.engine.standard.contracts.pipeline_result import ExactIdentificationResult
from geosolver.engine.standard.exact_assembly.identify_answer import identify_answer
from geosolver.runtime.deadline import runtime_session
from geosolver.runtime.integrity import _sha256_json
from geosolver.runtime.symbolic_operations import decode_identification, encode_identification


def test_symbolic_identification_json_keeps_all_binary_digits():
    with mp.workdps(500):
        original = mp.sqrt(2) + mp.mpf('1e-450')
        result = ExactIdentificationResult(
            exact_status='unresolved',
            identification_method='fixture',
            input_precision_dps=500,
            minimal_polynomial=None,
            polynomial_degree=None,
            selected_exact_value=None,
            verification_residual=mp.mpf('1e-460'),
            numeric_fallback_value=original,
        )
        encoded = encode_identification(result)
        assert all(type(part) is int for part in encoded['numeric_fallback_value'])
        restored = decode_identification(json.loads(json.dumps(encoded)))
        assert restored.numeric_fallback_value._mpf_ == original._mpf_
        assert restored.verification_residual._mpf_ == result.verification_residual._mpf_
        assert _sha256_json(original) == _sha256_json(
            {'mpf_binary': tuple(map(int, original._mpf_))}
        )


@pytest.mark.parametrize('source,kind', [('sqrt(2)', 'algebraic'), ('pi/7', 'affine_pi')])
def test_high_precision_symbolic_process_round_trip(source, kind):
    with mp.workdps(250), runtime_session(time.monotonic() + 20):
        value = mp.sqrt(2) if kind == 'algebraic' else mp.pi / 7
        result = identify_answer(
            answer_hp=value,
            tier='strict',
            input_precision_dps=250,
            answer_uncertainty=mp.mpf('1e-220'),
            closed_source=source,
        )
        assert result.descriptor is not None
        assert result.descriptor.kind == kind
        assert result.verification_residual is not None
        assert abs(result.verification_residual) < mp.mpf("1e-220")
