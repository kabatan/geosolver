"""Deterministic, output-only DSL rewrite. Does not call a solver."""
from __future__ import annotations

import ast
import copy
import csv
import datetime as dt
import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORPUS = HERE.parents[1]
ROOT = HERE.parents[4]
FROZEN = "60db4b679b04167175c51c479c87c22fa663fda0"
IDS = ["AIME-1983-12", "AIME-1985-09", "AIME-1991-12", "AIME-1995-09",
       "AIME-1996-13", "AIME-1996-15", "AIME-1997-04",
       "HMMT-2022-FEB-GEO-07", "HMMT-2023-FEB-GEO-06"]
REFERENCES = {
    "AIME-1983-12": ("65", "identity"),
    "AIME-1985-09": ("17/32", "numerator_plus_denominator"),
    "AIME-1991-12": ("672/5", "numerator_plus_denominator"),
    "AIME-1995-09": ("11+sqrt(605)", "integer_plus_sqrt"),
    "AIME-1996-13": ("27/38", "numerator_plus_denominator"),
    "AIME-1996-15": ("7/9", "floor_1000"),
    "AIME-1997-04": ("8/9", "numerator_plus_denominator"),
    "HMMT-2022-FEB-GEO-07": ("169/2", "100_numerator_plus_denominator"),
    "HMMT-2023-FEB-GEO-06": ("17*pi/45", "radians_to_degrees"),
    "AIME-1991-14": ("384", "identity"),
}

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")

def names(expression):
    return {n.id for n in ast.walk(ast.parse(str(expression), mode="eval")) if isinstance(n, ast.Name)}

def rewrite(dsl):
    out = copy.deepcopy(dsl)
    cid = dsl["id"]
    remove = set()
    binding = None
    if cid == "AIME-1983-12":
        assert dsl["target"] == "Distance(A, B)"
    elif cid == "AIME-1996-15":
        assert dsl["target"] == "(1000*r) // 1"
        out["target"] = "r"
    else:
        if dsl["target"] == "m+n":
            remove, form = {"m", "n", "u", "v"}, "m/n"
        elif dsl["target"] == "a+b":
            remove, form = {"a", "b"}, "a+sqrt(b)"
        elif dsl["target"] == "100*a+b":
            remove, form = {"a", "b", "h", "k"}, "a/b"
        elif dsl["target"] == "n":
            remove, form = {"n"}, "n*pi/180"
        else:
            raise ValueError(cid)
        bindings = [(i,c) for i,c in enumerate(dsl["conditions"])
                    if c["operator"] == "=" and c["right"] == form]
        assert len(bindings) == 1
        binding, condition = bindings[0]
        out["target"] = condition["left"]
    removed = [i for i,c in enumerate(dsl["conditions"])
               if (names(c["left"]) | names(c["right"])) & remove]
    if binding is not None:
        assert binding in removed
        assert not names(out["target"]) & remove
    out["conditions"] = [c for i,c in enumerate(dsl["conditions"]) if i not in removed]
    out["variables"] = [v for v in dsl["variables"] if v not in remove]
    assert out["constructions"] == dsl["constructions"]
    for c in out["constructions"]:
        assert not names(c["expression"]) & remove
    assert {k:v for k,v in out.items() if k not in {"conditions","variables","target"}} == {
        k:v for k,v in dsl.items() if k not in {"conditions","variables","target"}}
    return out, removed, sorted(remove), binding

def main():
    assert not (HERE / "prediction.lock.json").exists(), "Preparation is closed after prediction lock"
    rule_lock = HERE / "rules.lock.json"
    if not rule_lock.exists():
        save(rule_lock, {"sha256": sha(HERE / "rewrite-rules.md"), "created_at_utc": now(),
                         "rule_written_before_any_rewrite": True})
    assert json.loads(rule_lock.read_text())["sha256"] == sha(HERE / "rewrite-rules.md")
    (HERE / "dsl").mkdir(exist_ok=True)
    (HERE / "diff").mkdir(exist_ok=True)
    manifest, cases = [], []
    audit = {r["id"]: r for r in csv.DictReader((CORPUS / "audit/audit.csv").open())}
    refs = {}
    for cid in IDS:
        source = CORPUS / "dsl" / (cid + ".json")
        before = source.read_text()
        original = json.loads(before)
        changed, removed, variables, binding = rewrite(original)
        after = before if changed == original else json.dumps(changed, ensure_ascii=False, indent=2) + "\n"
        path = HERE / "dsl" / source.name
        path.write_text(after)
        diff = "".join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),
                      fromfile="original/"+source.name,tofile="posthoc/"+source.name))
        (HERE / "diff" / (cid+".diff")).write_text(diff)
        manifest.append({"id":cid,"changed":bool(diff),"original_sha256":sha(source),
                         "rewritten_sha256":sha(path),"removed_variables":variables,
                         "binding_condition_index_zero_based":binding,
                         "removed_condition_indices_zero_based":removed,
                         "removed_conditions":[original["conditions"][i] for i in removed],
                         "old_target":original["target"],"new_target":changed["target"],
                         "all_remaining_conditions_and_constructions_identical":True,
                         "no_op_reason":"intrinsic digit and rationality constraints" if not diff else None})
        cases.append({"id":cid,"dsl_path":"dsl/"+source.name,"dsl":changed,
                      "source":"Q29d post-hoc output normalization","authoring_status":"runnable"})
    for cid,(value,conversion) in REFERENCES.items():
        a = audit[cid]
        refs[cid] = {"geometric_value":value,"output_conversion":conversion,
                     "official_output":str(int(a["primary_answer"])),
                     "answer_source_file":a["primary_answer_file"],
                     "answer_source_locator":a["primary_answer_locator"],
                     "answer_source_sha256":a["primary_answer_sha256"],
                     "answer_source_url":a["primary_answer_url"]}
    save(HERE / "rewrite-manifest.json", manifest)
    save(HERE / "references.json", refs)
    (HERE / "cases.jsonl").write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in cases))
    save(HERE / "source-inputs.json", {"frozen_commit":FROZEN,"created_at_utc":now(),
        "original_dsl_sha256":{cid:sha(CORPUS/"dsl"/(cid+".json")) for cid in REFERENCES},
        "q19_assessment_sha256":sha(CORPUS/"prereg/q19-scored/assessment.jsonl"),
        "development_cases_sha256":sha(ROOT/"benchmarks/cases.jsonl"),
        "new2026_cases_sha256":sha(ROOT/"jssa/difficulty/new2026/cases.jsonl")})
    print(json.dumps({"cases":len(cases),"changed":sum(r["changed"] for r in manifest),
                      "rule_sha256":sha(HERE/"rewrite-rules.md")}))

if __name__ == "__main__":
    main()
