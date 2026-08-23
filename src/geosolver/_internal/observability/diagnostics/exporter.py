"""Diagnostics export helpers."""

import json
from dataclasses import asdict

from .types import SolverDiagnostics


def diagnostics_to_dict(diagnostics: SolverDiagnostics) -> dict[str, object]:
    return asdict(diagnostics)


def diagnostics_to_json(diagnostics: SolverDiagnostics) -> str:
    return json.dumps(diagnostics_to_dict(diagnostics), ensure_ascii=False, sort_keys=True)
