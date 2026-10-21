"""Summarize the frozen numeric evaluation from manually audited grades."""

import argparse
import json
from collections import Counter
from pathlib import Path


FIELDS = ("exact", "relation", "proof", "applied", "complete")


def read_grades(path: Path):
    rows = json.loads(path.read_text())
    by_key = {}
    for row in rows:
        key = (row["config"], row["sample"])
        if key in by_key:
            raise ValueError(f"duplicate grade: {key}")
        if row["complete"] != all(row[field] for field in FIELDS[:-1]):
            raise ValueError(f"inconsistent complete flag: {key}")
        by_key[key] = row
    return by_key


def summarize(rows, configs):
    selected = [row for row in rows.values() if row["config"] in configs]
    return {
        "answers": len(selected),
        **{field: sum(row[field] for row in selected) for field in FIELDS},
        "successful_configs": len({row["config"] for row in selected if row["complete"]}),
        "truncated": sum(row["finish"] == "length" for row in selected),
        "max_tokens": max((row["tokens"] for row in selected), default=0),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("base", type=Path)
    parser.add_argument("updated", type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())["numeric"]
    configs = {item["config"] for item in manifest}
    strata = {
        "all": configs,
        "shape": {item["config"] for item in manifest if item["augmentation"] == "shape"},
        "similarity": {item["config"] for item in manifest if item["augmentation"] == "similarity"},
        "train_overlap": {item["config"] for item in manifest if item["train_configuration_overlap"]},
        "nonoverlap": {item["config"] for item in manifest if not item["train_configuration_overlap"]},
    }
    expected = {(config, sample) for config in configs for sample in (0, 1)}
    base, updated = read_grades(args.base), read_grades(args.updated)
    for name, rows in (("base", base), ("updated", updated)):
        if set(rows) != expected:
            raise ValueError(f"{name}: missing={sorted(expected-set(rows))}, extra={sorted(set(rows)-expected)}")
        for key, row in rows.items():
            info = next(item for item in manifest if item["config"] == key[0])
            if row["augmentation"] != info["augmentation"] or row["train_overlap"] != info["train_configuration_overlap"]:
                raise ValueError(f"{name}: wrong stratum for {key}")

    output = {
        "base": {name: summarize(base, group) for name, group in strata.items()},
        "updated": {name: summarize(updated, group) for name, group in strata.items()},
        "paired_complete": dict(Counter(f"{int(base[key]['complete'])}->{int(updated[key]['complete'])}" for key in expected)),
        "config_complete": {
            model: {config: sum(rows[(config, sample)]["complete"] for sample in (0, 1)) for config in sorted(configs)}
            for model, rows in (("base", base), ("updated", updated))
        },
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
