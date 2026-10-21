"""Freeze a diverse second collection arm without answer or theorem feedback."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SELECTED = [
    "H07", "H13", "DA04", "DA15", "H03", "H08", "H15", "DA02",
    "DA03", "DA07", "DA08", "DB01", "DB06", "DB08", "DB10", "DB16",
]


def main():
    originals = json.loads((HERE / "material-original-jobs-en.json").read_text())
    by_config = {row["source_id"]: row for row in originals}
    assert len(SELECTED) == len(set(SELECTED)) == 16
    jobs = []
    for config in SELECTED:
        source = by_config[config]
        ident = f"diverse-en-fresh-thinking-{config}-v0-0"
        seed = int.from_bytes(hashlib.sha256(ident.encode()).digest()[:4], "big") % (2**31)
        jobs.append(source | {"id": ident, "seed": seed, "augmentation": "fresh_thinking"})
    output = HERE / "material-fresh-thinking-jobs-en.json"
    output.write_text(json.dumps(jobs, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"jobs": len(jobs), "configs": SELECTED,
                      "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
