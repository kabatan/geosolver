"""入力固定後に保存済み公式解答のAnswer行だけを別ファイルに転記する。

DSLや採否は変更しない。解法を入力へ戻さない。ネットワークやsolverを呼ばない。
"""
import hashlib
import json
import re
from pathlib import Path

OUT = Path(__file__).resolve().parent
SAVED = Path("/home/kabatan/work/solver-research-assets/corpus97-sources")
KEYS = {"HMMT-2016-FEB-GEO-01": (2016, 1), "HMMT-2022-FEB-GEO-07": (2022, 7),
        "HMMT-2022-FEB-GEO-08": (2022, 8), "HMMT-2023-FEB-GEO-06": (2023, 6)}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    manifest_bytes = (OUT / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    validation = json.loads((OUT / "validation.json").read_text())
    assert validation["passed"] and validation["cases"] == manifest["selected_count"] == 18
    before = {p.name: sha(p.read_bytes()) for p in (OUT / "dsl").glob("*.json")}
    for row in manifest["rows"]:
        if row["status"] == "selected_candidate":
            assert before[row["id"]+".json"] == row["input_sha256"]
    answers = [json.loads(s) for s in (OUT / "official_answers.jsonl").read_text().splitlines()]
    receipts = []
    for row in answers:
        if row["id"] not in KEYS:
            continue
        year, number = KEYS[row["id"]]
        path = SAVED / f"hmmt-{year}-geo-solutions.txt"
        source = path.read_text()
        # 問題見出し以後の最初のAnswer行のみ。解法の本文は転記しない。
        head = re.search(rf"^\s*{number}\.\s", source, re.M)
        assert head is not None
        answer = re.search(r"^\s*Answer:\s*([^\n]+)", source[head.end():], re.M)
        assert answer is not None
        value = answer.group(1).strip()
        assert re.fullmatch(r"\d+(?:,\s*\d+)*", value), value
        values = [int(s.strip()) for s in value.split(",")]
        row.update(official_answer=values if len(values)>1 else values[0],
                   official_source=str(path), status="transcribed_from_saved_official_solution_text",
                   reference_usage="入力・採否・hash固定後のAnswer行転記のみ。DSLへのフィードバックなし。")
        receipts.append(dict(id=row["id"], source_path=str(path), source_sha256=sha(path.read_bytes()),
                             answer_line="Answer: " + value, online_source_verified=False))
    (OUT / "official_answers.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True)+"\n" for r in answers))
    assert before == {p.name: sha(p.read_bytes()) for p in (OUT / "dsl").glob("*.json")}
    assert manifest_bytes == (OUT / "manifest.json").read_bytes()
    receipt = dict(input_freeze_manifest_sha256=sha(manifest_bytes), official_answers_available=len(receipts),
                   official_answers_missing=18-len(receipts), official_online_verification=False,
                   dsl_unchanged=True, manifest_unchanged=True, solver_run=False,
                   note="保存済み公式解答テキストのAnswer行。manifest内のofficial_answers_verified=0は入力固定時の状態。オンラインの出典再検証はしていない。",
                   rows=receipts)
    (OUT / "answer-provenance.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({k:v for k,v in receipt.items() if k != "rows"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
