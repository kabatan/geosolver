"""Join frozen manual grades to a condition mapping and summarize paired scores."""

import argparse
import json
from collections import defaultdict
from pathlib import Path


FIELDS = ("exact", "relation", "proof", "use")
GROUPS = {
    "projection_cluster": ("H03", "H04", "H14"),
    "H08": ("H08",),
    "H15": ("H15",),
    "near_transfer_all": ("H03", "H04", "H08", "H14", "H15"),
    "retention": ("H01", "H02", "H07", "H13"),
    "all_nine": ("H01", "H02", "H03", "H04", "H07", "H08", "H13", "H14", "H15"),
}


def load(path: Path):
    return json.loads(path.read_text())


def write(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--grade", type=Path, action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    packet = load(args.packet)
    mapping = load(args.mapping)
    assert len(packet) == len(mapping) == 36
    packets = {r["blind_id"]: r for r in packet}
    maps = {r["blind_id"]: r for r in mapping}
    assert len(packets) == len(maps) == 36 and packets.keys() == maps.keys()

    grades = {}
    for path in args.grade:
        rows = load(path)
        if isinstance(rows, dict):
            rows = rows["grades"]
        for row in rows:
            blind_id = row["blind_id"]
            assert blind_id in packets and blind_id not in grades
            assert all(type(row[k]) is bool for k in FIELDS), (path, blind_id)
            assert type(row["uncertain"]) is bool and not row["uncertain"], (path, blind_id)
            assert isinstance(row["note"], str) and row["note"].strip()
            assert row.get("source_id", packets[blind_id]["source_id"]) == packets[blind_id]["source_id"]
            grades[blind_id] = row
    assert grades.keys() == packets.keys(), sorted(packets.keys() - grades.keys())

    joined = []
    for blind_id, packet_row in packets.items():
        grade = grades[blind_id]
        row = {"blind_id": blind_id, "source_id": packet_row["source_id"],
               "condition": maps[blind_id]["condition"], "job_id": maps[blind_id]["job_id"],
               "finish_reason": packet_row["finish_reason"],
               **{k: grade[k] for k in FIELDS}, "note": grade["note"]}
        row["complete"] = all(row[k] for k in FIELDS)
        joined.append(row)
    conditions = sorted({r["condition"] for r in joined})
    assert len(conditions) == 4
    by_pair = defaultdict(dict)
    for row in joined:
        source, condition = row["source_id"], row["condition"]
        assert condition not in by_pair[source]
        by_pair[source][condition] = row
    assert set(by_pair) == set(GROUPS["all_nine"])
    assert all(set(v) == set(conditions) for v in by_pair.values())

    counts = {}
    for group, sources in GROUPS.items():
        counts[group] = {condition: {field: sum(by_pair[source][condition][field] for source in sources)
                                     for field in (*FIELDS, "complete")}
                         for condition in conditions}
    args.out.mkdir(parents=True, exist_ok=False)
    write(args.out / "joined-grades.json", sorted(joined, key=lambda r: (r["source_id"], r["condition"])))
    write(args.out / "counts.json", counts)
    write(args.out / "item-pairs.json", {source: by_pair[source] for source in sorted(by_pair)})
    print(json.dumps({"conditions": conditions, "complete": {g: {c: v["complete"] for c, v in a.items()}
                                                         for g, a in counts.items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
