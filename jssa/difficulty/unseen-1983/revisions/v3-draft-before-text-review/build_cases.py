"""v2を保存したままAIME Questionのみでv3を生成。答えの転記は別工程。
solver・式評価・数値配置生成は一切呼ばない。
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from aime_definitions import definitions
from aime_decisions import SOLID, UNSUPPORTED, COMBINATORIAL_NOTES

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
BASE = OUT / "revisions/v2-before-aime"
SOURCE = OUT / "source-evidence/aime-1983-1999/aime-1983-1999.jsonl"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n")


def jsonl(path, rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True)+"\n" for r in rows))


def read_rows(path):
    return [json.loads(s) for s in path.read_text().splitlines()]


def source_questions():
    # Answerは取得/分岐/出力しない。JSONパース後、直ちに許可4フィールドへ射影。
    return [{k: row[k] for k in ("ID", "Year", "Problem Number", "Question")}
            for row in read_rows(SOURCE)]


def render_card(entry, definition, text):
    card = f"# {entry['id']} 原文→入力対応カード\n\n"
    card += "状態: **二次資料・公式冊子未照合・数値検証未実施**。\n\n"
    card += f"- 資料: `{entry['source_row']['source_path']}` / line {entry['source_row']['row_idx']}\n"
    card += f"- 原文SHA-256: `{entry['statement_sha256']}`\n- 入力SHA-256: `{entry['input_sha256']}`\n"
    card += f"- 座標固定・同値性: {definition['gauge']}\n"
    card += "- 答えは `official_answers.jsonl` へ入力固定後に分離。選定・入力には未使用。\n\n"
    card += "## 手元の原文（二次資料のQuestionをそのまま保存）\n\n"+text+"\n\n"
    card += "## 対応\n\n| 原文の条件・定義 | DSL位置 | 入力 |\n|---|---|---|\n"
    for mapping in definition["mapping"]:
        fields = [mapping["source_clause"], f"`{mapping['path']}`", f"`{mapping['expression']}`"]
        card += "| "+" | ".join(s.replace("|", "&#124;").replace("\n", " ") for s in fields)+" |\n"
    card += "\n## 残る制約\n\n"+(definition["notes"] or "公式冊子照合と独立の意味監査は未了。")+"\n"
    card += "\n分枝・内部・非退化は表のguardで明示。根番号で解を選ばない。AST合格は幾何同値性・実行可能性・目標の一意性を保証しない。\n"
    return card


def main():
    freeze = json.loads((OUT/"revisions/v3-selection-freeze.json").read_text())
    assert sha(SOURCE.read_bytes()) == freeze["source_sha256"]
    assert sha((OUT/"authoring-rules.md").read_bytes()) == freeze["selection_rule_sha256"]
    for name, expected in json.loads((BASE/"snapshot-sha256.json").read_text()).items():
        assert sha((BASE/name).read_bytes()) == expected, name
    old_manifest = json.loads((BASE/"manifest.json").read_text())
    hmmt_cases = read_rows(BASE/"cases.jsonl")
    for case in hmmt_cases:
        assert (OUT/case["dsl_path"]).read_bytes() == (BASE/case["dsl_path"]).read_bytes()
    questions = source_questions()
    assert len(questions) == 224
    by_slot = {(int(r["Year"]),int(r["Problem Number"])):(i,r) for i,r in enumerate(questions,1)}
    assert len(by_slot) == 224 and all(1983<=y<=1999 and 1<=n<=15 for y,n in by_slot)
    defs = definitions()
    aime_rows, aime_cases, statements, cards = [], [], [], []
    assert not (set(UNSUPPORTED) & SOLID)
    assert not ({k.removeprefix("AIME-") for k in defs} & (set(UNSUPPORTED)|SOLID))
    for year in range(1983,2000):
        for number in range(1,16):
            key = f"{year}-{number:02}"
            cid = "AIME-"+key
            entry = dict(id=cid,year=year,number=number,statement_sha256=None,input_sha256=None,dsl_path=None)
            if (year,number) not in by_slot:
                entry.update(status="missing_data",geometry_classification="unknown_missing_data",
                             reason_code="missing_data",exclusion_reason="提供224行にこの年・番号の行がない。分野も未判定。")
            else:
                line, row = by_slot[(year,number)]
                text = row["Question"]
                entry.update(source_row=dict(source_path=str(SOURCE.relative_to(ROOT)),row_idx=line,source_id=row["ID"]),
                             statement_sha256=sha(text.encode()),source_status="二次資料・公式冊子未照合")
                statements.append(dict(id=cid,**entry["source_row"],problem_statement=text,statement_sha256=entry["statement_sha256"],source="secondary_huggingface",transcription_note="Question無変更。公式冊子との照合は未了。"))
                if cid in defs:
                    definition = defs[cid]
                    path = OUT/"dsl"/(cid+".json")
                    dump(path,definition["dsl"])
                    entry.update(status="selected_candidate",geometry_classification="planar_geometry",
                                 reason_code="direct_planar_value",exclusion_reason=None,
                                 input_sha256=sha(path.read_bytes()),dsl_path=str(path.relative_to(OUT)),
                                 card_path=f"cards/{cid}.md",n_variables=len(definition["dsl"]["variables"]))
                    aime_cases.append(dict(id=cid,dsl_path=entry["dsl_path"],dsl=definition["dsl"],
                                           problem_statement=text,source="AIME 1983–1999 / 二次資料・公式冊子未照合"))
                    card = render_card(entry,definition,text)
                    (OUT/entry["card_path"]).write_text(card)
                    cards.append(card)
                elif key in UNSUPPORTED:
                    code, reason = UNSUPPORTED[key]
                    entry.update(status="dsl_unsupported",geometry_classification="planar_geometry",
                                 reason_code=code,exclusion_reason=reason)
                elif key in SOLID:
                    entry.update(status="not_geometry",geometry_classification="out_of_scope_solid",
                                 reason_code="not_planar_solid",exclusion_reason="立体・球・多面体・体積または立体の組合せを本質的に含み、平面幾何の対象外。")
                else:
                    entry.update(status="not_geometry",geometry_classification="not_geometry",
                                 reason_code="not_geometry",exclusion_reason=COMBINATORIAL_NOTES.get(key,
                                 "本文の主対象は代数・整数・数列・組合せ・確率であり、ユークリッド平面の有限配置の形や測度を問う問題ではない。"))
            aime_rows.append(entry)
    assert {r["id"] for r in aime_cases} == set(defs)
    legacy_rows = [r for r in old_manifest["rows"] if not r["id"].startswith("AIME-")]
    cases = aime_cases+hmmt_cases
    jsonl(OUT/"cases.jsonl",cases)
    jsonl(OUT/"statements.jsonl",statements+read_rows(BASE/"statements.jsonl"))
    (OUT/"cards.md").write_text("# Q2対応カード集 v3\n\nAIME補充は二次資料・公式冊子未照合。旧HMMT18問はv2のまま保持。\n\n"+
                                  "\n\n---\n\n".join(cards)+"\n\n---\n\n"+(BASE/"cards.md").read_text())
    sources = [SOURCE,BASE/"manifest.json",BASE/"cases.jsonl",BASE/"statements.jsonl",
               ROOT/"benchmarks/cases.jsonl",ROOT/"jssa/difficulty/new2026/cases.jsonl"]
    rows = aime_rows+legacy_rows
    manifest = dict(schema_version=3,status="authored_candidates_pending_source_and_semantic_audit",
                    selection_rule_file="authoring-rules.md",selection_rule_sha256=freeze["selection_rule_sha256"],
                    selection_rule_text=(OUT/"authoring-rules.md").read_text(),selection_freeze_file="revisions/v3-selection-freeze.json",
                    selection_order="AIME year 1983..1999, number 1..15; all directly expressible candidates, no quota stop",
                    hash_contract=old_manifest["hash_contract"],target_count=[24,30],quota_is_cap=False,
                    selected_count=len(cases),aime_selected_count=len(aime_cases),hmmt_preserved_count=len(hmmt_cases),
                    aime_source_rows=224,aime_slots=255,pending_aime_count=sum(r["status"]=="missing_data" for r in aime_rows),
                    aime_status_counts=dict(Counter(r["status"] for r in aime_rows)),
                    aime_reason_counts=dict(Counter(r["reason_code"] for r in aime_rows)),
                    counts=dict(Counter(r["reason_code"] for r in rows)),ready_for_main_validation=False,
                    official_answers_verified=0,source_status="AIME二次資料・公式冊子との照合は未了。AoPS wikiは取得担当の記録では403。今回再取得なし。",
                    legacy_hmmt_manifest="revisions/v2-before-aime/manifest.json",old_case_count=343,
                    sources=[dict(path=str(p.relative_to(ROOT)),sha256=sha(p.read_bytes())) for p in sources],
                    authoring_code_sha256={p.name:sha(p.read_bytes()) for p in [Path(__file__),OUT/"aime_definitions.py",OUT/"aime_decisions.py"]},
                    solver_run=False,local_search_run=False,geometry_evaluation=False,answer_used_for_selection=False,
                    answer_sealing="separate seal_answers.py after input+manifest freeze",rows=rows)
    dump(OUT/"manifest.json",manifest)
    dump(OUT/"revisions/v3-input-freeze.json",dict(phase="before_aime_answer_transfer",manifest_sha256=sha((OUT/"manifest.json").read_bytes()),
         selection_rule_sha256=freeze["selection_rule_sha256"],input_hashes={r["id"]:r["input_sha256"] for r in rows if r["status"]=="selected_candidate"},
         answer_field_used=False,solver_run=False))
    print(json.dumps({k:manifest[k] for k in ["selected_count","aime_selected_count","hmmt_preserved_count","aime_status_counts"]},ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
