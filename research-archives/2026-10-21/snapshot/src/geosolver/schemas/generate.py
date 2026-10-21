"""Generate checked-in public JSON schemas from the Pydantic models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from geosolver.problem.models import GeometryProblem, SolveResult

_SCHEMA_DIRECTORY = Path(__file__).resolve().parent
_SCHEMAS = {
    "geometry-problem.schema.json": (
        GeometryProblem,
        "https://geosolver.local/schemas/geometry-problem.schema.json",
    ),
    "solve-result.schema.json": (
        SolveResult,
        "https://geosolver.local/schemas/solve-result.schema.json",
    ),
}


def _render(model: object, schema_id: str) -> str:
    schema = model.model_json_schema(mode="validation")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = schema_id
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def generate(*, check: bool) -> int:
    """Write schemas, or return nonzero if checked-in files are stale."""
    stale: list[str] = []
    for filename, (model, schema_id) in _SCHEMAS.items():
        expected = _render(model, schema_id)
        path = _SCHEMA_DIRECTORY / filename
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != expected:
                stale.append(filename)
            continue
        path.write_text(expected, encoding="utf-8")
    if stale:
        print("stale generated schemas: " + ", ".join(stale))
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    return generate(check=bool(args.check))


if __name__ == "__main__":
    raise SystemExit(main())
