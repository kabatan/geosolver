# ruff: noqa: E501, SIM115
"""Write AUDIT.md: statement, DSL, clause mapping and verification per case."""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

STATEMENT_IDS = {
    "HMMT-2026-FEB-GEO-": "hmmt-2026-feb-geo-",
    "HMMT-2026-FEB-GUTS-": "hmmt-2026-feb-guts-",
    "JMO-2026-PRE-": "jmo-2026-pre-",
}


def statement_id(case_id):
    for prefix, lower in STATEMENT_IDS.items():
        if case_id.startswith(prefix):
            return lower + case_id[len(prefix):]
    raise KeyError(case_id)


def main():
    statements = {
        json.loads(line)["id"]: json.loads(line)
        for line in open(HERE / "statements.jsonl", encoding="utf-8")
    }
    mapping = json.load(open(HERE / "mapping.json", encoding="utf-8"))
    verification = json.load(open(HERE / "verification.json", encoding="utf-8"))
    out = ["# 2026年新規問題 DSL監査表", "",
           "規則: [authoring-rules.md](authoring-rules.md)。検算方法: `verify/check_dsl.py`"
           "（GeoSolverの探索は使わず、DSL評価層＋SciPy多点開始＋60桁Gauss-Newton）。", ""]
    out.append("| id | 公式の答え | 検算 | 実行可能配置の目標値 | 備考 |")
    out.append("|---|---|---|---|---|")
    rows = [json.loads(line) for line in open(HERE / "cases.jsonl", encoding="utf-8")]
    for row in rows:
        v = verification[row["id"]]
        out.append(f"| {row['id']} | {', '.join(row['answer'])} | {v['verdict']} | "
                   f"{v['values']} | {v.get('remark', '')} |")
    out.append("")
    for row in rows:
        cid = row["id"]
        st = statements[statement_id(cid)]
        m = mapping[cid]
        v = verification[cid]
        out += [f"## {cid}", "", f"出典: {row['source']}", "", "**原文**", "", "> " + st["statement"].replace("\n", "\n> "), ""]
        if st.get("notes"):
            out += [f"図の情報（収集時のメモ）: {st['notes']}", ""]
        out += [f"公式の答え: `{st['official_answer']}` → 参照値 `{', '.join(row['answer'])}`", "",
                "**原文とDSLの対応**", "", "| 原文 | DSL | 根拠・正規化・枝 |", "|---|---|---|"]
        for src, dsl, why in m["mapping"]:
            out.append(f"| {src} | `{dsl}` | {why} |" if "`" not in dsl else f"| {src} | {dsl} | {why} |")
        if m["notes"]:
            out += ["", f"注: {m['notes']}"]
        out += ["", "**DSL**", "", "```json", json.dumps(row["dsl"], ensure_ascii=False, indent=1), "```", "",
                "**検算**", "", "```", v["log"].rstrip(), "```", ""]
        if v.get("remark"):
            out += [f"判定の補足: {v['remark']}", ""]
    (HERE / "AUDIT.md").write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
