from __future__ import annotations

import json
from pathlib import Path

import pytest
from mpmath import mp


@pytest.fixture(autouse=True)
def isolate_mpmath_context():
    """Keep frozen evaluator precision changes local to the invoking test.

    Some frozen low-level fault paths raise after increasing ``mp.dps``.  The
    product runtime calls those paths through its precision-isolation seam,
    while differential tests deliberately invoke the underlying evaluator
    directly.  Restore the process-global context at every test boundary so
    collection order cannot change intersection tolerances or branch choices.
    """

    original_dps = int(mp.dps)
    original_trap_complex = bool(mp.trap_complex)
    original_pretty = bool(mp.pretty)
    try:
        yield
    finally:
        mp.dps = original_dps
        mp.trap_complex = original_trap_complex
        mp.pretty = original_pretty


@pytest.fixture
def problem() -> dict:
    path = Path(__file__).resolve().parents[1] / "examples/problem.json"
    return json.loads(path.read_text(encoding="utf-8"))
