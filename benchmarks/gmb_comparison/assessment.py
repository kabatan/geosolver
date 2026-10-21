"""Offline, fail-closed assessment of immutable GMB/GeoSolver comparison evidence.

This module never starts a solver or repairs a witness. Run it only after the
controller has sealed new artifacts in RAW_SHA256SUMS. Old GMB campaigns are
read through their original, manifest-pinned SHA256SUMS files.

The primary metric is first *emitted*, native-accepted, commonly valid model,
not successful process termination. Offline checking time is recorded once in
immutable per-model results and is not charged to the search time. Reaggregation
reuses only hash-verified assessment records, making every output reproducible.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

import mpmath

from benchmarks.gmb_comparison.canary import (
    observation_record_issues,
    unexpected_observation_failure,
)
from benchmarks.gmb_comparison.checker import (
    CHECKER_POLICY,
    check_configuration,
    inspect_gmbl,
    witness_from_gmb_model,
)
from benchmarks.gmb_comparison.checker_geometry import CheckError

METHODS = ("gmb", "geosolver")
NATIVE_STAGE = "native_accepted_return"
VERSION = 1
COMMON_THREADS = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)


class EvidenceError(ValueError):
    """An artifact cannot support the claimed experimental observation."""


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(value, *, pretty=False):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, allow_nan=False, indent=2 if pretty else None
    )


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceError(f"duplicate_json_key:{key}")
        result[key] = value
    return result


def _invalid_constant(value):
    raise EvidenceError(f"nonfinite_json_constant:{value}")


def _finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise EvidenceError(f"nonfinite_json_number:{value}")
    return number


def _decode(text):
    try:
        return json.loads(
            text,
            object_pairs_hook=_pairs,
            parse_constant=_invalid_constant,
            parse_float=_finite_float,
        )
    except (ValueError, TypeError) as error:
        raise EvidenceError(f"invalid_json:{error}") from error


def _relative(root, name):
    if not isinstance(name, str) or not name or "\\" in name or "\x00" in name:
        raise EvidenceError("invalid_relative_path")
    path = Path(name)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != name:
        raise EvidenceError(f"unsafe_relative_path:{name}")
    result = root / path
    if not result.resolve().is_relative_to(root.resolve()):
        raise EvidenceError(f"escaping_symlink:{name}")
    return result


def _number(value):
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


def _identifier(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value)


class Seal:
    """A checksum index; only verified files may be decoded as experimental data."""

    def __init__(self, root, name, *, expected_sha256=None):
        self.root = Path(root).resolve()
        self.path = self.root / name
        if not self.path.is_file():
            raise EvidenceError(f"missing_seal:{self.path}")
        self.digest = sha256(self.path)
        if expected_sha256 is not None and self.digest != expected_sha256:
            raise EvidenceError(f"seal_hash_mismatch:{self.path}")
        self.entries = {}
        self.verified = set()
        for line in self.path.read_text(encoding="utf-8").splitlines():
            digest, separator, relative = line.partition("  ")
            if not separator or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise EvidenceError(f"invalid_seal_line:{self.path.name}")
            _relative(self.root, relative)
            if relative in self.entries:
                raise EvidenceError(f"duplicate_seal_entry:{relative}")
            self.entries[relative] = digest

    def relative(self, path):
        path = Path(path).absolute()
        if not path.is_relative_to(self.root):
            raise EvidenceError(f"path_outside_seal:{path}")
        name = path.relative_to(self.root).as_posix()
        _relative(self.root, name)
        return name

    def verify(self, path):
        relative = self.relative(path)
        expected = self.entries.get(relative)
        if expected is None:
            raise EvidenceError(f"unsealed_file:{relative}")
        if not Path(path).is_file():
            raise EvidenceError(f"missing_file:{relative}")
        # Cache only within this read-only assessment invocation. Check the seal
        # again before publishing; never reuse this cache across invocations.
        if relative not in self.verified:
            if sha256(path) != expected:
                raise EvidenceError(f"file_hash_mismatch:{relative}")
            self.verified.add(relative)
        return expected

    def read(self, path):
        self.verify(path)
        return Path(path).read_text(encoding="utf-8")

    def mapping(self, path):
        value = _decode(self.read(path))
        if not isinstance(value, dict):
            raise EvidenceError(f"expected_json_object:{self.relative(path)}")
        return value

    def directory_issues(self, directory):
        """Include logs, identity and orphan files, not merely favorable models."""
        prefix = self.relative(directory) + "/"
        names = {name for name in self.entries if name.startswith(prefix)}
        if Path(directory).is_dir():
            names.update(
                self.relative(path) for path in Path(directory).rglob("*") if path.is_file()
            )
        issues = []
        for name in sorted(names):
            try:
                self.verify(self.root / name)
            except EvidenceError as error:
                issues.append(str(error))
        return issues

    def recheck(self):
        if sha256(self.path) != self.digest:
            raise EvidenceError(f"seal_changed_during_assessment:{self.path}")
        for relative in sorted(self.verified):
            path = self.root / relative
            if not path.is_file() or sha256(path) != self.entries[relative]:
                raise EvidenceError(f"raw_changed_during_assessment:{relative}")


def checker_identity():
    here = Path(__file__).resolve().parent
    return {
        "source_sha256": {
            name: sha256(here / name)
            for name in ("assessment.py", "checker.py", "checker_geometry.py", "canary.py")
        },
        "policy": CHECKER_POLICY,
        "python": sys.version,
        "mpmath": mpmath.__version__,
    }


def _put(path, text):
    """An assessment is append-only: reruns must produce the identical content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise EvidenceError(f"refusing_to_overwrite_assessment:{path}")
        return
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("x", encoding="utf-8", newline="") as handle:
        handle.write(text)
    temporary.replace(path)


def _put_json(path, value):
    _put(path, _json(value, pretty=True) + "\n")


