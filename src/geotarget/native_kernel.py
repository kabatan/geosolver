"""Fail-closed loader and adapter for the optional Rust flat-tape kernel."""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import math
import os
import re
import sys
from pathlib import Path
from typing import Any

from geotarget.flat_tape_backend import FlatTapeProgram

NATIVE_SEMANTIC_ABI = "geotarget.native-flat-kernel/ieee754-bf53-v1"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SUPPORTED_OPS = frozenset(
    {
        1,  # ExactInt
        2,  # BF53Literal
        3,  # BF53Input
        5,  # Add
        6,  # Sub
        7,  # Mult
        8,  # Div
        10,  # USub
        11,  # UAdd
        12,  # Sqrt
        15,  # Abs
        20,  # Point
        21,  # PointX
        22,  # PointY
        23,  # MidpointPP
        24,  # PointOnSegment
        30,  # Circle
        31,  # CircleCenter
        32,  # CircleRadius
        40,  # LinePP
        41,  # LineABC
        50,  # DistancePP
        51,  # DistancePL
        52,  # DistanceLP
        53,  # DistancePC
        54,  # DistanceCP
        55,  # AreaPoints
    }
)

_EXACT_INT = 1
_BF53_LITERAL = 2
_BF53_INPUT = 3
_SQRT = 12
_IMPLICIT_SQRT_OPS = frozenset(
    {
        40,  # LinePP normalization
        41,  # LineABC normalization
        50,  # DistancePP
        53,  # DistancePC
        54,  # DistanceCP
    }
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def native_capability() -> dict[str, Any]:
    if os.environ.get("GEOTARGET_NATIVE_DISABLE") == "1":
        return {"available": False, "reason": "disabled_by_environment"}
    try:
        experimental_path = os.environ.get("GEOTARGET_NATIVE_MODULE_PATH")
        if experimental_path:
            path = Path(experimental_path).expanduser().resolve()
            module = sys.modules.get("geotarget._native_kernel")
            if module is None or Path(str(getattr(module, "__file__", ""))).resolve() != path:
                specification = importlib.util.spec_from_file_location(
                    "geotarget._native_kernel",
                    path,
                )
                if specification is None or specification.loader is None:
                    raise ImportError(path)
                module = importlib.util.module_from_spec(specification)
                sys.modules[specification.name] = module
                specification.loader.exec_module(module)
        else:
            module = importlib.import_module("geotarget._native_kernel")
    except Exception as error:
        return {"available": False, "reason": f"import_failed:{type(error).__name__}"}
    path = Path(str(getattr(module, "__file__", ""))).resolve()
    sidecar = path.with_name(path.name + ".sha256")
    try:
        expected_hash = sidecar.read_text(encoding="ascii").strip()
        observed_hash = _sha256(path)
        observed_abi = str(module.semantic_abi())
    except Exception as error:
        return {"available": False, "reason": f"attestation_failed:{type(error).__name__}"}
    if not _HEX64.fullmatch(expected_hash) or expected_hash != observed_hash:
        return {"available": False, "reason": "binary_hash_mismatch"}
    if observed_abi != NATIVE_SEMANTIC_ABI:
        return {"available": False, "reason": "semantic_abi_mismatch"}
    return {
        "available": True,
        "semantic_abi": observed_abi,
        "binary_sha256": observed_hash,
        "module": module,
    }


def _serialized_instruction(item: Any) -> tuple[Any, ...]:
    op = int(item.op)
    if op not in _SUPPORTED_OPS:
        raise ValueError(f"unsupported native opcode: {item.op.name}")
    output_kind = int(item.output.kind)
    operands = [(int(reference.kind), reference.index) for reference in item.operands]
    float_payload: float | None = None
    int_payload: int | None = None
    if op == 1:
        int_payload = int(item.payload)
        if abs(int_payload) > 2**53:
            raise ValueError("native exact integer exceeds exact binary64 range")
    elif op == 2:
        float_payload = float(item.payload)
        if not math.isfinite(float_payload):
            raise ValueError("native literal is non-finite")
    elif op == 3:
        int_payload = int(item.payload)
    return (
        op,
        output_kind,
        item.output.index,
        operands,
        float_payload,
        int_payload,
    )


def _certify_numeric_effects(flat: FlatTapeProgram) -> None:
    """Reject source-exact radicals before selecting the binary64 kernel.

    The qualified Python tape intentionally retains an input-free irrational
    radical as a deferred symbolic scalar until the residual boundary.  A
    hardware ``sqrt`` rounds that value earlier and can move the final result
    by one ULP.  Dependency flow through every scalar and geometry slot is a
    source-independent numeric effect, so this conservative gate rejects the
    complete native program whenever such a hidden or explicit radical has no
    BF53 input/literal ancestor.
    """

    has_bf53_ancestor: dict[tuple[int, int], bool] = {}
    tapes = [
        flat.construction_tape,
        *(tape for tape, _left, _right in flat.constraint_tapes),
    ]
    for tape in tapes:
        for item in tape:
            op = int(item.op)
            output = (int(item.output.kind), item.output.index)
            operand_effects = [
                has_bf53_ancestor.get((int(reference.kind), reference.index), False)
                for reference in item.operands
            ]
            if op in {_BF53_LITERAL, _BF53_INPUT}:
                effect = True
            elif op == _EXACT_INT:
                effect = False
            else:
                effect = any(operand_effects)
            if op == _SQRT and not effect:
                raise ValueError("native source-exact sqrt requires symbolic boundary")
            if op in _IMPLICIT_SQRT_OPS and not effect:
                raise ValueError("native source-exact geometry requires symbolic boundary")
            has_bf53_ancestor[output] = effect


class NativeResidualProgram:
    """One-FFI residual evaluator with whole-callback Python fallback."""

    semantic_abi = NATIVE_SEMANTIC_ABI

    def __init__(self, fallback: FlatTapeProgram, implementation: Any, attestation: dict[str, Any]):
        self.fallback = fallback
        self.implementation = implementation
        self.attestation = attestation

    def evaluate(self, values: list[float]) -> list[float]:
        result = self.implementation.evaluate(values)
        return self.fallback.evaluate(values) if result is None else list(result)

    def metadata(self) -> dict[str, Any]:
        return {
            "semantic_abi": self.semantic_abi,
            "binary_sha256": self.attestation["binary_sha256"],
            "ffi_calls_per_residual": 1,
            "fastmath": False,
            "native_libm_approximation": False,
            "runtime_fallback_scope": "whole_callback",
            "fallback_value_classes": [
                "signed_zero",
                "subnormal",
                "non_finite",
                "uncertified_intermediate",
            ],
            "case_specific_routing": False,
            "problem_identity_read": False,
            "corpus_metadata_read": False,
        }


def compile_native_program(flat: FlatTapeProgram) -> NativeResidualProgram | None:
    capability = native_capability()
    if not capability.get("available"):
        return None
    try:
        _certify_numeric_effects(flat)
        construction = [_serialized_instruction(item) for item in flat.construction_tape]
        constraints = [
            (
                [_serialized_instruction(item) for item in tape],
                (int(left.kind), left.index),
                (int(right.kind), right.index),
            )
            for tape, left, right in flat.constraint_tapes
        ]
        module = capability["module"]
        implementation = module.NativeProgram(
            len(flat.variable_names),
            flat.slot_counts,
            construction,
            constraints,
        )
    except Exception:
        return None
    return NativeResidualProgram(flat, implementation, capability)


__all__ = [
    "NATIVE_SEMANTIC_ABI",
    "NativeResidualProgram",
    "compile_native_program",
    "native_capability",
]
