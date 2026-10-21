"""Divide a condition-blind geometry scoring packet by source group."""

import argparse
import hashlib
import json
from pathlib import Path


GROUPS = {
    "projection": {"H03", "H04", "H14"},
    "tangent_reflection": {"H08", "H15"},
    "retention_a": {"H01", "H02"},
    "retention_b": {"H07", "H13"},
}


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    args = parser.parse_args()
    packet = json.loads(args.packet.read_text())
    assert len(packet) == 36
    assert len({row["blind_id"] for row in packet}) == len(packet)
    assert {row["source_id"] for row in packet} == set().union(*GROUPS.values())
    assert all({"blind_id", "source_id", "problem", "final_text", "finish_reason"} <= set(row) for row in packet)
    folder = args.packet.parent
    for name, sources in GROUPS.items():
        group = [row for row in packet if row["source_id"] in sources]
        assert len(group) == 4 * len(sources), (name, len(group))
        write(folder / f"blind-{name}.json", group)
        print(name, len(group), hashlib.sha256((folder / f"blind-{name}.json").read_bytes()).hexdigest())
    for source in sorted({row["source_id"] for row in packet}):
        group = [row for row in packet if row["source_id"] == source]
        assert len(group) == 4
        write(folder / f"blind-{source}.json", group)


if __name__ == "__main__":
    main()
