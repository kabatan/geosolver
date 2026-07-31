"""Lossless JSON transport for exact integer polynomial coefficients.

JSON3 may parse a JSON integer outside its native integer range through a
floating representation.  This adapter changes only schema-declared exact ZZ
coefficient arrays to canonical decimal strings.  Structural integers remain
JSON integers, and any unclassified large integer fails closed.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "geotarget.lossless-exact-integer-json-transport/v1"
EXACT_INTEGER_ARRAY_KEYS = frozenset(
    {
        "coefficients_high_to_low",
        "coefficients_low_to_high",
        "minimal_polynomial_high_to_low",
        "minimal_polynomial_low_to_high",
        "theta_numerators_low_to_high",
    }
)
JSON3_SAFE_NATIVE_INTEGER = (1 << 63) - 1
DECIMAL_PATTERN = re.compile(r"(?:0|-[1-9][0-9]*|[1-9][0-9]*)\Z")
MAX_ERROR_TEXT = 512


class TransportError(ValueError):
    """Lossless transport could not prove that the job is representable."""


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json(document: object) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _decimal(value: object, path: str) -> str:
    if isinstance(value, bool):
        raise TransportError(f"Boolean is not a ZZ coefficient at {path}")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str) and DECIMAL_PATTERN.fullmatch(value):
        return value
    raise TransportError(f"non-canonical decimal ZZ coefficient at {path}")


def encode_job(job: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a JSON3-safe job and an attestation of the lossless rewrite."""

    if not isinstance(job, Mapping):
        raise TransportError("job root is not a mapping")
    encoded_count = 0
    maximum_digits = 0

    def walk(value: object, path: str, field: str | None = None) -> object:
        nonlocal encoded_count, maximum_digits
        if field in EXACT_INTEGER_ARRAY_KEYS:
            if not isinstance(value, list) or not value:
                raise TransportError(f"exact coefficient field is not a nonempty list at {path}")
            result: list[str] = []
            for index, coefficient in enumerate(value):
                text = _decimal(coefficient, f"{path}[{index}]")
                result.append(text)
                encoded_count += 1
                maximum_digits = max(maximum_digits, len(text.lstrip("-")))
            return result
        if isinstance(value, Mapping):
            result_dict: dict[str, object] = {}
            for key, item in value.items():
                if not isinstance(key, str):
                    raise TransportError(f"non-string object key at {path}")
                child_path = f"{path}.{key}"
                result_dict[key] = walk(item, child_path, key)
            return result_dict
        if isinstance(value, list):
            return [walk(item, f"{path}[{index}]") for index, item in enumerate(value)]
        if isinstance(value, bool) or value is None or isinstance(value, str):
            return value
        if isinstance(value, int):
            if abs(value) > JSON3_SAFE_NATIVE_INTEGER:
                raise TransportError(f"unclassified large integer at {path}")
            return value
        if isinstance(value, float):
            detail = "non-finite" if not math.isfinite(value) else "floating"
            raise TransportError(f"{detail} value in exact job at {path}")
        raise TransportError(f"unsupported JSON value {type(value).__name__} at {path}")

    encoded = walk(job, "$")
    assert isinstance(encoded, dict)
    if encoded_count == 0:
        raise TransportError("job contains no schema-declared exact ZZ coefficients")
    original_sha256 = _sha256(_canonical_json(job))
    transport_payload = _canonical_json(encoded)
    decoded = decode_job(encoded)
    if _canonical_json(decoded) != _canonical_json(job):
        raise TransportError("transport round-trip changed the mathematical job")
    attestation = {
        "schema_version": SCHEMA,
        "status": "LOSSLESS_DECIMAL_STRING_TRANSPORT_VERIFIED",
        "exact_integer_count": encoded_count,
        "maximum_decimal_digits": maximum_digits,
        "mathematical_job_sha256": original_sha256,
        "transport_json_sha256": _sha256(transport_payload),
        "round_trip_equal": True,
        "truth_used": False,
        "case_routing_used": False,
    }
    return encoded, attestation


def decode_job(encoded: Mapping[str, Any]) -> dict[str, Any]:
    """Inverse of :func:`encode_job`, used only for transport validation."""

    def walk(value: object, path: str, field: str | None = None) -> object:
        if field in EXACT_INTEGER_ARRAY_KEYS:
            if not isinstance(value, list) or not value:
                raise TransportError(f"exact coefficient field is not a nonempty list at {path}")
            return [int(_decimal(item, f"{path}[{index}]")) for index, item in enumerate(value)]
        if isinstance(value, Mapping):
            result: dict[str, object] = {}
            for key, item in value.items():
                if not isinstance(key, str):
                    raise TransportError(f"non-string object key at {path}")
                result[key] = walk(item, f"{path}.{key}", key)
            return result
        if isinstance(value, list):
            return [walk(item, f"{path}[{index}]") for index, item in enumerate(value)]
        return value

    result = walk(encoded, "$")
    if not isinstance(result, dict):
        raise TransportError("decoded job root is not an object")
    return result


LAST_ATTESTATION: dict[str, Any] | None = None


def run_julia_lossless(
    job: Mapping[str, Any],
    *,
    julia_project: Path,
    julia_worker: Path,
    timeout_seconds: float,
) -> dict[str, Any]:
    """Run the frozen worker after a proven lossless decimal-string rewrite."""

    global LAST_ATTESTATION
    encoded, attestation = encode_job(job)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".json", prefix="qqbar-lossless-job-", delete=False
    ) as stream:
        json.dump(encoded, stream, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        stream.flush()
        job_path = Path(stream.name)
    environment = os.environ.copy()
    environment.update(
        {
            "JULIA_NUM_THREADS": "1",
            "JULIA_NUM_GC_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
    )
    try:
        completed = subprocess.run(
            [
                "julia",
                "--compile=no",
                f"--project={julia_project}",
                "--startup-file=no",
                "--history-file=no",
                str(julia_worker),
                str(job_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=environment,
        )
    except subprocess.TimeoutExpired as error:
        raise TransportError("Nemo exact replay exceeded frozen inner deadline") from error
    finally:
        job_path.unlink(missing_ok=True)
    if completed.returncode != 0:
        detail = completed.stderr[-MAX_ERROR_TEXT:].replace("\n", " ")
        raise TransportError(f"Nemo worker failed with code {completed.returncode}: {detail}")
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if len(lines) != 1:
        raise TransportError("Nemo worker did not emit exactly one JSON record")
    try:
        result = json.loads(lines[0])
    except json.JSONDecodeError as error:
        raise TransportError("Nemo worker output is not JSON") from error
    if not isinstance(result, dict) or result.get("status") != "EXACT_REPLAY_ACCEPTED":
        detail = result.get("error", "Nemo exact replay rejected") if isinstance(result, dict) else "non-object result"
        raise TransportError(str(detail))
    if result.get("truth_used") is not False:
        raise TransportError("Nemo result truth flag is not false")
    if result.get("completeness_claim_permitted") is not False:
        raise TransportError("Nemo result permits a completeness claim")
    LAST_ATTESTATION = {
        **attestation,
        "complete_qqbar_source_replay": result.get("source_raw_answer_exact") is True,
        "replay_status": result.get("status"),
    }
    return result
