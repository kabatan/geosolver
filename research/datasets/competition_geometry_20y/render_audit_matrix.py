#!/usr/bin/env python3
"""Render a compact, reviewable year/contest decision matrix."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent
rows = [json.loads(line) for line in (ROOT / "scope_inventory.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
groups: dict[tuple[int, str], list[dict]] = defaultdict(list)
for row in rows:
    if row["scope_status"] == "metadata_only":
        continue
    groups[(int(row["year"]), row["contest"])].append(row)

out = [
    "# 20年手動監査マトリクス",
    "",
    "`manual_scope_audit.py`で問題文または公式問題画像を一問ずつ確認した結果。HMMT 2011のtrack再掲は `dedupe_key` でまとめ、JMOの公式年次リンクは問題行に数えていない。",
    "",
    "| 年 | contest | source rows | unique in-scope | unique out-of-scope | JSON | runnable | reference_only | pending |",
    "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
]
for year in range(2006, 2026):
    for contest in ("AIME", "HMMT", "JMO preliminary"):
        group = groups.get((year, contest), [])
        if not group:
            continue
        scope = [r for r in group if r["scope_status"] == "in_scope"]
        unique_scope = {r["dedupe_key"] for r in scope}
        unique_out = {r["dedupe_key"] for r in group if r["scope_status"] == "out_scope"}
        ready = {r["dedupe_key"] for r in scope if r["dsl_status"] == "ready"}
        pending = unique_scope - ready
        runnable = set()
        reference_only = set()
        for dedupe in ready:
            candidate = ROOT / "dsl" / f"{dedupe}.json"
            if not candidate.exists():
                matching = [r for r in scope if r["dedupe_key"] == dedupe and r.get("dsl_path")]
                candidate = ROOT / (matching[0]["dsl_path"] if matching else "__missing__.json")
            if candidate.exists():
                case = json.loads(candidate.read_text(encoding="utf-8"))
                if str(case.get("solver_coverage", "")).startswith("reference_only"):
                    reference_only.add(dedupe)
                else:
                    runnable.add(dedupe)
        out.append(f"| {year} | {contest} | {len(group)} | {len(unique_scope)} | {len(unique_out)} | {len(ready)} | {len(runnable)} | {len(reference_only)} | {len(pending)} |")

out += ["", "## 問題ID一覧", ""]
for year in range(2006, 2026):
    for contest in ("AIME", "HMMT", "JMO preliminary"):
        group = groups.get((year, contest), [])
        if not group:
            continue
        scope = sorted({r["dedupe_key"] for r in group if r["scope_status"] == "in_scope"})
        out.append(f"- **{year} {contest} / in_scope ({len(scope)})**: {', '.join(scope)}")
        out.append("")

(ROOT / "AUDIT_MATRIX.md").write_text("\n".join(out) + "\n", encoding="utf-8")
print(f"wrote {ROOT / 'AUDIT_MATRIX.md'}")
