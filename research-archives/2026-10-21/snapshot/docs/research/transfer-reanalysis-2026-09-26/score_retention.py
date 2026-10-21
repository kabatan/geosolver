"""Score the four frozen elementary checks, with receipt and source verification."""
import argparse
import hashlib
import json
from pathlib import Path

from score_numeric import grade_numeric_text

HERE = Path(__file__).resolve().parent
ANSWERS = {
    "easy-triangle-median": "2*sqrt(7)",
    "easy-right-circumradius": "15/2",
    "easy-angle-bisector": "5",
    "easy-intersecting-chords": "6",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    jobs_file = HERE / "retention-jobs.json"
    jobs = json.loads(jobs_file.read_text())
    assert len(jobs) == 4 and {j["source_id"] for j in jobs} == set(ANSWERS)
    run = json.loads((args.run_dir / "receipt.json").read_text())
    assert run["inputs"][str(jobs_file)] == sha(jobs_file)
    assert not run["extended_jobs"].get("retention"), "Use a selected-source scorer if retries exist"
    results = {}
    for condition in ("base", "code128", "numeric128", "opd32"):
        label = f"retention-{condition}-32768"
        assert label in run["completed"]
        directory = args.run_dir / label
        receipt_file = directory / "receipt.json"
        receipt = json.loads(receipt_file.read_text())
        for key, expected in dict(status="complete", completed_jobs=4, samples=1,
                                  cap=32768, context=40960, batch_size=4,
                                  temperature=0.7, top_p=0.95, top_k=20,
                                  presence_penalty=0.2, enable_thinking=False,
                                  jobs_sha256=sha(jobs_file),
                                  driver_sha256=sha(HERE / "generate_batch.py")).items():
            assert receipt[key] == expected, (label, key)
        if condition == "base":
            assert receipt["adapter"] is None and receipt["adapter_sha256"] is None
        else:
            adapter = Path(receipt["adapter"]) / "adapter_model.safetensors"
            assert sha(adapter) == receipt["adapter_sha256"] == run["inputs"][str(adapter)]
        assert {p.name for p in directory.glob("*-0.json")} == {j["id"] + "-0.json" for j in jobs}
        rows = []
        for job in jobs:
            source = directory / (job["id"] + "-0.json")
            row = json.loads(source.read_text())
            assert all(row[k] == v for k, v in job.items())
            assert row["sample"] == 0 and row["finish_reason"] == "stop"
            assert row["adapter"] == receipt["adapter"] and row["revision"] == receipt["model_revision"]
            expected = ANSWERS[job["source_id"]]
            grade = grade_numeric_text(row["raw_text"], expected)
            rows.append(dict(job_id=job["id"], expected=expected, grade=grade,
                             source_file=str(source.resolve()), source_sha256=sha(source),
                             final_excerpt=row["raw_text"][-1200:],
                             completion_tokens=len(row["completion_ids"])))
        results[condition] = dict(correct=sum(r["grade"]["numeric_correct"] is True for r in rows),
                                  total=4, natural_end=4, rows=rows,
                                  receipt_sha256=sha(receipt_file))
    report = dict(status="complete", jobs_sha256=sha(jobs_file),
                  scorer_sha256=sha(Path(__file__)), conditions=results)
    with args.out.open("x") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({c: r["correct"] for c, r in results.items()}))


if __name__ == "__main__":
    main()
