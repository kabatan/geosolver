"""入力・採否固定後だけAIMEの二次資料Answerを別ファイルへ転記する。

答えの値を表示・評価しない。DSL/manifest/cardを書き換えない。
v2のHMMT答え18行は保存版から保持し、公式冊子の再照合は行わない。
"""
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
BASE = OUT / "revisions/v2-before-aime"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def rows(path):
    return [json.loads(s) for s in path.read_text().splitlines()]


def input_hashes():
    paths = [OUT/name for name in ["manifest.json","cases.jsonl","statements.jsonl","cards.md",
             "authoring-rules.md","build_cases.py","aime_definitions.py","aime_decisions.py","verify_static.py",
             "revisions/v3-input-freeze.json","revisions/v3-selection-freeze.json"]]
    paths += sorted((OUT/"dsl").glob("*.json"))+sorted((OUT/"cards").glob("*.md"))
    return {str(p.relative_to(OUT)):sha(p.read_bytes()) for p in paths}


def main():
    manifest = json.loads((OUT/"manifest.json").read_text())
    freeze = json.loads((OUT/"revisions/v3-input-freeze.json").read_text())
    validation = json.loads((OUT/"validation.json").read_text())
    assert validation["passed"] and validation["cases"] == manifest["selected_count"]
    assert sha((OUT/"manifest.json").read_bytes()) == freeze["manifest_sha256"]
    selected = [r for r in manifest["rows"] if r["status"] == "selected_candidate"]
    for r in selected:
        assert sha((OUT/r["dsl_path"]).read_bytes()) == freeze["input_hashes"][r["id"]] == r["input_sha256"]
    before = input_hashes()
    source_path = OUT/"source-evidence/aime-1983-1999/aime-1983-1999.jsonl"
    assert sha(source_path.read_bytes()) == json.loads((OUT/"revisions/v3-selection-freeze.json").read_text())["source_sha256"]
    # この行以降だけAnswer欄へアクセスする。値による分岐や採否への戻しはない。
    by_slot = {(int(r["Year"]),int(r["Problem Number"])):r for r in rows(source_path)}
    answers, receipts = [], []
    for r in selected:
        if not r["id"].startswith("AIME-"):
            continue
        source = by_slot[(r["year"],r["number"])]
        answers.append(dict(id=r["id"],official_answer=None,official_source=None,
                            secondary_answer=source["Answer"],status="secondary_unverified",
                            source_status="二次資料・未照合",official_booklet_verified=False,
                            reference_source=dict(path=str(source_path.relative_to(OUT)),source_id=source["ID"],
                                                  row_idx=r["source_row"]["row_idx"],sha256=sha(source_path.read_bytes())),
                            reference_usage="採否・DSL・manifest・入力hash固定後の転記のみ。公式冊子との照合は未了。答えを入力に使用しない。"))
        receipts.append(dict(id=r["id"],status="二次資料・未照合",source_row=r["source_row"],
                             statement_sha256=r["statement_sha256"],input_sha256=r["input_sha256"]))
    inherited = rows(BASE/"official_answers.jsonl")
    assert len(inherited) == 18
    answers += inherited
    assert [r["id"] for r in answers] == [r["id"] for r in selected]
    assert len(receipts) == manifest["aime_selected_count"]
    (OUT/"official_answers.jsonl").write_text("".join(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n" for r in answers))
    after = input_hashes()
    assert before == after
    receipt = dict(input_freeze_manifest_sha256=freeze["manifest_sha256"],
                   aime_secondary_answers_transcribed=len(receipts),aime_official_answers_verified=0,
                   hmmt_answers_preserved=18,hmmt_saved_official_transcriptions_preserved=4,hmmt_official_missing=14,
                   hmmt_original_provenance="revisions/v2-before-aime/answer-provenance.json",
                   official_online_verification=False,official_booklet_verification=False,
                   input_artifacts_unchanged=True,dsl_unchanged=True,manifest_unchanged=True,
                   input_artifact_hashes=before,validation_sha256=sha((OUT/"validation.json").read_bytes()),
                   official_answers_sha256=sha((OUT/"official_answers.jsonl").read_bytes()),
                   source_sha256=sha(source_path.read_bytes()),solver_run=False,local_search_run=False,
                   note="AIMEは全件二次資料・未照合。公式答えというファイル名でもofficial_answerはnull。答えを見た後の採否・入力変更はしない。HMMT18行はv2を保持。",
                   rows=receipts)
    (OUT/"answer-provenance.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:receipt[k] for k in ["aime_secondary_answers_transcribed","aime_official_answers_verified",
          "hmmt_answers_preserved","input_artifacts_unchanged","dsl_unchanged","manifest_unchanged","solver_run"]},ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
