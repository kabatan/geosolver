"""Small, preregistered theory checks and metadata census; no solver calls."""
import argparse
import collections
import csv
import hashlib
import itertools
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def locked_hashes():
    return {name: digest(OUT / name) for name in ("preregistration.md", "audit.py")}


def write_json(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def counterexamples():
    torus = []
    for d in (1, 2, 3, 4):
        counts = [0] * (d + 1)
        false_min = 0
        max_grad = 0.0
        for bits in itertools.product((0, 1), repeat=d):
            theta = [bit * math.pi for bit in bits]
            hessian = [2 * math.cos(t) for t in theta]
            index = sum(h < 0 for h in hessian)
            counts[index] += 1
            residual_sq = sum((math.cos(t) - 1) ** 2 + math.sin(t) ** 2 for t in theta)
            max_grad = max(max_grad, *(abs(2 * math.sin(t)) for t in theta))
            assert min(map(abs, hessian)) > 1e-8
            false_min += int(index == 0 and residual_sq > 1e-8)
        expected = [math.comb(d, k) for k in range(d + 1)]
        torus.append(dict(d=d, counts_by_index=counts, betti=expected,
                          false_minima=false_min, max_gradient=max_grad,
                          passed=counts == expected and false_min == 0 and max_grad <= 1e-11))
    quartic = []
    for eps, expected in ((1.0, (1, 0, 0)), (0.25, (2, 1, 1))):
        roots = [0.0]
        if 1 - 2 * eps >= 0:
            roots += [(3 - math.sqrt(1 - 2 * eps)) / 2,
                      (3 + math.sqrt(1 - 2 * eps)) / 2]
        rows = []
        for x in roots:
            f = (x * (x - 2)) ** 2 + (math.sqrt(eps) * x) ** 2
            expanded = x ** 4 - 4 * x ** 3 + (4 + eps) * x ** 2
            grad = 4 * x ** 3 - 12 * x ** 2 + 2 * (4 + eps) * x
            hess = 12 * x ** 2 - 24 * x + 2 * (4 + eps)
            rows.append(dict(x=x, f=f, gradient=grad, hessian=hess,
                             kind="minimum" if hess > 0 else "maximum",
                             passed=abs(grad) <= 1e-11 and abs(hess) > 1e-8
                             and abs(f - expanded) <= 1e-11))
        counts = (sum(r["kind"] == "minimum" for r in rows),
                  sum(r["kind"] == "maximum" for r in rows),
                  sum(r["kind"] == "minimum" and r["f"] > 1e-8 for r in rows))
        quartic.append(dict(epsilon=eps, critical_points=rows, counts=counts,
                            expected=expected, passed=counts == expected and all(r["passed"] for r in rows)))
    return dict(C1=torus, C2=quartic,
                all_passed=all(r["passed"] for r in torus + quartic))


def census():
    table_path = ROOT / "jssa/difficulty/minima/basins-323.csv"
    with table_path.open(newline="") as handle:
        table = list(csv.DictReader(handle))
    result = dict(table_rows=len(table), table_sha256=digest(table_path),
                  variables=sorted(collections.Counter(int(r["n_vars"]) for r in table).items()),
                  multiple_correct_coordinate_clusters=sum(int(r["n_correct_basins"] or 0) >= 2 for r in table),
                  seeds={})
    per_problem = []
    for seed, folder in ((0, "raw-323"), (1, "raw-323-seed1")):
        counts, keys, status_counts = collections.Counter(), collections.Counter(), collections.Counter()
        missing = []
        cases_with_records = cases_with_hit = max_bytes = 0
        total_hash = hashlib.sha256()
        for row in table:
            path = ROOT / "jssa/difficulty/minima" / folder / (row["id"] + ".json")
            if not path.is_file():
                missing.append(row["id"])
                continue
            payload = path.read_bytes()
            total_hash.update(row["id"].encode() + b"\0" + hashlib.sha256(payload).digest())
            max_bytes = max(max_bytes, len(payload))
            data = json.loads(payload)
            records = data.get("records", [])
            case_counts = collections.Counter(r.get("cls", "missing") for r in records)
            status_counts[data.get("status", "missing")] += 1
            cases_with_records += bool(records)
            cases_with_hit += case_counts["hit"] > 0
            counts.update(case_counts)
            for record in records:
                keys.update(record.keys())
            per_problem.append(dict(seed=seed, id=row["id"], n_vars=row["n_vars"],
                                    n_records=len(records), hit=case_counts["hit"],
                                    stuck=case_counts["stuck"], left_box=case_counts["left_box"],
                                    wrong_branch=case_counts["wrong_branch"],
                                    wrong_answer=case_counts["wrong_answer"], error=case_counts["error"],
                                    raw_sha256=hashlib.sha256(payload).hexdigest()))
        result["seeds"][str(seed)] = dict(cases_with_records=cases_with_records,
            cases_with_hit=cases_with_hit, n_records=sum(counts.values()),
            classes=dict(counts), record_key_occurrences=dict(keys),
            file_statuses=dict(status_counts), missing_files=missing,
            max_input_file_bytes=max_bytes, ordered_input_digest=total_hash.hexdigest())
    with (OUT / "census.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(per_problem[0]))
        writer.writeheader()
        writer.writerows(per_problem)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    if args.freeze:
        target = OUT / "freeze.json"
        with target.open("x") as handle:
            json.dump(dict(time_utc=datetime.now(timezone.utc).isoformat(), sha256=locked_hashes()), handle, indent=2)
            handle.write("\n")
        print(target.read_text())
        return
    locked = json.loads((OUT / "freeze.json").read_text())["sha256"]
    assert locked_hashes() == locked
    started = time.monotonic()
    result = dict(checks=counterexamples(), census=census(), solver_calls=0,
                  elapsed_seconds=time.monotonic() - started)
    assert locked_hashes() == locked
    result["registration_hashes_unchanged"] = True
    write_json("audit.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
