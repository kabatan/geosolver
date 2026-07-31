#!/usr/bin/env python3
"""Root-custody builder for the disposable Vieta v4 private manifest.

The builder reads only raw solve inputs and ordinary HP authority artifacts.
It never reads a scorer, truth, control outcome, candidate outcome, or known
target count.  Selection is entirely by authenticated source/endpoint bytes
and frozen SHA-256 ranking.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from itertools import combinations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from typing import Any, Mapping, Sequence


HERE = Path(__file__).resolve().parent
CONNECTOR_PATH = HERE / "canonical_connector.py"
CONNECTOR_SHA256 = "b6e9dd7bb5c62a657451fd18294cbceef032d6b764cace0628d878684faa2b41"
RESULTS_ROOT = Path("/home/kabatan/work/solver-experiment-results")
PANEL_SCHEMA = "geotarget.cross-endpoint-vieta-private-gate/v2"
WORK_ITEM_SCHEMA = "geotarget.cross-endpoint-vieta-private-subset/v4"
AGGREGATE_SCHEMA = "geotarget.cross-endpoint-vieta-v4-manifest-build/v1"
MAX_SOURCE_BYTES = 4 * 1024 * 1024
MAX_ARTIFACT_BYTES = 16 * 1024 * 1024
MAX_SOURCES = 128
MAX_SUBSETS_PER_SOURCE = 16
MAX_SUBSETS = 595
LOW_BITS = 768
HIGH_BITS = 1024


class BuildFailure(RuntimeError):
    pass


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _valid_sha(value: object) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _load_connector() -> Any:
    if _sha256(CONNECTOR_PATH.read_bytes()) != CONNECTOR_SHA256:
        raise BuildFailure("frozen v4 connector changed")
    specification = importlib.util.spec_from_file_location(
        "geotarget_cross_endpoint_vieta_manifest_connector", CONNECTOR_PATH
    )
    if specification is None or specification.loader is None:
        raise BuildFailure("cannot load v4 connector")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    module.verify_frozen_dependencies()
    return module


def _within(path: Path, root: Path, *, must_exist: bool) -> Path:
    resolved = path.resolve(strict=must_exist)
    approved = root.resolve(strict=True)
    if resolved == approved or approved not in resolved.parents:
        raise BuildFailure("path is outside its approved root")
    return resolved


def _regular_file(path: Path, root: Path, *, max_bytes: int) -> tuple[Path, bytes]:
    path = _within(path, root, must_exist=True)
    metadata = path.stat()
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or metadata.st_uid != os.getuid()
        or not 0 < metadata.st_size <= max_bytes
    ):
        raise BuildFailure("artifact is not a bounded owner-controlled regular file")
    return path, path.read_bytes()


def _json(payload: bytes, label: str, connector: Any) -> dict[str, Any]:
    try:
        value = json.loads(payload, object_pairs_hook=connector._strict_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BuildFailure(f"{label} is not strict JSON") from error
    if not isinstance(value, dict):
        raise BuildFailure(f"{label} is not a JSON object")
    return value


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _source_records(input_directory: Path, connector: Any) -> dict[str, dict[str, Any]]:
    input_directory = input_directory.resolve(strict=True)
    if not input_directory.is_dir():
        raise BuildFailure("formal-control input directory is absent")
    by_raw_sha: dict[str, dict[str, Any]] = {}
    by_projection_sha: dict[str, str] = {}
    paths = sorted(input_directory.glob("*.json"))
    if not paths:
        raise BuildFailure("formal-control input directory has no JSON sources")
    for source_path in paths:
        source_path, payload = _regular_file(
            source_path, input_directory, max_bytes=MAX_SOURCE_BYTES
        )
        raw_sha = _sha256(payload)
        source = _json(payload, "raw source", connector)
        if source.get("task") != "solve" or "id" not in source:
            raise BuildFailure("formal input is not an id-bearing solve source")
        projection = dict(source)
        projection.pop("id")
        projection_payload = (
            json.dumps(
                projection,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
        projection_sha = _sha256(projection_payload)
        binding, observed_raw, observed_projection, _document = connector._source(
            {"path": str(source_path), "sha256": raw_sha}, projection_sha
        )
        if observed_raw != raw_sha or observed_projection != projection_payload:
            raise BuildFailure("connector source authentication changed")
        if raw_sha in by_raw_sha:
            raise BuildFailure("formal input directory repeats raw source bytes")
        if projection_sha in by_projection_sha:
            raise BuildFailure("two id-bearing sources collapse to one anonymous projection")
        by_projection_sha[projection_sha] = raw_sha
        by_raw_sha[raw_sha] = {
            "source_artifact": {"path": str(binding["path"]), "sha256": raw_sha},
            "source_projection_sha256": projection_sha,
        }
    return by_raw_sha


def _binding(path: Path, payload: bytes) -> dict[str, str]:
    return {"path": str(path), "sha256": _sha256(payload)}


def _authority_lanes(authority: Mapping[str, Any]) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    final = authority.get("final_result")
    numeric = final.get("original_numerical_replay") if isinstance(final, Mapping) else None
    lanes = numeric.get("lanes") if isinstance(numeric, Mapping) else None
    if not isinstance(lanes, list):
        raise BuildFailure("ordinary HP numeric replay lanes are absent")
    selected: list[Mapping[str, Any]] = []
    for precision in (LOW_BITS, HIGH_BITS):
        matches = [
            lane
            for lane in lanes
            if isinstance(lane, Mapping) and lane.get("bits") == precision
        ]
        if len(matches) != 1:
            raise BuildFailure("ordinary HP authority lacks one frozen precision lane")
        lane = matches[0]
        if not (
            lane.get("finite") is True
            and lane.get("hard_feasible") is True
            and lane.get("guard_ok") is True
            and lane.get("guard_violations") == []
            and lane.get("raw_hard_feasible_without_intrinsic_domains") is True
            and lane.get("intrinsic_domain_ok") is True
            and lane.get("intrinsic_domain_violations") == []
            and isinstance(lane.get("point"), list)
            and lane["point"]
            and all(isinstance(item, str) and item for item in lane["point"])
            and isinstance(lane.get("answer"), str)
            and lane["answer"]
        ):
            raise BuildFailure("ordinary HP lane lacks frozen numeric replay parity")
        selected.append(lane)
    return selected[0], selected[1]


def _endpoint_record(
    directory: Path,
    *,
    artifact_root: Path,
    sources: Mapping[str, Mapping[str, Any]],
    connector: Any,
) -> tuple[str, dict[str, Any]]:
    plan_path, plan_payload = _regular_file(
        directory / "PLAN.json", artifact_root, max_bytes=MAX_ARTIFACT_BYTES
    )
    result_path, result_payload = _regular_file(
        directory / "RESULT.json", artifact_root, max_bytes=MAX_ARTIFACT_BYTES
    )
    lane_path, lane_payload = _regular_file(
        directory / "authority.json", artifact_root, max_bytes=MAX_ARTIFACT_BYTES
    )
    plan = _json(plan_payload, "ordinary HP PLAN", connector)
    result = _json(result_payload, "ordinary HP RESULT", connector)
    authority = _json(lane_payload, "ordinary HP authority", connector)
    raw_source_sha = result.get("source_sha256")
    endpoint_sha = result.get("endpoint_float64_sha256")
    if (
        result.get("schema_version")
        != "geotarget.exp008-single-raw-endpoint-hp-result/v1"
        or result.get("status") != "COMPLETE"
        or result.get("process_classification") != "SUCCESS"
        or result.get("artifact_accepted") is not True
        or result.get("authority_pass") is not True
        or not _valid_sha(raw_source_sha)
        or not _valid_sha(endpoint_sha)
        or raw_source_sha not in sources
        or plan.get("schema_version")
        != "geotarget.exp008-single-raw-endpoint-hp-plan/v1"
        or plan.get("source_sha256") != raw_source_sha
        or plan.get("endpoint_float64_sha256") != endpoint_sha
        or authority.get("schema_version")
        != "geotarget.exp008-target-first-fallback-composition/v1"
        or authority.get("status") != "TARGET_AUTHORITY_READY"
        or authority.get("authority_pass") is not True
    ):
        raise BuildFailure("ordinary HP artifact triple is not accepted/bound")
    endpoint_bits = connector._plan_endpoint_bits(plan)
    if connector._endpoint_sha256(endpoint_bits) != endpoint_sha:
        raise BuildFailure("PLAN endpoint bits do not match endpoint digest")
    low, high = _authority_lanes(authority)
    result_binding = _binding(result_path, result_payload)
    plan_binding = _binding(plan_path, plan_payload)
    lane_binding = _binding(lane_path, lane_payload)
    bindings = {
        "result_artifact": result_binding,
        "plan_artifact": plan_binding,
        "lane_artifact": lane_binding,
    }

    def rung(precision: int, lane: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "precision_bits": precision,
            "provenance_sha256": connector._hp_provenance_sha256(
                result_sha256=result_binding["sha256"],
                plan_sha256=plan_binding["sha256"],
                lane_sha256=lane_binding["sha256"],
                source_sha256=str(raw_source_sha),
                endpoint_bits=endpoint_bits,
                endpoint_sha256=str(endpoint_sha),
                precision_bits=precision,
            ),
            "raw_answer_decimal": lane["answer"],
            "full_tuple_decimal": list(lane["point"]),
            **bindings,
        }

    low_rung = rung(LOW_BITS, low)
    high_rung = rung(HIGH_BITS, high)
    projection_sha = str(sources[str(raw_source_sha)]["source_projection_sha256"])
    connector._rung(
        low_rung,
        precision_bits=LOW_BITS,
        dimension=len(endpoint_bits),
        artifact_source_sha256=str(raw_source_sha),
        source_projection_sha256=projection_sha,
        endpoint_bits=endpoint_bits,
        endpoint_sha256=str(endpoint_sha),
    )
    connector._rung(
        high_rung,
        precision_bits=HIGH_BITS,
        dimension=len(endpoint_bits),
        artifact_source_sha256=str(raw_source_sha),
        source_projection_sha256=projection_sha,
        endpoint_bits=endpoint_bits,
        endpoint_sha256=str(endpoint_sha),
    )
    return str(raw_source_sha), {
        "endpoint_float64_bits_hex": list(endpoint_bits),
        "endpoint_float64_sha256": endpoint_sha,
        "low": low_rung,
        "high": high_rung,
        "custody_rank_sha256": _sha256(
            bytes.fromhex(result_binding["sha256"])
            + bytes.fromhex(plan_binding["sha256"])
            + bytes.fromhex(lane_binding["sha256"])
        ),
    }


def _candidate_directories(artifact_root: Path, connector: Any) -> tuple[list[Path], int]:
    directories: list[Path] = []
    ignored = 0
    for plan_path in sorted(artifact_root.rglob("PLAN.json")):
        try:
            path, payload = _regular_file(
                plan_path, artifact_root, max_bytes=MAX_ARTIFACT_BYTES
            )
        except BuildFailure:
            ignored += 1
            continue
        # Schema prefilter prevents unrelated PLAN/RESULT/outcome trees from
        # becoming semantic inputs to this builder.
        if b"geotarget.exp008-single-raw-endpoint-hp-plan/v1" not in payload:
            ignored += 1
            continue
        if not (path.parent / "RESULT.json").is_file() or not (
            path.parent / "authority.json"
        ).is_file():
            ignored += 1
            continue
        directories.append(path.parent)
    return directories, ignored


def _source_rank(projection_sha: str) -> str:
    return _sha256(b"vieta-source-v1" + bytes.fromhex(projection_sha))


def build_manifest(
    *,
    artifact_root: Path,
    input_directory: Path,
    private_output: Path,
    aggregate_output: Path,
) -> dict[str, Any]:
    connector = _load_connector()
    artifact_root = artifact_root.resolve(strict=True)
    approved_results = RESULTS_ROOT.resolve(strict=True)
    if artifact_root != approved_results and approved_results not in artifact_root.parents:
        raise BuildFailure("formal-control artifact root is outside approved results")
    private_output = _within(private_output, RESULTS_ROOT, must_exist=False)
    aggregate_output = _within(aggregate_output, RESULTS_ROOT, must_exist=False)
    if private_output == aggregate_output:
        raise BuildFailure("private manifest and aggregate output paths must differ")
    sources = _source_records(input_directory, connector)
    directories, ignored_plan_count = _candidate_directories(artifact_root, connector)
    accepted_by_source: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    custody_replacements = 0
    rejected = Counter()
    for directory in directories:
        try:
            raw_source_sha, endpoint = _endpoint_record(
                directory,
                artifact_root=artifact_root,
                sources=sources,
                connector=connector,
            )
        except Exception as error:
            rejected[type(error).__name__] += 1
            continue
        endpoint_sha = str(endpoint["endpoint_float64_sha256"])
        existing = accepted_by_source[raw_source_sha].get(endpoint_sha)
        if existing is None or endpoint["custody_rank_sha256"] < existing["custody_rank_sha256"]:
            if existing is not None:
                custody_replacements += 1
            accepted_by_source[raw_source_sha][endpoint_sha] = endpoint

    grouped: list[tuple[str, list[dict[str, Any]]]] = []
    for raw_source_sha, endpoints_by_sha in accepted_by_source.items():
        if len(endpoints_by_sha) < 2:
            continue
        source = sources[raw_source_sha]
        projection_sha = str(source["source_projection_sha256"])
        endpoints = list(endpoints_by_sha.values())
        ranked_subsets: list[tuple[str, dict[str, Any]]] = []
        for degree in range(2, min(6, len(endpoints)) + 1):
            for selected in combinations(endpoints, degree):
                subset_sha = connector.subset_sha256(
                    projection_sha,
                    [str(endpoint["endpoint_float64_sha256"]) for endpoint in selected],
                )
                row = {
                    "schema_version": WORK_ITEM_SCHEMA,
                    "source_artifact": dict(source["source_artifact"]),
                    "source_projection_sha256": projection_sha,
                    "subset_sha256": subset_sha,
                    "endpoints": [
                        {key: value for key, value in endpoint.items() if key != "custody_rank_sha256"}
                        for endpoint in selected
                    ],
                }
                ranked_subsets.append((subset_sha, row))
        ranked_subsets.sort(key=lambda item: item[0])
        grouped.append(
            (projection_sha, [row for _digest, row in ranked_subsets[:MAX_SUBSETS_PER_SOURCE]])
        )
    grouped.sort(key=lambda item: _source_rank(item[0]))
    rows: list[dict[str, Any]] = []
    for _projection_sha, source_rows in grouped[:MAX_SOURCES]:
        for row in source_rows:
            if len(rows) == MAX_SUBSETS:
                break
            rows.append(row)
        if len(rows) == MAX_SUBSETS:
            break
    if not rows:
        raise BuildFailure("no source has two authenticated ordinary HP endpoints")

    # Mandatory final replay of the exact private schema and every artifact
    # binding before any bytes are published.
    validated = [connector.validate_private_subset(row) for row in rows]
    if len(validated) != len(rows):
        raise BuildFailure("v4 connector did not validate every generated row")
    panel = {"schema_version": PANEL_SCHEMA, "subsets": rows}
    panel_payload = (
        json.dumps(panel, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    aggregate = {
        "schema_version": AGGREGATE_SCHEMA,
        "status": "PRIVATE_V4_MANIFEST_READY",
        "formal_input_source_count": len(sources),
        "ordinary_hp_plan_directory_count": len(directories),
        "ignored_nonordinary_plan_count": ignored_plan_count,
        "rejected_ordinary_hp_artifact_count": sum(rejected.values()),
        "accepted_unique_endpoint_count": sum(
            len(endpoints) for endpoints in accepted_by_source.values()
        ),
        "eligible_anonymous_source_group_count": len(grouped),
        "private_subset_count": len(rows),
        "private_manifest_sha256": _sha256(panel_payload),
        "connector_sha256": CONNECTOR_SHA256,
        "selection": {
            "source_rank": "sha256(vieta-source-v1 || source_projection_sha256)",
            "subset_rank": "vieta-subset-v1 digest",
            "max_sources": MAX_SOURCES,
            "max_subsets_per_source": MAX_SUBSETS_PER_SOURCE,
            "max_subsets": MAX_SUBSETS,
            "degrees": [2, 3, 4, 5, 6],
        },
        "all_private_rows_revalidated": True,
        "private_output_mode": "0600",
        "truth_read": False,
        "scorer_read": False,
        "control_or_candidate_outcome_read": False,
        "case_or_family_identity_routing": False,
        "individual_records_emitted_publicly": False,
        "public_paths_or_source_hashes_emitted": False,
    }
    aggregate["aggregate_sha256"] = _sha256(
        json.dumps(aggregate, sort_keys=True, separators=(",", ":")).encode()
    )
    _atomic_json(private_output, panel)
    if private_output.read_bytes() != panel_payload or stat.S_IMODE(private_output.stat().st_mode) != 0o600:
        raise BuildFailure("private v4 manifest bytes/mode changed after atomic write")
    _atomic_json(aggregate_output, aggregate)
    print(json.dumps(aggregate, sort_keys=True))
    return aggregate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--input-directory", required=True, type=Path)
    parser.add_argument("--private-output", required=True, type=Path)
    parser.add_argument("--aggregate-output", required=True, type=Path)
    arguments = parser.parse_args()
    build_manifest(
        artifact_root=arguments.artifact_root,
        input_directory=arguments.input_directory,
        private_output=arguments.private_output,
        aggregate_output=arguments.aggregate_output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
