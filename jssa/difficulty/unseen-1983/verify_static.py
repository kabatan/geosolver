"""JSONとASTだけの検査。solver・式の数値評価・残差評価は行わない。"""
from __future__ import annotations

import ast
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from geosolver.problem.models import GeometryProblem
from geosolver.problem.validation import _expression_issues

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    parts = value.upper().split("-")
    parts = [{"I": "1", "II": "2"}.get(x, x) for x in parts]
    return "-".join(str(int(x)) if x.isdigit() else x for x in parts)


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def normalized_dsl(d):
    return json.dumps(d, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def statements_normalized(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def main():
    manifest = json.loads((OUT / "manifest.json").read_text())
    cases = read_rows(OUT / "cases.jsonl")
    statements = read_rows(OUT / "statements.jsonl")
    selected = [r for r in manifest["rows"] if r["status"] == "selected_candidate"]
    errors = []
    expressions = 0
    old_files = [ROOT / "benchmarks/cases.jsonl", ROOT / "jssa/difficulty/new2026/cases.jsonl"]
    old = [r for p in old_files for r in read_rows(p)]
    old_ids = {canonical(r["id"]) for r in old}
    old_texts = {statements_normalized(r["problem_statement"]) for r in old if r.get("problem_statement")}
    old_dsls = {sha(normalized_dsl(r["dsl"])) for r in old}
    assert len(cases) == len(selected) == manifest["selected_count"]
    assert len({r["id"] for r in cases}) == len(cases)
    assert [c["id"] for c in cases] == [r["id"] for r in selected]
    assert {r["id"] for r in statements} == {r["id"] for r in manifest["rows"] if "source_row" in r}
    for source in manifest["sources"]:
        assert sha((ROOT / source["path"]).read_bytes()) == source["sha256"], source["path"]
    assert sha((OUT / "authoring-rules.md").read_bytes()) == manifest["selection_rule_sha256"]
    for c, entry in zip(cases, selected):
        p = OUT / c["dsl_path"]
        d = json.loads(p.read_text())
        assert d == c["dsl"]
        assert sha(p.read_bytes()) == entry["input_sha256"], c["id"]
        assert sha(c["problem_statement"].encode()) == entry["statement_sha256"], c["id"]
        assert canonical(c["id"]) not in old_ids
        assert sha(normalized_dsl(d)) not in old_dsls
        assert statements_normalized(c["problem_statement"]) not in old_texts
        assert not ({"answer", "official_answer", "solution", "rating"} & c.keys())
        GeometryProblem.model_validate(d)
        assert len(d["variables"]) == len(set(d["variables"]))
        scope = set(d["variables"])
        for v in scope:
            assert re.fullmatch("[A-Za-z_][A-Za-z0-9_]*", v)

        def inspect(path, expression):
            nonlocal expressions
            expressions += 1
            issues, tree = _expression_issues(path, str(expression), scope)
            for issue in issues:
                errors.append(dict(id=c["id"], path=path, issue=issue.model_dump()))
            assert isinstance(tree, ast.Expression), (c["id"], path)

        for i, construction in enumerate(d["constructions"]):
            assert construction["name"] not in scope
            inspect(f"constructions[{i}].expression", construction["expression"])
            scope.add(construction["name"])
        for i, cond in enumerate(d["conditions"]):
            if "predicate" in cond:
                inspect(f"conditions[{i}].predicate", cond["predicate"])
            else:
                inspect(f"conditions[{i}].left", cond["left"])
                inspect(f"conditions[{i}].right", cond["right"])
        inspect("target", d["target"])
        card = (OUT / entry["card_path"]).read_text()
        assert entry["input_sha256"] in card
        assert entry["statement_sha256"] in card
        for kind in ("constructions", "conditions"):
            assert all(f"`{kind}[{i}]`" in card for i in range(len(d[kind])))
        assert "`target`" in card

    for row in manifest["rows"]:
        if row["status"] != "selected_candidate":
            assert row["input_sha256"] is None and row["dsl_path"] is None
            assert row["exclusion_reason"]
    for row in statements:
        assert sha(row["problem_statement"].encode()) == row["statement_sha256"]
    # 公式答えの内容は読まない。入力集合と原文だけの静的検査。
    assert not any(k.startswith("geosolver.engine") for k in __import__("sys").modules)
    report = dict(passed=not errors, cases=len(cases), ast_expressions=expressions,
                  existing_cases=len(old), overlap_normalized_ids=0,
                  overlap_identical_dsl=0, overlap_normalized_statements=0,
                  pending_aime=manifest["pending_aime_count"],
                  frame_counts=dict(Counter(r["status"] for r in manifest["rows"])),
                  errors=errors, solver_run=False, local_search_run=False,
                  geometry_evaluation=False, official_answers_read=False,
                  scope="JSONモデル、AST、関数名/引数/スコープ、対応カード網羅性、SHA-256。幾何の意味・実行可能性・値の一意性は未検証。")
    (OUT / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
