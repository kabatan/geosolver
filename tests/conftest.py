from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def problem() -> dict:
    path = Path(__file__).resolve().parents[1] / "examples/problem.json"
    return json.loads(path.read_text(encoding="utf-8"))
