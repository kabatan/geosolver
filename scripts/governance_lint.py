"""Minimal consistency checks for project contracts and ADR links."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "REQUIREMENTS.md"
TRACEABILITY = ROOT / "TRACEABILITY.md"
ADR_INDEX = ROOT / "docs" / "adr" / "README.md"

REQUIREMENT_ID = re.compile(r"\| ((?:GOAL|DSL|ANS|ARCH|RES|QA)-\d{2}) \|")
ADR_LINK = re.compile(r"\((\d{4}-[^)]+\.md)\)")


def main() -> int:
    errors: list[str] = []
    requirements_text = REQUIREMENTS.read_text(encoding="utf-8")
    requirement_ids = REQUIREMENT_ID.findall(requirements_text)
    if len(requirement_ids) != len(set(requirement_ids)):
        errors.append("duplicate requirement ID")

    traceability_text = TRACEABILITY.read_text(encoding="utf-8")
    for prefix in ("GOAL", "DSL", "ANS", "ARCH", "RES", "QA"):
        if prefix not in traceability_text:
            errors.append(f"traceability omits requirement group {prefix}")

    index_text = ADR_INDEX.read_text(encoding="utf-8")
    for relative in ADR_LINK.findall(index_text):
        if not (ADR_INDEX.parent / relative).is_file():
            errors.append(f"ADR index points to missing file {relative}")

    if errors:
        for error in errors:
            print(f"governance-lint: {error}", file=sys.stderr)
        return 1
    print(f"governance-lint: OK ({len(requirement_ids)} requirements)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

