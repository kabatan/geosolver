"""JSONモデル・AST・hash・対応カード・静的重複だけ。式評価もsolverも呼ばない。"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from geosolver.problem.models import GeometryProblem
from geosolver.problem.validation import _expression_issues

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
BASE = OUT / "revisions/v2-before-aime"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    parts = value.upper().split("-")
    parts = [{"I": "1", "II": "2"}.get(x, x) for x in parts]
    return "-".join(str(int(x)) if x.isdigit() else x for x in parts)


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def normalized_dsl(d):
    # 別IDでも同じ入力を検出する。IDは幾何の内容ではない。
    return json.dumps({k:v for k,v in d.items() if k != "id"}, sort_keys=True,
                      ensure_ascii=False, separators=(",", ":")).encode()


def alpha_dsl(d):
    """変数・構成名の一貫した改名と条件順だけを無視するAST指紋。評価しない。"""
    names = {name:f"var_{i}" for i,name in enumerate(d["variables"])}
    names.update({c["name"]:f"object_{i}" for i,c in enumerate(d["constructions"])})

    class Rename(ast.NodeTransformer):
        def visit_Name(self,node):
            return ast.Name(id=names.get(node.id,node.id),ctx=node.ctx)

    def expression(s):
        return ast.dump(Rename().visit(ast.parse(str(s),mode="eval")),include_attributes=False)

    cons = [expression(c["expression"]) for c in d["constructions"]]
    conds = []
    for c in d["conditions"]:
        if "predicate" in c:
            conds.append(("predicate",expression(c["predicate"])))
        else:
            conds.append((c["operator"],expression(c["left"]),expression(c["right"])))
    return sha(json.dumps([len(names),cons,sorted(conds),expression(d["target"])],sort_keys=True).encode())


def statement_normalized(s):
    s = re.sub(r"\[asy\].*?\[/asy\]", "", s, flags=re.S)
    return re.sub(r"[^a-z0-9]", "", s.lower())


def main():
    manifest = json.loads((OUT/"manifest.json").read_text())
    cases = read_rows(OUT/"cases.jsonl")
    statements = read_rows(OUT/"statements.jsonl")
    selected = [r for r in manifest["rows"] if r["status"] == "selected_candidate"]
    aime = manifest["rows"][:255]
    assert [r["id"] for r in aime] == [f"AIME-{y}-{n:02}" for y in range(1983,2000) for n in range(1,16)]
    assert dict(Counter(r["status"] for r in aime)) == manifest["aime_status_counts"]
    assert dict(Counter(r["reason_code"] for r in aime)) == manifest["aime_reason_counts"]
    assert sum("source_row" in r for r in aime) == manifest["aime_source_rows"] == 224
    assert sum(r["status"] == "missing_data" for r in aime) == manifest["pending_aime_count"] == 31
    assert len(cases) == len(selected) == manifest["selected_count"]
    assert len({r["id"] for r in cases}) == len(cases)
    assert [c["id"] for c in cases] == [r["id"] for r in selected]
    assert {r["id"] for r in statements} == {r["id"] for r in manifest["rows"] if "source_row" in r}
    assert len(statements) == len({r["id"] for r in statements})
    text_by_id = {r["id"]:r for r in statements}
    for source in manifest["sources"]:
        assert sha((ROOT/source["path"]).read_bytes()) == source["sha256"], source["path"]
    assert (OUT/"authoring-rules.md").read_text() == manifest["selection_rule_text"]
    assert sha((OUT/"authoring-rules.md").read_bytes()) == manifest["selection_rule_sha256"]
    for name,h in manifest["authoring_code_sha256"].items():
        assert sha((OUT/name).read_bytes()) == h, name
    for name,h in json.loads((BASE/"snapshot-sha256.json").read_text()).items():
        assert sha((BASE/name).read_bytes()) == h, name
    freeze = json.loads((OUT/"revisions/v3-input-freeze.json").read_text())
    assert sha((OUT/"manifest.json").read_bytes()) == freeze["manifest_sha256"]
    source_path = OUT/"source-evidence/aime-1983-1999/aime-1983-1999.jsonl"
    # 原文だけ照合。Answerフィールドは参照しない。
    question_by_slot = {(int(r["Year"]),int(r["Problem Number"])):r["Question"] for r in read_rows(source_path)}
    for r in aime:
        if r["status"] == "missing_data":
            assert (r["year"],r["number"]) not in question_by_slot
            assert r["statement_sha256"] is None
        else:
            text = question_by_slot[(r["year"],r["number"])]
            assert text_by_id[r["id"]]["problem_statement"] == text
            assert sha(text.encode()) == r["statement_sha256"]
    old_groups = [("benchmarks",read_rows(ROOT/"benchmarks/cases.jsonl")),
                  ("new2026",read_rows(ROOT/"jssa/difficulty/new2026/cases.jsonl"))]
    hmmt = read_rows(BASE/"cases.jsonl")
    assert len(old_groups[0][1]) == 323 and len(old_groups[1][1]) == 20 and len(hmmt) == 18
    assert [c for c in cases if c["id"].startswith("HMMT-")] == hmmt
    for c in hmmt:
        assert (OUT/c["dsl_path"]).read_bytes() == (BASE/c["dsl_path"]).read_bytes()
        card_path = "cards/"+c["id"]+".md"
        assert (OUT/card_path).read_bytes() == (BASE/card_path).read_bytes()
    errors, expressions = [], 0
    for c, entry in zip(cases,selected):
        p = OUT/c["dsl_path"]
        d = json.loads(p.read_text())
        assert d == c["dsl"]
        assert sha(p.read_bytes()) == entry["input_sha256"] == freeze["input_hashes"][c["id"]]
        assert sha(c["problem_statement"].encode()) == entry["statement_sha256"]
        assert not ({"answer","official_answer","secondary_answer","solution","rating"} & c.keys())
        assert set(d) == {"id","variables","constructions","conditions","target"}
        GeometryProblem.model_validate(d)
        assert len(d["variables"]) == len(set(d["variables"]))
        scope = set(d["variables"])
        for name in scope:
            assert re.fullmatch("[A-Za-z_][A-Za-z0-9_]*",name)

        def inspect(path,expression):
            nonlocal expressions
            expressions += 1
            issues,tree = _expression_issues(path,str(expression),scope)
            errors.extend(dict(id=c["id"],path=path,issue=issue.model_dump()) for issue in issues)
            assert isinstance(tree,ast.Expression),(c["id"],path)

        for i,con in enumerate(d["constructions"]):
            assert con["name"] not in scope
            inspect(f"constructions[{i}].expression",con["expression"])
            scope.add(con["name"])
        for i,cond in enumerate(d["conditions"]):
            if "predicate" in cond:
                inspect(f"conditions[{i}].predicate",cond["predicate"])
            else:
                inspect(f"conditions[{i}].left",cond["left"])
                inspect(f"conditions[{i}].right",cond["right"])
        inspect("target",d["target"])
        card = (OUT/entry["card_path"]).read_text()
        assert entry["input_sha256"] in card and entry["statement_sha256"] in card
        for kind in ("constructions","conditions"):
            assert all(f"`{kind}[{i}]`" in card for i in range(len(d[kind])))
        assert "`target`" in card and card in (OUT/"cards.md").read_text()
    for r in manifest["rows"]:
        if r["status"] != "selected_candidate":
            assert r["input_sha256"] is None and r["dsl_path"] is None and r["exclusion_reason"]
    for r in statements:
        assert sha(r["problem_statement"].encode()) == r["statement_sha256"]
    # solver結果や答えの列は読まない。旧ケースから抽出するのはID, DSL, 原文だけ。
    def signature(row,kind):
        if kind == "normalized_id": return canonical(row["id"])
        if kind == "identical_dsl_without_id": return sha(normalized_dsl(row["dsl"]))
        if kind == "alpha_ast_dsl": return alpha_dsl(row["dsl"])
        text = row.get("problem_statement")
        return statement_normalized(text) if text else None

    kinds = ["normalized_id","identical_dsl_without_id","alpha_ast_dsl","normalized_statement_without_asy"]
    overlaps, coverage = [], []
    targets = [("all_candidates_vs_"+name,cases,group) for name,group in old_groups]
    targets.append(("new_aime_vs_preserved_hmmt",[c for c in cases if c["id"].startswith("AIME-")],hmmt))
    for label, new, old in targets:
        coverage.append(dict(comparison=label,new_cases=len(new),reference_cases=len(old),
                             reference_with_statement=sum(bool(r.get("problem_statement")) for r in old)))
        for kind in kinds:
            index = defaultdict(list)
            for r in old:
                key = signature(r,kind)
                if key is not None: index[key].append(r["id"])
            for r in new:
                key = signature(r,kind)
                for existing_id in index.get(key,[]) if key is not None else []:
                    overlaps.append(dict(comparison=label,kind=kind,id=r["id"],existing_id=existing_id))
    internal = []
    for kind in kinds:
        index = defaultdict(list)
        for c in cases:
            key = signature(c,kind)
            if key is not None: index[key].append(c["id"])
        internal.extend(dict(kind=kind,ids=ids) for ids in index.values() if len(ids)>1)
    assert not any(k.startswith("geosolver.engine") for k in sys.modules)
    dedup = dict(passed=not overlaps and not internal,coverage=coverage,methods=kinds,
                 external_overlaps=overlaps,internal_overlaps=internal,
                 limitations="別名・翻訳・相似な定式化・条件並替え以上の数学的同値性は証明しない。原文なしの既存ケースもある。alpha ASTは宣言順を保持し、条件順だけを無視する。",
                 inputs={str(ROOT/p):sha((ROOT/p).read_bytes()) for p in ["benchmarks/cases.jsonl","jssa/difficulty/new2026/cases.jsonl"]},
                 solver_run=False,answer_read=False)
    (OUT/"duplicate-audit.json").write_text(json.dumps(dedup,ensure_ascii=False,indent=2)+"\n")
    report = dict(passed=not errors and dedup["passed"],cases=len(cases),aime_cases=manifest["aime_selected_count"],
                  preserved_hmmt_cases=len(hmmt),ast_expressions=expressions,existing_cases=343,
                  duplicate_audit="duplicate-audit.json",overlaps=len(overlaps)+len(internal),
                  pending_aime=31,aime_status_counts=manifest["aime_status_counts"],errors=errors,
                  solver_run=False,local_search_run=False,geometry_evaluation=False,official_answers_read=False,
                  scope="JSONモデル、AST、関数/引数/名前、カード網羅性、原文/入力/規則/旧版hash、静的重複。条件の意味・実行可能性・一意性は未検証。")
    (OUT/"validation.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if not report["passed"]: raise SystemExit(1)


if __name__ == "__main__":
    main()
