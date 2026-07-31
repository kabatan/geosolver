#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from prototype import run_all


HERE = Path(__file__).resolve().parent


def main() -> int:
    result = run_all()
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    output = HERE / "D0_RESULT.json"
    output.write_text(payload, encoding="utf-8")
    digest = hashlib.sha256(payload.encode()).hexdigest()
    print(json.dumps({"gate_pass": result["aggregate"]["gate_pass"], "sha256": digest}))
    return 0 if result["aggregate"]["gate_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
