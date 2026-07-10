"""Post-outcome representation repair around the frozen S4 analyzer."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import tempfile
import types
from pathlib import Path
from typing import Any


EXPERIMENT_DIRECTORY = Path(__file__).resolve().parent
ORIGINAL_ANALYZER = EXPERIMENT_DIRECTORY / "s4_development_analysis.py"
ANALYSIS_AMENDMENT = EXPERIMENT_DIRECTORY / "s4-protocol-amendment-a9.json"


def bytes_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def parse_json(payload: bytes) -> Any:
    return json.loads(payload.decode("utf-8"))


def normalize_unit_radius_tokens(
    raw_document: dict[str, Any],
) -> tuple[dict[str, Any], int]:
    """Map JSON integer 1 to float 1.0 only at frozen gradient-radius fields."""

    normalized = copy.deepcopy(raw_document)
    count = 0
    for row in normalized.get("rows", []):
        gradients = (
            row.get("diagnostics", {}).get("error_audit", {}).get("gradients", [])
        )
        for gradient in gradients:
            radius = gradient.get("radius_multiplier")
            if type(radius) is int and radius == 1:
                gradient["radius_multiplier"] = 1.0
                count += 1
    if count == 0:
        raise ValueError("S4 A9 repair found no unit-radius token")
    return normalized, count


def write_json_atomic(path: Path, document: dict[str, Any]) -> None:
    payload = (
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_frozen_analyzer(payload: bytes) -> Any:
    module = types.ModuleType("geotarget_s4_frozen_analysis_a9")
    module.__file__ = str(ORIGINAL_ANALYZER)
    module.__package__ = None
    code = compile(payload, str(ORIGINAL_ANALYZER), "exec")
    exec(code, module.__dict__)
    return module


def unique_path_option(arguments: list[str], option: str) -> Path:
    positions = [index for index, value in enumerate(arguments) if value == option]
    if len(positions) != 1:
        raise ValueError(f"S4 A9 requires exactly one {option}")
    position = positions[0]
    if position + 1 >= len(arguments) or arguments[position + 1].startswith("--"):
        raise ValueError(f"S4 A9 {option} has no value")
    return Path(arguments[position + 1]).resolve()


def verify_bound_result_artifacts(
    result_directory: Path, result_bindings: dict[str, Any]
) -> None:
    bindings = result_bindings["bindings"]
    for filename, key in (
        ("checkpoint-manifest.json", "checkpoint_manifest_sha256"),
        ("environment.json", "environment_sha256"),
        ("raw.json", "raw_sha256"),
        ("report.md", "report_sha256"),
        ("summary.json", "summary_sha256"),
    ):
        observed = bytes_sha256((result_directory / filename).read_bytes())
        if observed != bindings[key]:
            raise ValueError(f"S4 A9 result artifact changed: {filename}")
    for filename, key in (
        ("run-identity.json", "run_identity_sha256"),
        ("warmup.json", "warmup_sha256"),
    ):
        observed = bytes_sha256((result_directory / filename).read_bytes())
        if observed != result_bindings[key]:
            raise ValueError(f"S4 A9 base artifact changed: {filename}")


def main() -> int:
    amendment_payload = ANALYSIS_AMENDMENT.read_bytes()
    amendment_sha256 = bytes_sha256(amendment_payload)
    amendment = parse_json(amendment_payload)
    if amendment["status"] != "frozen-after-radius-token-analysis-failure":
        raise ValueError("S4 A9 status mismatch")
    wrapper_path = Path(__file__).resolve()
    wrapper_payload = wrapper_path.read_bytes()
    wrapper_sha256 = bytes_sha256(wrapper_payload)
    if wrapper_sha256 != amendment["wrapper_source_sha256"]:
        raise ValueError("S4 A9 wrapper source mismatch")
    analyzer_payload = ORIGINAL_ANALYZER.read_bytes()
    analyzer_sha256 = bytes_sha256(analyzer_payload)
    if analyzer_sha256 != amendment["original_analyzer_sha256"]:
        raise ValueError("S4 A9 original analyzer mismatch")
    result_directory = unique_path_option(sys.argv[1:], "--result-directory")
    experiment_directory = unique_path_option(sys.argv[1:], "--experiment-directory")
    if experiment_directory != EXPERIMENT_DIRECTORY:
        raise ValueError("S4 A9 experiment directory mismatch")
    result_bindings_path = result_directory / "result-bindings.json"
    result_bindings_payload = result_bindings_path.read_bytes()
    result_bindings_sha256 = bytes_sha256(result_bindings_payload)
    if result_bindings_sha256 != amendment["result_bindings_sha256"]:
        raise ValueError("S4 A9 result bindings mismatch")
    result_bindings = parse_json(result_bindings_payload)
    verify_bound_result_artifacts(result_directory, result_bindings)
    destination = result_directory / "independent-analysis.json"
    binding_path = result_directory / "independent-analysis-a9-bindings.json"
    if destination.exists() or binding_path.exists():
        raise FileExistsError("S4 A9 refuses an existing independent analysis")

    frozen = load_frozen_analyzer(analyzer_payload)
    original_analyze = frozen.analyze
    normalization_count = 0

    def repaired_analyze(
        raw_document: dict[str, Any],
        summary_document: dict[str, Any],
        manifest: dict[str, Any],
        gold: dict[str, Any],
    ) -> dict[str, Any]:
        nonlocal normalization_count
        normalized, normalization_count = normalize_unit_radius_tokens(raw_document)
        return original_analyze(normalized, summary_document, manifest, gold)

    frozen.analyze = repaired_analyze
    exit_code = int(frozen.main())
    if exit_code != 0:
        return exit_code
    analysis_payload = destination.read_bytes()
    analysis_sha256 = bytes_sha256(analysis_payload)
    analysis = parse_json(analysis_payload)
    if analysis.get("independent_reconstruction_passed") is not True:
        raise ValueError("S4 A9 analyzer returned success without reconstruction pass")
    if bytes_sha256(ANALYSIS_AMENDMENT.read_bytes()) != amendment_sha256:
        raise ValueError("S4 A9 amendment changed before binding")
    if bytes_sha256(wrapper_path.read_bytes()) != wrapper_sha256:
        raise ValueError("S4 A9 wrapper changed before binding")
    if bytes_sha256(ORIGINAL_ANALYZER.read_bytes()) != analyzer_sha256:
        raise ValueError("S4 A9 original analyzer changed before binding")
    if bytes_sha256(destination.read_bytes()) != analysis_sha256:
        raise ValueError("S4 A9 independent analysis changed before binding")
    if bytes_sha256(result_bindings_path.read_bytes()) != result_bindings_sha256:
        raise ValueError("S4 A9 result bindings changed before binding")
    verify_bound_result_artifacts(result_directory, result_bindings)
    write_json_atomic(
        binding_path,
        {
            "analysis_amendment_sha256": amendment_sha256,
            "independent_analysis_sha256": analysis_sha256,
            "normalization_count": normalization_count,
            "original_analyzer_sha256": analyzer_sha256,
            "product_connected": False,
            "result_bindings_sha256": result_bindings_sha256,
            "schema": "geotarget.singular-s4-independent-analysis-a9-bindings/v1",
            "wrapper_source_sha256": wrapper_sha256,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