def _failure_reasons(result, section="assumptions"):
    reasons = set()
    if result.get("code"):
        reasons.add(str(result["code"]))
    for clause in result.get(section, []):
        if clause.get("status") == "passed":
            continue
        prefix = f"{clause.get('source_path', '?')}:{clause.get('status', 'unknown')}"
        if clause.get("code"):
            reasons.add(f"{prefix}:{clause['code']}")
        for item in clause.get("checks", []):
            if item.get("status") != "passed":
                reasons.add(f"{prefix}:{item.get('label', item.get('code', 'condition'))}")
        if not clause.get("code") and not clause.get("checks"):
            reasons.add(prefix)
    if not reasons and result.get("valid") is not True and section == "assumptions":
        reasons.add(str(result.get("status", "not_checked")))
    return sorted(reasons)


class Assessment:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.raw = Seal(self.root, "RAW_SHA256SUMS")
        self.manifest = self.raw.mapping(self.root / "campaign-manifest.json")
        self.manifest_hash = self.raw.verify(self.root / "campaign-manifest.json")
        self._validate_manifest()
        self.identity = checker_identity()
        for name, digest in self.identity["source_sha256"].items():
            frozen = self.manifest.get("identity_files", {}).get(
                f"benchmarks/gmb_comparison/{name}"
            )
            if frozen is not None and frozen != digest:
                raise EvidenceError(f"checker_changed_since_campaign_freeze:{name}")
        self.legacy = {}
        self.legacy_errors = {}
        for source in self.manifest.get("legacy_sources", []):
            directory = Path(source["directory"]).resolve()
            try:
                seal = Seal(directory, "SHA256SUMS", expected_sha256=source["sha256sums_sha256"])
                if seal.verify(directory / "campaign-manifest.json") != source["manifest_sha256"]:
                    raise EvidenceError("legacy_manifest_hash_mismatch")
                old = seal.mapping(directory / "campaign-manifest.json")
                if old["seeds"] != source["seeds"]:
                    raise EvidenceError("legacy_seed_profile_mismatch")
                self.legacy[directory] = (seal, old, source)
            except (EvidenceError, OSError, KeyError, TypeError) as error:
                self.legacy_errors[directory] = str(error)
        self.output = self.root / "assessment"
        self.previous = None
        if self.output.exists():
            self.previous = Seal(self.output, "SHA256SUMS")
            for relative in sorted(self.previous.entries):
                self.previous.verify(self.output / relative)
            extra = {
                path.relative_to(self.output).as_posix()
                for path in self.output.rglob("*")
                if path.is_file() and path != self.previous.path
            } - self.previous.entries.keys()
            if extra:
                raise EvidenceError(f"unsealed_assessment_files:{sorted(extra)}")

    def _validate_manifest(self):
        manifest = self.manifest
        if manifest.get("schema_version") != VERSION:
            raise EvidenceError("unsupported_campaign_schema")
        if not isinstance(manifest.get("cpu"), int) or isinstance(manifest["cpu"], bool):
            raise EvidenceError("invalid_campaign_cpu")
        if not _number(manifest.get("timeout_seconds")) or manifest["timeout_seconds"] <= 0:
            raise EvidenceError("invalid_campaign_timeout")
        seeds = manifest.get("seeds")
        if (
            not isinstance(seeds, list)
            or not seeds
            or any(
                not isinstance(seed, int) or isinstance(seed, bool) or seed < 0 for seed in seeds
            )
            or len(set(seeds)) != len(seeds)
        ):
            raise EvidenceError("invalid_campaign_seeds")
        entries = manifest.get("entries")
        if not isinstance(entries, list) or not entries:
            raise EvidenceError("missing_campaign_entries")
        ids = [entry.get("case_id") for entry in entries if isinstance(entry, dict)]
        if len(ids) != len(entries) or any(not _identifier(value) for value in ids):
            raise EvidenceError("invalid_case_id")
        if len(set(ids)) != len(ids):
            raise EvidenceError("duplicate_case_id")
        protocol = manifest.get("protocol", {})
        self.tolerances = protocol.get("sensitivity_tolerances")
        self.primary_tolerance = protocol.get("common_tolerance")
        self.dps = protocol.get("checker_dps")
        if (
            not isinstance(self.tolerances, list)
            or not self.tolerances
            or any(not isinstance(value, str) for value in self.tolerances)
            or len(set(self.tolerances)) != len(self.tolerances)
            or self.primary_tolerance not in self.tolerances
            or not isinstance(self.dps, int)
            or isinstance(self.dps, bool)
            or self.dps < 40
        ):
            raise EvidenceError("invalid_checker_protocol")
        for value in self.tolerances:
            try:
                numeric = float(value)
            except ValueError as error:
                raise EvidenceError("invalid_tolerance") from error
            if not math.isfinite(numeric) or not 0 < numeric < 1:
                raise EvidenceError("invalid_tolerance")

    def _case(self, entry):
        issues, text = [], None
        for prefix in ("geo", "gmbl"):
            try:
                path = _relative(self.root, entry[f"{prefix}_input"])
                if self.raw.verify(path) != entry[f"{prefix}_sha256"]:
                    raise EvidenceError(f"{prefix}_input_hash_mismatch")
                if prefix == "gmbl":
                    text = self.raw.read(path)
            except (EvidenceError, OSError, KeyError, TypeError) as error:
                issues.append(str(error))
        if entry.get("original_assumptions_covered") is not True:
            issues.append("original_assumptions_not_approved")
        if text is not None:
            coverage = inspect_gmbl(text)
            if coverage.get("supported") is not True:
                issues.append("checker_source_coverage_incomplete")
            if coverage.get("declarations") != entry.get("declarations"):
                issues.append("declared_objects_mismatch")
        return text, issues

    def _location(self, entry, seed, method):
        if method == "geosolver":
            directory = self.root / "geosolver/runs" / entry["case_id"] / str(seed)
            return directory, self.raw, self.manifest, self.manifest_hash, "new_geosolver"
        chosen = entry["gmb_runs"][str(seed)]
        directory = Path(chosen["directory"]).resolve()
        origin = chosen["origin"]
        if origin == "new_aligned":
            expected = self.root / "gmb-aligned/runs" / entry["case_id"] / str(seed)
            if directory != expected:
                raise EvidenceError("aligned_run_directory_mismatch")
            path = self.root / "gmb-aligned/campaign-manifest.json"
            native = self.raw.mapping(path)
            if native.get("comparison_manifest_sha256") != self.manifest_hash:
                raise EvidenceError("aligned_comparison_manifest_mismatch")
            return directory, self.raw, native, self.raw.verify(path), origin
        if origin != "reused_official":
            raise EvidenceError("unsupported_gmb_origin")
        for source in self.manifest.get("legacy_sources", []):
            root = Path(source["directory"]).resolve()
            if directory != root / "runs" / entry["case_id"] / str(seed):
                continue
            if seed not in source["seeds"]:
                raise EvidenceError("wrong_legacy_seed_source")
            if root in self.legacy_errors:
                raise EvidenceError(f"legacy_source_invalid:{self.legacy_errors[root]}")
            seal, native, _ = self.legacy[root]
            return directory, seal, native, source["manifest_sha256"], origin
        raise EvidenceError("gmb_run_not_in_pinned_legacy_sources")

    @staticmethod
    def _optional(seal, path):
        # A process may be killed after a valid model but before its final result.
        # Missing *sealed* files are corruption; files never produced are absence.
        if path.is_file() or seal.relative(path) in seal.entries:
            return seal.mapping(path)
        return None

    def _run_contract(self, directory, seal, native, native_hash, entry, seed, method):
        issues = seal.directory_issues(directory)
        run = seal.mapping(directory / "run.json")
        request = seal.mapping(directory / "request.json")
        for required in ("stdout.log", "stderr.log"):
            seal.verify(directory / required)
        expected_hash = entry["geo_sha256" if method == "geosolver" else "gmbl_sha256"]
        for label, value in (("run", run), ("request", request)):
            if value.get("schema_version") != VERSION:
                issues.append(f"{label}_schema_mismatch")
            for key, expected in (
                ("case_id", entry["case_id"]),
                ("seed", seed),
                ("input_sha256", expected_hash),
            ):
                if value.get(key) != expected:
                    issues.append(f"{label}_{key}_mismatch")
        if run.get("manifest_sha256") != native_hash:
            issues.append("run_manifest_hash_mismatch")
        if native.get("cpu") != self.manifest["cpu"] or seed not in native.get("seeds", []):
            issues.append("source_manifest_resource_or_seed_mismatch")
        if native.get("timeout_seconds") != self.manifest["timeout_seconds"]:
            issues.append("source_manifest_timeout_mismatch")
        if request.get("cpu") != self.manifest["cpu"]:
            issues.append("request_cpu_mismatch")
        if request.get("instrument", True) is not True:
            issues.append("observation_not_enabled")
        input_path = Path(request.get("input", ""))
        if not input_path.is_absolute() or seal.verify(input_path) != expected_hash:
            issues.append("request_input_hash_mismatch")
        if method == "gmb":
            matched = [item for item in native["entries"] if item["case_id"] == entry["case_id"]]
            if len(matched) != 1 or matched[0].get("input_sha256") != expected_hash:
                issues.append("gmb_source_manifest_input_mismatch")
            for key in ("options", "upstream_defaults"):
                if request.get(key) != native.get(key):
                    issues.append(f"gmb_request_{key}_mismatch")
        else:
            if request.get("timeout_seconds") != self.manifest["timeout_seconds"]:
                issues.append("geosolver_request_timeout_mismatch")
            for key in ("declarations", "bindings"):
                if request.get(key, {}) != entry.get(key, {}):
                    issues.append(f"geosolver_request_{key}_mismatch")
            if request.get("engine_identity") != self.manifest.get("engine_identity"):
                issues.append("geosolver_request_engine_identity_mismatch")
        environment = run.get("environment", {})
        for key in COMMON_THREADS:
            if environment.get(key) != "1":
                issues.append(f"thread_limit_not_one:{key}")
        for key, value in environment.items():
            if key.endswith("_THREADS") and value != "1":
                issues.append(f"thread_limit_not_one:{key}")
        if environment.get("PYTHONHASHSEED") != str(seed):
            issues.append("python_hash_seed_mismatch")
        if environment.get("CUDA_VISIBLE_DEVICES") != "-1":
            issues.append("gpu_not_disabled")
        return run, request, issues

    def _resources(self, process, child, artifact, identity):
        issues, masks = [], []
        if not isinstance(process, dict):
            raise EvidenceError("missing_process_record")
        for key in ("wall_seconds", "cpu_seconds", "peak_rss_bytes"):
            if not _number(process.get(key)):
                issues.append(f"invalid_resource_measurement:{key}")
        for key in ("timed_out", "cancelled", "descendants_remaining_at_leader_exit"):
            if not isinstance(process.get(key), bool):
                issues.append(f"invalid_process_flag:{key}")
        if not isinstance(process.get("returncode"), int):
            issues.append("missing_process_returncode")
        if not isinstance(process.get("affinity_violations"), list):
            issues.append("missing_affinity_monitor")
        elif process["affinity_violations"]:
            issues.append("cpu_affinity_violation")
        observed = process.get("affinity_masks_observed")
        if not isinstance(observed, list):
            issues.append("missing_observed_affinity")
        else:
            masks.extend(observed)
        for value in (child, identity, (artifact or {}).get("process_info")):
            if isinstance(value, dict) and "cpu_affinity" in value:
                masks.append(value["cpu_affinity"])
        if not masks:
            issues.append("cpu_affinity_unconfirmed")
        if any(mask != [self.manifest["cpu"]] for mask in masks):
            issues.append("cpu_affinity_mismatch")
        if process.get("descendants_remaining_at_leader_exit"):
            issues.append("uncollected_descendants_at_leader_exit")
        if identity and identity.get("visible_gpus") != []:
            issues.append("worker_gpu_visibility_mismatch")
        return issues

    @staticmethod
    def _termination(process, child, method):
        if process.get("cancelled"):
            return "cancelled"
        if process.get("affinity_violations") or process.get(
            "descendants_remaining_at_leader_exit"
        ):
            return "resource_violation"
        if process.get("timed_out"):
            return "timeout"
        if method == "gmb" and child and child.get("outcome") == "error":
            return "error"
        if process.get("returncode") != 0 or child is None:
            return "crash"
        return child.get("outcome", "invalid_artifact")

    def _events(self, seal, directory, wall):
        events, issues = [], []
        previous = -1
        for index, line in enumerate(seal.read(directory / "events.jsonl").splitlines()):
            if not line.strip():
                continue
            value = _decode(line)
            if not isinstance(value, dict) or not isinstance(value.get("event"), str):
                raise EvidenceError(f"invalid_event:{index}")
            elapsed = value.get("elapsed_seconds")
            if not _number(elapsed) or elapsed < previous or (_number(wall) and elapsed > wall):
                issues.append(f"invalid_event_clock:{index}")
            else:
                previous = elapsed
            events.append(value)
        return events, issues

    def _check_model(self, path, seal, event, entry, seed, method, text):
        digest = seal.verify(path)
        payload = seal.mapping(path)
        identity = {
            "case_id": entry["case_id"],
            "seed": seed,
            "method": method,
            "model_sha256": digest,
            "gmbl_sha256": entry["gmbl_sha256"],
            "event_sha256": hashlib.sha256(_json(event).encode()).hexdigest(),
            "checker": self.identity,
            "tolerances": self.tolerances,
            "dps": self.dps,
        }
        output = self.output / "models" / method / entry["case_id"] / str(seed) / path.name
        if output.exists():
            if self.previous is None:
                raise EvidenceError("unsealed_cached_assessment")
            cached = self.previous.mapping(output)
            if cached.get("identity") != identity:
                raise EvidenceError("cached_assessment_identity_mismatch")
            return cached
        if self.previous is not None:
            raise EvidenceError("previous_assessment_missing_model")
        issues, result = [], {}
        native = method == "gmb" or payload.get("stage") == NATIVE_STAGE
        emitted = event.get("elapsed_seconds" if method == "gmb" else "emitted_seconds")
        if not _number(emitted):
            issues.append("invalid_model_emission_time")
        if method == "geosolver":
            try:
                # Late but consistently recorded models are not corrupt records.
                # Actual deadline exclusion is a separate gate below.
                issues.extend(observation_record_issues(payload, event, timeout=math.inf))
                if not all(
                    _number(payload.get(key))
                    for key in ("coordinate_observed_seconds", "materialized_seconds")
                ):
                    issues.append("invalid_model_observation_clock")
                if _number(emitted) and emitted > event["elapsed_seconds"]:
                    issues.append("emission_after_logging_clock")
            except (KeyError, TypeError, ValueError) as error:
                issues.append(f"invalid_observation_record:{type(error).__name__}")
        elif (
            not _number(event.get("materialized_seconds"))
            or not _number(emitted)
            or event["materialized_seconds"] > emitted
        ):
            issues.append("invalid_gmb_materialization_clock")
        started = time.perf_counter()
        try:
            witness = (
                payload["witness"] if method == "geosolver" else witness_from_gmb_model(payload)
            )
            conversion_error = None
        except (CheckError, KeyError, TypeError, ValueError) as error:
            witness, conversion_error = None, str(error)
            issues.append(f"invalid_witness_record:{type(error).__name__}")
        conversion_seconds = time.perf_counter() - started
        for tolerance in self.tolerances:
            started = time.perf_counter()
            if text is None or conversion_error or issues:
                checked = {
                    "valid": False,
                    "status": "not_checked",
                    "goals_valid": None,
                    "code": "evidence_issue",
                    "assumptions": [],
                    "goals": [],
                }
            else:
                checked = check_configuration(text, witness, tolerance=tolerance, dps=self.dps)
            result[tolerance] = {
                "result": checked,
                "checker_seconds": time.perf_counter() - started,
                "failure_reasons": _failure_reasons(checked),
            }
        record = {
            "schema_version": VERSION,
            "identity": identity,
            "model": str(path.resolve()),
            "native_accepted": native,
            "emitted_seconds": emitted,
            "stage": payload.get("stage") if method == "geosolver" else "native_get_model",
            "within_deadline": _number(emitted) and emitted <= self.manifest["timeout_seconds"],
            "evidence_issues": sorted(set(issues)),
            "conversion_error": conversion_error,
            "conversion_seconds": conversion_seconds,
            "checks": result,
        }
        _put_json(output, record)
        return record

    def _threshold(self, models, tolerance, issues):
        native = [model for model in models if model["native_accepted"]]
        on_time = [model for model in native if model["within_deadline"]]
        eligible = [
            model
            for model in on_time
            if not model["evidence_issues"]
            and model["checks"][tolerance]["result"]["valid"] is True
        ]
        first = (
            min(eligible, key=lambda model: (model["emitted_seconds"], model["model"]))
            if eligible and not issues
            else None
        )
        if issues:
            outcome = "evidence_issue"
        elif first:
            outcome = "success"
        elif not models:
            outcome = "no_output"
        elif not native:
            outcome = "no_native_output"
        elif not on_time:
            outcome = "late_output_only"
        else:
            outcome = "no_valid_output"
        goals = first["checks"][tolerance]["result"] if first else None
        return {
            "success": first is not None,
            "outcome": outcome,
            "first_valid_model": first["model"] if first else None,
            "time_to_first_valid_seconds": first["emitted_seconds"] if first else None,
            "capped_time_seconds": first["emitted_seconds"]
            if first
            else self.manifest["timeout_seconds"],
            "common_status_counts": dict(
                sorted(
                    Counter(
                        model["checks"][tolerance]["result"]["status"] for model in on_time
                    ).items()
                )
            ),
            "failure_reasons": sorted(
                {
                    reason
                    for model in on_time
                    for reason in model["checks"][tolerance]["failure_reasons"]
                }
            ),
            "goals_valid": goals.get("goals_valid") if goals else None,
            "goal_clause_count": len(goals.get("goals", [])) if goals else 0,
            "goal_failure_reasons": _failure_reasons(goals, "goals") if goals else [],
        }

    def assess_run(self, entry, seed, method, text, case_issues):
        issues, models = list(case_issues), []
        run, child, artifact, events, process, request = {}, None, None, [], {}, {}
        directory, origin, termination = None, None, "unavailable"
        try:
            directory, seal, native, native_hash, origin = self._location(entry, seed, method)
            run, request, more = self._run_contract(
                directory, seal, native, native_hash, entry, seed, method
            )
            issues.extend(more)
            child = self._optional(seal, directory / "child-result.json")
            if method == "geosolver":
                artifact = self._optional(seal, directory / "worker-artifact.json")
                identity = None
            else:
                identity = self._optional(seal, directory / "identity.json")
            process = run.get("process", {})
            issues.extend(self._resources(process, child, artifact, identity))
            termination = self._termination(process, child, method)
            if run.get("outcome") != termination:
                issues.append("termination_outcome_mismatch")
            if not child and termination not in {
                "crash",
                "timeout",
                "cancelled",
                "resource_violation",
            }:
                issues.append("missing_terminal_child_result")
            if process.get("returncode") == 0 and not process.get("timed_out") and child is None:
                issues.append("zero_exit_without_terminal_artifact")
            events, more = self._events(seal, directory, process.get("wall_seconds"))
            issues.extend(more)
            observations = [event for event in events if event["event"] == "model_materialized"]
            names = []
            for event in observations:
                try:
                    path = _relative(directory, event["model"])
                    if path.parent != directory / "models" or path.suffix != ".json":
                        raise EvidenceError("unexpected_model_path")
                    if event["model"] in names:
                        raise EvidenceError("duplicate_model_emission")
                    names.append(event["model"])
                    model = self._check_model(path, seal, event, entry, seed, method, text)
                    models.append(model)
                    issues.extend(f"{event['model']}:{item}" for item in model["evidence_issues"])
                except (EvidenceError, OSError, KeyError, TypeError) as error:
                    issues.append(f"model_evidence:{error}")
            actual_models = {
                path.relative_to(directory).as_posix()
                for path in (directory / "models").glob("*.json")
                if path.is_file()
            }
            if actual_models != set(names):
                issues.append("model_files_and_events_mismatch")
            if child and child.get("model_files") != names:
                issues.append("child_model_files_and_events_mismatch")
            if method == "gmb":
                if names and identity is None:
                    issues.append("missing_gmb_runtime_identity")
                if child and child.get("outcome") in {"model_returned", "no_model"}:
                    if child.get("models_returned") != len(names):
                        issues.append("gmb_returned_model_count_mismatch")
                    if (child["outcome"] == "model_returned") != bool(names):
                        issues.append("gmb_native_outcome_model_count_mismatch")
            else:
                failures = [event for event in events if event["event"] == "materialization_error"]
                failures.extend((child or {}).get("materialization_failures", []))
                for failure in failures:
                    if unexpected_observation_failure(failure):
                        issues.append(f"observation_error:{failure.get('kind', 'missing_kind')}")
                expected_identity = self.manifest.get("engine_identity")
                for label, value in (("child", child), ("artifact", artifact)):
                    if value and label == "artifact":
                        actual_identity = value.get("execution_identity")
                        # The worker's ordinary exception path returns a failed
                        # artifact without identity/process_info. Parent/child
                        # still identify that run; absence here is not corruption.
                        if (
                            actual_identity or value.get("status") == "completed"
                        ) and actual_identity != expected_identity:
                            issues.append("artifact_engine_identity_mismatch")
                    if (
                        value
                        and label == "child"
                        and "engine_identity" in value
                        and value["engine_identity"] != expected_identity
                    ):
                        issues.append("child_engine_identity_mismatch")
                if child and child.get("outcome") == "completed":
                    if artifact is None:
                        issues.append("missing_geosolver_worker_artifact")
                    elif child.get("solver_status") != artifact.get("solver_status"):
                        issues.append("geosolver_terminal_status_mismatch")
        except (EvidenceError, OSError, KeyError, TypeError) as error:
            issues.append(str(error))
        issues = sorted(set(issues))
        thresholds = {
            tolerance: self._threshold(models, tolerance, issues) for tolerance in self.tolerances
        }
        primary = thresholds[self.primary_tolerance]
        completed = (
            not issues
            and process.get("returncode") == 0
            and not process.get("timed_out")
            and not process.get("cancelled")
            and bool(child)
        )
        if method == "gmb":
            native_success = (
                completed
                and child.get("outcome") == "model_returned"
                and child.get("models_returned", 0) > 0
            )
        else:
            native_success = completed and bool(
                artifact
                and artifact.get("status") == "completed"
                and artifact.get("solver_status") == "success"
                and artifact.get("public_solved") is True
            )
        return {
            "schema_version": VERSION,
            "case_id": entry["case_id"],
            "seed": seed,
            "method": method,
            "input_origin": entry.get("input_origin"),
            "run_origin": origin,
            "run_directory": str(directory) if directory else None,
            "original_assumptions_covered": entry.get("original_assumptions_covered") is True,
            "primary_tolerance": self.primary_tolerance,
            **primary,
            "thresholds": thresholds,
            "evidence_issues": issues,
            "termination_outcome": termination,
            "recorded_termination_outcome": run.get("outcome"),
            "termination_reason": (child or {}).get(
                "termination_reason", (artifact or {}).get("termination_reason")
            ),
            "native_completed_success": bool(native_success),
            "native_emitted_output": any(model["native_accepted"] for model in models),
            "native_emitted_within_deadline": any(
                model["native_accepted"] and model["within_deadline"] for model in models
            ),
            "output_count": len(models),
            "native_output_count": sum(model["native_accepted"] for model in models),
            "late_native_output_count": sum(
                model["native_accepted"] and not model["within_deadline"] for model in models
            ),
            "wall_seconds": process.get("wall_seconds"),
            "cpu_seconds": process.get("cpu_seconds"),
            "cpu_user_seconds": process.get("cpu_user_seconds"),
            "cpu_system_seconds": process.get("cpu_system_seconds"),
            "peak_rss_bytes": process.get("peak_rss_bytes"),
            "returncode": process.get("returncode"),
            "timed_out": process.get("timed_out"),
            "cancelled": process.get("cancelled"),
            "affinity_masks_observed": process.get("affinity_masks_observed"),
            "affinity_violations": process.get("affinity_violations"),
            "phase_timings": (artifact or {}).get("phase_timings", {}),
            "counters": (artifact or {}).get("counters", {}),
            "event_timings": event_timings(events),
            "last_event": events[-1]["event"] if events else None,
            "failure_stage": (child or {}).get("failure_stage"),
            "worker_error": (artifact or {}).get("error")
            or {key: child[key] for key in ("exception", "message") if child and key in child}
            or None,
            "observation_failures": [
                {key: value for key, value in event.items() if key != "candidate"}
                for event in events
                if event["event"] == "materialization_error"
            ],
            "checker_seconds": sum(
                item["checker_seconds"] for model in models for item in model["checks"].values()
            ),
            "witness_conversion_seconds": sum(model["conversion_seconds"] for model in models),
            "model_check_files": [
                f"models/{method}/{entry['case_id']}/{seed}/{Path(model['model']).name}"
                for model in models
            ],
        }

    def run(self):
        rows = []
        for entry in sorted(self.manifest["entries"], key=lambda item: item["case_id"]):
            text, issues = self._case(entry)
            for seed in self.manifest["seeds"]:
                for method in METHODS:
                    rows.append(self.assess_run(entry, seed, method, text, issues))
        for seal in (self.raw, *(value[0] for value in self.legacy.values())):
            seal.recheck()
        summary = summarize(rows, self.manifest)
        summary.update(
            manifest_sha256=self.manifest_hash,
            raw_sha256sums_sha256=self.raw.digest,
            checker_identity=self.identity,
            raw_files_verified=len(self.raw.verified),
            legacy_files_verified=sum(len(value[0].verified) for value in self.legacy.values()),
        )
        _put(self.output / "run-results.jsonl", "".join(_json(row) + "\n" for row in rows))
        _put(self.output / "run-results.csv", rows_csv(rows))
        _put_json(self.output / "summary.json", summary)
        _put(self.output / "REPORT.md", japanese_report(summary))
        paths = sorted(
            path for path in self.output.rglob("*") if path.is_file() and path.name != "SHA256SUMS"
        )
        _put(
            self.output / "SHA256SUMS",
            "".join(
                f"{sha256(path)}  {path.relative_to(self.output).as_posix()}\n" for path in paths
            ),
        )
        return summary


