"""Join frozen blinded LOO grades to arm identities and paired base grades."""

import argparse
import json
from collections import defaultdict
from pathlib import Path


FIELDS = ("exact", "relation", "proof", "use")
TARGETS = {"H03", "H04", "H14"}
CONTROLS = {"H01", "H02", "H07", "H13"}


def read(path: Path):
    return json.loads(path.read_text())


def write(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--packet", type=Path, required=True)
    p.add_argument("--mapping", type=Path, required=True)
    p.add_argument("--grade", type=Path, action="append", required=True)
    p.add_argument("--base", type=Path, required=True,
                   help="First-pass scored-near-transfer joined-grades.json")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()

    packet = {r["blind_id"]: r for r in read(args.packet)}
    mapping = {r["blind_id"]: r for r in read(args.mapping)}
    assert len(packet) == len(mapping) == 15 and packet.keys() == mapping.keys()
    grades = {}
    for path in args.grade:
        rows = read(path)
        if isinstance(rows, dict):
            rows = rows["grades"]
        for row in rows:
            bid = row["blind_id"]
            assert bid in packet and bid not in grades
            assert all(type(row[k]) is bool for k in FIELDS)
            assert type(row["uncertain"]) is bool and not row["uncertain"]
            assert isinstance(row["note"], str) and row["note"].strip()
            assert row.get("source_id", packet[bid]["source_id"]) == packet[bid]["source_id"]
            grades[bid] = row
    assert grades.keys() == packet.keys()

    base = {}
    for row in read(args.base):
        if row["condition"] == "base":
            assert row["source_id"] not in base
            base[row["source_id"]] = row
    assert TARGETS | CONTROLS <= base.keys()

    joined, by_arm = [], defaultdict(dict)
    for bid in packet:
        source = packet[bid]["source_id"]
        arm = mapping[bid]["condition"]
        target = arm.removeprefix("minus-")
        assert arm == f"minus-{target}" and target in TARGETS
        assert source in CONTROLS | {target}
        row = {"blind_id": bid, "source_id": source, "condition": arm,
               "finish_reason": packet[bid]["finish_reason"],
               **{field: grades[bid][field] for field in FIELDS},
               "note": grades[bid]["note"]}
        row["complete"] = all(row[field] for field in FIELDS)
        assert source not in by_arm[arm]
        by_arm[arm][source] = row
        joined.append(row)
    assert set(by_arm) == {f"minus-{target}" for target in TARGETS}
    assert all(set(rows) == CONTROLS | {arm.removeprefix('minus-')}
               for arm, rows in by_arm.items())

    counts = {}
    for target in sorted(TARGETS):
        arm = f"minus-{target}"
        rows = by_arm[arm]
        counts[arm] = {
            "target": {field: int(rows[target][field]) for field in (*FIELDS, "complete")},
            "base_target": {field: int(base[target][field]) for field in (*FIELDS, "complete")},
            "controls": {field: sum(rows[source][field] for source in CONTROLS)
                         for field in (*FIELDS, "complete")},
            "base_controls": {field: sum(base[source][field] for source in CONTROLS)
                              for field in (*FIELDS, "complete")},
        }
    args.out.mkdir(parents=True, exist_ok=False)
    write(args.out / "joined-grades.json", joined)
    write(args.out / "counts.json", counts)
    print(json.dumps({arm: {group: score["complete"] for group, score in groups.items()}
                      for arm, groups in counts.items()}))


if __name__ == "__main__":
    main()
