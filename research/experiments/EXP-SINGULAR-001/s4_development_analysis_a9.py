"""Post-outcome representation repair around the frozen S4 analyzer."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any


EXPERIMENT_DIRECTORY = Path(__file__).resolve().parent
ORIGINAL_ANALYZER = EXPERIMENT_DIRECTORY / "s4_development_analysis.py"
ANALYSIS_AMENDMENT = EXPERIMENT_DIRECTORY / "s4-protocol-amendment-a9.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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
            if isinstance(radius, bool) or not isinstance(radius, (int, float)):
                raise TypeError("S4 gradient radius must be a JSON number")
            exact = Decimal(str(radius))
            if exact == Decimal("1"):
                gradient["radius_multiplier"] = 1.0
                count += 1
            elif exact != Decimal("0.5"):
                raise ValueError(f"unexpected S4 gradient radius: {radius!r}")
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


def load_frozen_analyzer() -> Any:
    specification = importlib.util.spec_from_file_location(
        "geotarget_s4_frozen_analysis_a9", ORIGINAL_ANALYZER
    )
    if specification is None or specification.loader is None:
        raise ImportError("cannot load frozen S4 analyzer")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def main() -> int:
    amendment = load_json(ANALYSIS_AMENDMENT)
    if amendment["status"] != "frozen-after-radius-token-analysis-failure":
        raise ValueError("S4 A9 status mismatch")
    if sha256(Path(__file__)) != amendment["wrapper_source_sha256"]:
        raise ValueError("S4 A9 wrapper source mismatch")
    if sha256(ORIGINAL_ANALYZER) != amendment["original_analyzer_sha256"]:
        raise ValueError("S4 A9 original analyzer mismatch")
    result_index = sys.argv.index("--result-directory") + 1
    result_directory = Path(sys.argv[result_index]).resolve()
    destination = result_directory / "independent-analysis.json"
    binding_path = result_directory / "independent-analysis-a9-bindings.json"
    if destination.exists() or binding_path.exists():
        raise FileExistsError("S4 A9 refuses an existing independent analysis")

    frozen = load_frozen_analyzer()
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
    analysis = load_json(destination)
    if analysis.get("independent_reconstruction_passed") is not True:
        raise ValueError("S4 A9 analyzer returned success without reconstruction pass")
    write_json_atomic(
        binding_path,
        {
            "analysis_amendment_sha256": sha256(ANALYSIS_AMENDMENT),
            "independent_analysis_sha256": sha256(destination),
            "normalization_count": normalization_count,
            "original_analyzer_sha256": sha256(ORIGINAL_ANALYZER),
            "product_connected": False,
            "result_bindings_sha256": sha256(result_directory / "result-bindings.json"),
            "schema": "geotarget.singular-s4-independent-analysis-a9-bindings/v1",
            "wrapper_source_sha256": sha256(Path(__file__)),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