def event_timings(events):
    """Unfinished phases stay unfinished; no endpoint is invented at timeout."""
    stacks, durations, counts = {}, Counter(), Counter()
    for event in events:
        name, elapsed = event["event"], event.get("elapsed_seconds")
        if not _number(elapsed):
            continue
        if name.endswith("_start"):
            stacks.setdefault(name[:-6], []).append(elapsed)
        elif name.endswith(("_end", "_error")):
            phase = name.rsplit("_", 1)[0]
            if stacks.get(phase):
                started = stacks[phase].pop()
                if elapsed >= started:
                    durations[phase] += elapsed - started
                    counts[phase] += 1
    return {
        phase: {
            "completed_seconds": durations[phase] if counts[phase] else None,
            "completed_calls": counts[phase],
            "incomplete_calls": len(stacks.get(phase, [])),
        }
        for phase in sorted(stacks.keys() | counts.keys())
    }


def distribution(values):
    values = [value for value in values if _number(value)]
    return {
        "n": len(values),
        "mean": statistics.mean(values) if values else None,
        "median": statistics.median(values) if values else None,
        "min": min(values) if values else None,
        "max": max(values) if values else None,
        "sum": math.fsum(values),
    }


def _aggregate(rows, tolerance):
    metrics = [row["thresholds"][tolerance] for row in rows]
    successes = sum(metric["success"] for metric in metrics)
    return {
        "planned_runs": len(rows),
        "success_runs": successes,
        "success_rate": successes / len(rows) if rows else None,
        "evidence_issue_runs": sum(bool(row["evidence_issues"]) for row in rows),
        "outcome_counts": dict(sorted(Counter(metric["outcome"] for metric in metrics).items())),
        "capped_time_seconds": distribution([metric["capped_time_seconds"] for metric in metrics]),
        "successful_time_seconds_descriptive_only": distribution(
            [metric["time_to_first_valid_seconds"] for metric in metrics if metric["success"]]
        ),
        "first_valid_goal_evaluable_runs": sum(
            metric["goals_valid"] is not None for metric in metrics
        ),
        "first_valid_all_goals_passed_runs": sum(
            metric["goals_valid"] is True for metric in metrics
        ),
        "failure_reason_run_counts": dict(
            sorted(
                Counter(
                    reason for metric in metrics for reason in set(metric["failure_reasons"])
                ).items()
            )
        ),
    }


