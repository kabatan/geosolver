from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import psutil

from geotarget.engine import ENGINE_HASH, ENGINE_ID, julia_project_root, verify_engine
from geotarget.native_kernel import native_capability
from geotarget.qualification import policy
from geotarget.resources import physical_cpu_ids


def diagnose() -> dict[str, Any]:
    errors = verify_engine()
    warnings: list[str] = []
    python_ok = sys.version_info[:2] == (3, 12)
    if not python_ok:
        errors.append(f"Python 3.12 required; running {sys.version.split()[0]}")
    julia = shutil.which("julia")
    julia_version = None
    if julia:
        completed = subprocess.run(
            [julia, "--version"], text=True, capture_output=True, timeout=10, check=False
        )
        julia_version = completed.stdout.strip()
        if "1.12.6" not in julia_version:
            errors.append(f"Julia 1.12.6 required; found {julia_version or 'unknown'}")
    else:
        errors.append("Julia executable not found")
    manifest = julia_project_root() / "Manifest.toml"
    nemo_ok = manifest.is_file() and 'version = "0.56.1"' in manifest.read_text(encoding="utf-8")
    if not nemo_ok:
        errors.append("locked Nemo 0.56.1 manifest not found")
    cpus = physical_cpu_ids()
    compatible = [cpu for cpu in cpus if cpu < 16]
    if not compatible:
        errors.append("no affinity-compatible physical core in [0,15]")
    memory = psutil.virtual_memory().available
    if memory < 1_500_000_000:
        errors.append("less than 1.5 GB memory available")
    if len(cpus) > len(compatible):
        warnings.append("only physical CPUs in [0,15] are compatible with the frozen worker")
    launcher = Path(__file__).resolve().parent / "_engine/runtime/solver/python/.venv/bin/python"
    if not launcher.is_file() or not os.access(launcher, os.X_OK):
        errors.append("frozen subprocess Python launcher is missing or not executable")
    native = {key: value for key, value in native_capability().items() if key != "module"}
    return {
        "ok": not errors,
        "engine_id": ENGINE_ID,
        "engine_hash": ENGINE_HASH,
        "python": sys.version.split()[0],
        "julia": julia_version,
        "nemo_locked": nemo_ok,
        "physical_cpu_ids": list(cpus),
        "compatible_cpu_ids": compatible,
        "available_memory_bytes": memory,
        "errors": errors,
        "warnings": warnings,
        "native_kernel": native,
        "optimized_qualification": policy(),
    }


def formatted_report() -> str:
    return json.dumps(diagnose(), ensure_ascii=False, indent=2)
