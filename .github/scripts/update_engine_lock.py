"""Regenerate the checked-in single-engine identity lock."""

from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path

from geosolver.runtime.integrity import expected_engine_lock

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    lock_bytes = (ROOT / "uv.lock").read_bytes()
    packages = tomllib.loads(lock_bytes.decode("utf-8"))["package"]
    dependencies = {
        "uv_lock_sha256": hashlib.sha256(lock_bytes).hexdigest(),
        "packages": {
            entry["name"]: entry["version"]
            for entry in packages
            if "version" in entry and entry["name"] != "geosolver"
        },
    }
    (ROOT / "src/geosolver/dependency-lock.json").write_text(
        json.dumps(dependencies, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    target = ROOT / "src" / "geosolver" / "engine-lock.json"
    target.write_text(
        json.dumps(expected_engine_lock(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