def summarize(rows, manifest):
    seeds = manifest["seeds"]
    primary = manifest["protocol"]["common_tolerance"]
    tolerances = manifest["protocol"]["sensitivity_tolerances"]
    case_ids = sorted(entry["case_id"] for entry in manifest["entries"])
    by_method = {}
    for method in METHODS:
        selected = [row for row in rows if row["method"] == method]
        histogram = Counter(
            sum(row["success"] for row in selected if row["case_id"] == case) for case in case_ids
        )
        by_method[method] = {
            "primary": _aggregate(selected, primary),
            "by_tolerance": {
                tolerance: _aggregate(selected, tolerance) for tolerance in tolerances
            },
            "by_seed": {
                str(seed): _aggregate([row for row in selected if row["seed"] == seed], primary)
                for seed in seeds
            },
            "case_success_count_distribution": {
                str(count): histogram[count] for count in range(len(seeds) + 1)
            },
            "cases_succeeded_at_least_once": len(case_ids) - histogram[0],
            "cases_succeeded_all_seeds": histogram[len(seeds)],
            "native_completed_success_runs": sum(
                row["native_completed_success"] for row in selected
            ),
            "native_emitted_within_deadline_runs": sum(
                row["native_emitted_within_deadline"] for row in selected
            ),
            "termination_outcome_counts": dict(
                sorted(Counter(row["termination_outcome"] for row in selected).items())
            ),
            "run_origin_counts": dict(
                sorted(Counter(row["run_origin"] or "unavailable" for row in selected).items())
            ),
            "resources": {
                key: distribution([row[key] for row in selected])
                for key in ("wall_seconds", "cpu_seconds", "peak_rss_bytes", "checker_seconds")
            },
            "evidence_issue_run_counts": dict(
                sorted(
                    Counter(
                        issue for row in selected for issue in set(row["evidence_issues"])
                    ).items()
                )
            ),
        }
    by_case = []
    for case in case_ids:
        item = {"case_id": case}
        for method in METHODS:
            selected = sorted(
                [row for row in rows if row["case_id"] == case and row["method"] == method],
                key=lambda row: row["seed"],
            )
            item[method] = {
                "successes": sum(row["success"] for row in selected),
                "seeds": {
                    str(row["seed"]): {
                        key: row[key]
                        for key in (
                            "success",
                            "outcome",
                            "time_to_first_valid_seconds",
                            "termination_outcome",
                            "evidence_issues",
                        )
                    }
                    for row in selected
                },
            }
        by_case.append(item)
    return {
        "schema_version": VERSION,
        "study": manifest.get("study"),
        "input_profile": manifest.get("input_profile"),
        "case_count": len(case_ids),
        "seeds": seeds,
        "planned_runs_per_method": len(case_ids) * len(seeds),
        "total_run_rows": len(rows),
        "cpu": manifest["cpu"],
        "cores_per_run": 1,
        "timeout_seconds": manifest["timeout_seconds"],
        "primary_tolerance": primary,
        "checker_dps": manifest["protocol"]["checker_dps"],
        "by_method": by_method,
        "by_case": by_case,
        "complete_evidence": not any(row["evidence_issues"] for row in rows),
        "scope_exceptions": manifest["protocol"].get("common_scope_exceptions", {}),
        "input_origin_counts": dict(
            sorted(
                Counter(
                    entry.get("input_origin", "unspecified") for entry in manifest["entries"]
                ).items()
            )
        ),
        "resource_scope": {
            "exclusive_cpu": manifest.get("host", {}).get("exclusive_core", False),
            "concurrent_paired_or_abba_measurement": False,
            "three_seed_inference": (
                "descriptive only; no population-rate or speed-superiority proof"
            ),
        },
        "timing_policy": (
            "first native-accepted model atomically emitted within limit and passing the "
            "offline checker; timeout/crash later is a separate outcome"
        ),
        "censoring_policy": (
            "all planned trials remain in denominator; no qualifying success "
            "(including evidence issues) is capped at timeout, never zero"
        ),
        "interpretation": (
            "numerical configuration validation only; neither existence proof, theorem proof, "
            "enumeration completeness nor a literal replication of all 39 paper instances"
        ),
        "sensitivity_warning": (
            "tolerances affect both equality error and boundary/branch resolution; "
            "success sets need not be nested"
        ),
    }


