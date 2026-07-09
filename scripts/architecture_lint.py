"""Fail fast when production boundaries acquire forbidden coupling.

This is intentionally conservative and dependency-free. Semantic architecture
tests supplement it as the implementation grows.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JULIA = ROOT / "julia"


def source_files(path: Path) -> list[Path]:
    return sorted([*path.rglob("*.jl"), *path.rglob("*.py")])


def dependency_errors() -> list[str]:
    projects = {
        "GeoTargetBase": JULIA / "GeoTargetBase" / "Project.toml",
        "GeoTargetCore": JULIA / "GeoTargetCore" / "Project.toml",
        "GeoTargetGeometry": JULIA / "GeoTargetGeometry" / "Project.toml",
    }
    deps: dict[str, set[str]] = {}
    for name, project in projects.items():
        data = tomllib.loads(project.read_text(encoding="utf-8"))
        deps[name] = set(data.get("deps", {})) & projects.keys()

    errors: list[str] = []
    if "GeoTargetGeometry" in deps["GeoTargetCore"]:
        errors.append("GeoTargetCore must not depend on GeoTargetGeometry")
    if deps["GeoTargetBase"]:
        errors.append(f"GeoTargetBase must not depend on sibling packages: {deps['GeoTargetBase']}")
    if deps["GeoTargetGeometry"] - {"GeoTargetBase"}:
        errors.append("GeoTargetGeometry may depend only on GeoTargetBase")
    return errors


def source_errors() -> list[str]:
    errors: list[str] = []
    production = [
        JULIA / "GeoTargetBase" / "src",
        JULIA / "GeoTargetCore" / "src",
        JULIA / "GeoTargetGeometry" / "src",
        ROOT / "python" / "src",
    ]
    dynamic_patterns = {
        "dynamic eval": re.compile(r"(?<![A-Za-z_])(eval|exec)\s*\(|@eval\b|Core\.eval|Meta\.parse"),
        "bare Python except": re.compile(r"^\s*except\s*:\s*$", re.MULTILINE),
        "case-specific routing": re.compile(
            r"\b(case_id|problem_name|known_answer|magic_target|answer_table)\b",
            re.IGNORECASE,
        ),
        "legacy runtime path": re.compile(r"OneDrive.*geosolver|geosolver_repro", re.IGNORECASE),
    }
    for directory in production:
        for path in source_files(directory):
            text = path.read_text(encoding="utf-8")
            relative = path.relative_to(ROOT)
            for label, pattern in dynamic_patterns.items():
                if pattern.search(text):
                    errors.append(f"{relative}: forbidden {label}")

    core_dir = JULIA / "GeoTargetCore" / "src"
    geometry_names = re.compile(
        r"\b(Point2|Line2|Circle2|OrientedArc|Intersect|Circumcircle)\b"
    )
    for path in source_files(core_dir):
        text = path.read_text(encoding="utf-8")
        if "GeoTargetGeometry" in text or geometry_names.search(text):
            errors.append(f"{path.relative_to(ROOT)}: Core contains geometry-specific names")

    combined_core = "\n".join(
        path.read_text(encoding="utf-8") for path in source_files(core_dir)
    )
    for unique_type in ("CandidateStore", "EvidenceLog", "VerificationPipeline"):
        declarations = len(re.findall(rf"\b(struct|mutable struct)\s+{unique_type}\b", combined_core))
        if declarations > 1:
            errors.append(f"GeoTargetCore declares {unique_type} {declarations} times")
    return errors


def main() -> int:
    errors = dependency_errors() + source_errors()
    if errors:
        for error in errors:
            print(f"architecture-lint: {error}", file=sys.stderr)
        return 1
    print("architecture-lint: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

