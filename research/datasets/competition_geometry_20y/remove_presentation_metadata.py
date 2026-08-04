#!/usr/bin/env python3
"""Remove contest answer-formatting metadata from DSL records."""
from __future__ import annotations

import re
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main() -> None:
    changed = 0
    for path in sorted((ROOT / "dsl").glob("*.json")):
        text = path.read_text(encoding="utf-8")
        # Clause-ledger prose may mention the old implementation detail.  It
        # is metadata only, but use neutral wording so no DSL record suggests
        # that a contest-format value is still emitted or judged.
        if '"post_process"' not in text and "post_process" not in text and "post-process" not in text and "postprocess" not in text:
            continue
        # Every generated record stores this metadata as the final JSON
        # member.  Remove its leading comma as well so the result remains
        # valid JSON, while all other source-faithful text stays unchanged.
        updated = re.sub(
            r",\n(\s*)\"post_process\"\s*:\s*[^\n]+\n(\s*)\}",
            r"\n\2}",
            text,
            flags=re.MULTILINE,
        )
        updated = updated.replace("post_process", "contest presentation")
        updated = updated.replace("post-process", "contest presentation")
        updated = updated.replace("postprocess", "contest presentation")
        path.write_text(updated, encoding="utf-8")
        changed += 1
    print(json.dumps({"updated_records": changed}, ensure_ascii=False))


if __name__ == "__main__":
    main()