def rows_csv(rows):
    leading = ["case_id", "seed", "method", "success", "outcome", "time_to_first_valid_seconds"]
    fields = leading + sorted({key for row in rows for key in row} - set(leading))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                key: _json(value) if isinstance(value, dict | list) else value
                for key, value in row.items()
            }
        )
    return stream.getvalue()


def japanese_report(summary):
    def number(value):
        return f"{value:.3f}" if value is not None else "—"

    methods = summary["by_method"]
    count, denominator = summary["case_count"], summary["planned_runs_per_method"]
    lines = [
        "# GMB・GeoSolver：配置生成の共通基準比較",
        "",
        f"対象 {count} 問、seed {', '.join(map(str, summary['seeds']))}。"
        f"各手法 {denominator} 試行。",
        f"1 試行 {summary['timeout_seconds']} 秒、論理 CPU {summary['cpu']} の 1 コアに固定。"
        f"共通閾値 `{summary['primary_tolerance']}`、検査精度 {summary['checker_dps']} 桁。",
        "",
        "原文条件への対応が承認された入力を使用し、両手法が自ら受理して期限内にファイルへ出力した配置を、同じ独立検査器で検査した。",
        "最初の有効出力の時刻を採用し、その後の timeout / crash は終了状態として別記する。"
        "内部の未受理候補や期限後の出力は成功に含めない。",
        "",
        "| 手法 | 共通検査成功 / 全試行 | 成功率 | 1 回以上成功した問題 "
        "| 全 seed 成功した問題 | 証跡不整合 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for method in METHODS:
        value, metric = methods[method], methods[method]["primary"]
        lines.append(
            f"| {method} | {metric['success_runs']} / {denominator} "
            f"| {metric['success_rate']:.1%} | {value['cases_succeeded_at_least_once']} / {count} "
            f"| {value['cases_succeeded_all_seeds']} / {count} "
            f"| {metric['evidence_issue_runs']} |"
        )
    lines += [
        "",
        "## 時間・資源",
        "",
        "成功しなかった試行（証跡不整合を含む）は制限時間で打ち切った値として平均する。成功例だけの時間平均による速度優位は主張しない。",
        "入力読込み・import・観測・出力保存を含む時刻であり、終了までの wall time と区別する。"
        "オフライン検査時間は探索時間に加算していない。",
        "",
        "| 手法 | 打切り込み平均時間（秒） | 成功例時間中央値（参考・秒） "
        "| 全実行 CPU 時間合計（秒） | 最大 RSS（MiB） | 検査時間合計（秒） |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for method in METHODS:
        value = methods[method]
        resources, metric = value["resources"], value["primary"]
        rss = resources["peak_rss_bytes"]["max"]
        lines.append(
            f"| {method} | {number(metric['capped_time_seconds']['mean'])} "
            f"| {number(metric['successful_time_seconds_descriptive_only']['median'])} "
            f"| {number(resources['cpu_seconds']['sum'])} "
            f"| {number(rss / 1024**2 if rss is not None else None)} "
            f"| {number(resources['checker_seconds']['sum'])} |"
        )
    lines += [
        "",
        "## 閾値別の確認",
        "",
        "等式の許容誤差だけでなく、境界や枝の識別余裕にも閾値を使うため、成功集合が閾値の大小順に包含されるとは限らない。",
        "",
        "| 閾値 | GMB 成功 / 全試行 | GeoSolver 成功 / 全試行 |",
        "|---|---:|---:|",
    ]
    for tolerance in methods["gmb"]["by_tolerance"]:
        counts = [methods[method]["by_tolerance"][tolerance]["success_runs"] for method in METHODS]
        lines.append(
            f"| `{tolerance}` | {counts[0]} / {denominator} | {counts[1]} / {denominator} |"
        )
    lines += ["", "## 問題別の成功回数", "", "| 問題 | GMB | GeoSolver |", "|---|---:|---:|"]
    for item in summary["by_case"]:
        lines.append(
            f"| {item['case_id']} | {item['gmb']['successes']} / {len(summary['seeds'])} "
            f"| {item['geosolver']['successes']} / {len(summary['seeds'])} |"
        )
    lines += ["", "## 終了状態と証跡の限界", ""]
    for method in METHODS:
        value = methods[method]
        lines.append(
            f"- {method}：正常終了した native 成功 {value['native_completed_success_runs']} 試行。"
            f"終了状態 `{_json(value['termination_outcome_counts'])}`。"
        )
        lines.append(
            f"- {method}：成功回数 0〜{len(summary['seeds'])} 回の問題分布 "
            f"`{_json(value['case_success_count_distribution'])}`。"
        )
        if value["evidence_issue_run_counts"]:
            lines.append(
                f"- {method} の証跡不整合：`{_json(value['evidence_issue_run_counts'])}`。"
                "これらを solver の数学的失敗とは断定しない。"
            )
    if not summary["complete_evidence"]:
        lines += [
            "",
            "証跡不整合があるため、この表は全試行の確定した性能比較ではない。不整合の試行は分母から除外せず、成功を認めていない。",
        ]
    lines += [
        "",
        "結論（eval）は最初の共通有効配置に対する診断だけで、成功判定・探索・配置選択には使っていない。数値検査は厳密な存在証明や定理証明ではなく、全解の網羅性も評価していない。",
        "この比較は取得可能な対象入力についての原文整合比較であり、入力を補正したケースを含む。"
        "GMB 論文の全 39 問に対するそのままの追試とは区別する。",
    ]
    origins = summary["input_origin_counts"]
    reused = methods["gmb"]["run_origin_counts"].get("reused_official", 0)
    new_gmb = methods["gmb"]["run_origin_counts"].get("new_aligned", 0)
    lines += [
        "",
        f"入力の内訳：`{_json(origins)}`。GMB は既存 raw {reused} 試行を再利用し、"
        f"補正版を {new_gmb} 試行新規測定した。"
        "旧 raw の入力ハッシュも選択した比較入力と照合している。",
        "両手法を同時刻に交互実行した ABBA 比較ではなく、CPU 固定も専有を意味しない。"
        "背景負荷や測定時期の差があり、3 seed の結果は記述的比較として扱う。",
    ]
    if summary["scope_exceptions"]:
        lines += ["", "事前に合意した対象範囲の留保：", ""]
        lines.extend(
            f"- `{case}`：{note}" for case, note in sorted(summary["scope_exceptions"].items())
        )
    lines += [
        "",
        "詳細は `run-results.jsonl` / `run-results.csv`（試行ごと）、"
        "`models/`（全閾値・全条件の検査）、`summary.json` を参照。"
        "元 raw は変更していない。`SHA256SUMS` で本集計を固定している。",
        "",
    ]
    return "\n".join(lines)


def assess_campaign(directory):
    """Assess a sealed campaign, or reproduce its already-sealed assessment."""
    return Assessment(directory).run()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", required=True, type=Path)
    args = parser.parse_args()
    summary = assess_campaign(args.campaign)
    print(
        _json(
            {
                "assessment": str(args.campaign.resolve() / "assessment"),
                "total_run_rows": summary["total_run_rows"],
                "complete_evidence": summary["complete_evidence"],
            },
            pretty=True,
        )
    )
    return 0 if summary["complete_evidence"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
