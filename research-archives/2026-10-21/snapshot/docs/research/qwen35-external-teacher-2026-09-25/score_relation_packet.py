"""Join frozen blind relation-only grades to conditions and summarize by source."""

import argparse
import json
from collections import defaultdict
from pathlib import Path


FIELDS = ("relation", "branch", "reason", "instruction")
GROUPS = {
    "projection_cluster": ("H03", "H04", "H14"),
    "H08": ("H08",),
    "H15": ("H15",),
    "near_transfer_all": ("H03", "H04", "H08", "H14", "H15"),
    "retention": ("H01", "H02", "H07", "H13"),
}


def load(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--grade", type=Path, action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    packet = {x["blind_id"]: x for x in load(args.packet)}
    mapping = {x["blind_id"]: x for x in load(args.mapping)}
    assert len(packet) == len(mapping) == 36 and packet.keys() == mapping.keys()
    grades = {}
    for path in args.grade:
        rows = load(path)
        if isinstance(rows, dict):
            rows = rows["grades"]
        for row in rows:
            bid = row["blind_id"]
            assert bid in packet and bid not in grades
            assert row["source_id"] == packet[bid]["source_id"]
            assert all(type(row[k]) is bool for k in FIELDS)
            assert row["uncertain"] is False
            assert isinstance(row["note"], str) and row["note"].strip()
            grades[bid] = row
    assert grades.keys() == packet.keys(), sorted(packet.keys() - grades.keys())

    paired = defaultdict(dict)
    joined = []
    for bid, item in packet.items():
        grade, code = grades[bid], mapping[bid]
        row = {"blind_id": bid, "source_id": item["source_id"],
               "condition": code["condition"], "job_id": code["job_id"],
               "finish_reason": item["finish_reason"],
               **{k: grade[k] for k in FIELDS}, "note": grade["note"]}
        row["complete_relation"] = all(row[k] for k in FIELDS[:3])
        assert code["condition"] not in paired[row["source_id"]]
        paired[row["source_id"]][code["condition"]] = row
        joined.append(row)
    assert len(paired) == 9
    conditions = sorted({x["condition"] for x in joined})
    assert len(conditions) == 4 and all(set(v) == set(conditions) for v in paired.values())
    counts = {group: {condition: {field: sum(paired[source][condition][field] for source in sources)
                                  for field in (*FIELDS, "complete_relation")}
                      for condition in conditions}
              for group, sources in GROUPS.items()}
    args.out.mkdir(parents=True, exist_ok=False)
    write(args.out / "joined-grades.json", sorted(joined, key=lambda x: (x["source_id"], x["condition"])))
    write(args.out / "item-pairs.json", {k: paired[k] for k in sorted(paired)})
    write(args.out / "counts.json", counts)
    print(json.dumps({group: {c: x["complete_relation"] for c, x in arms.items()}
                      for group, arms in counts.items()}))


if __name__ == "__main__":
    main()
