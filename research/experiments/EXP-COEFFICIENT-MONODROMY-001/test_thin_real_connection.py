from __future__ import annotations

from pathlib import Path

from run_thin_connection_smoke import run

COMMON_CONTROL = Path("/home/kabatan/work/solver-experiment-runtime/solver")


def test_generated_source_only_connection_gate() -> None:
    result = run(COMMON_CONTROL)
    assert result["gate"]["passed"] is True
    assert result["aggregate"]["descriptor_losses"] == 0
    assert result["aggregate"]["false_or_extra"] == 0
    assert result["aggregate"]["payload_mismatch"] == 0
