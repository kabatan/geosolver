"""Build English, numeric-only candidate prompts without opening private cases."""
import argparse
import hashlib
import json
import runpy
import string
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PREVIOUS = HERE.parent / "answer-opd-pilot-2026-09-26"
TEMPLATES_PATH = HERE.parent / "qwen35-diverse-sft-2026-09-24/english_templates.py"
TEMPLATES = runpy.run_path(str(TEMPLATES_PATH))["NUMERIC_EN"]
SOURCES = ("H01", "H04", "H07", "H13", "H14", "H15", "DA01", "DA05")
MODULES = "math, cmath, statistics, fractions, decimal, itertools, functools"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def slots(source):
    return sorted({key for _, key, _, _ in string.Formatter().parse(TEMPLATES[source]) if key})


def specification(source):
    return TEMPLATES[source].format(**{k: f'givens["{k}"]' for k in slots(source)})


def program_prompt(source, examples=()):
    prompt = (
        "Write a reusable Python function solve(givens) for the geometry task below. "
        "The input is a dictionary of real-valued numerical givens; the output must be "
        "one finite real number for the requested quantity. It must work for every "
        "nondegenerate configuration satisfying the stated assumptions, including "
        "new numerical conditions. Derive a procedure from the geometry; do not "
        "hard-code a table of examples.\n\n"
        + specification(source)
        + "\n\nThe dictionary has exactly these fields: "
        + ", ".join(slots(source))
        + ". Inputs and reference values use ordinary floating-point precision. "
        "Accuracy is checked with absolute tolerance 1e-7 plus relative tolerance 1e-6.\n"
        f"You may use ordinary Python and these standard numerical modules: {MODULES}. "
        "You have no geometry solver, external data, files, network, or other packages. "
        "General numerical algorithms and ordinary control flow are permitted. "
        "Do not use reflection, double-underscore attributes, eval, exec, or dynamic imports.\n"
        "Return one closed Python code block containing the complete program and "
        "a top-level def solve(givens). Do not print results or read input; the evaluator "
        "calls solve. Return code only, without comments, docstrings, proofs or prose."
    )
    if examples:
        prompt += "\n\nObserved numerical examples (not an exhaustive test set):\n"
        prompt += "\n".join(json.dumps({"givens": x["givens"], "output": x["answer"]},
                                     ensure_ascii=False, sort_keys=True) for x in examples)
    return prompt


def numeric_prompt(source, givens):
    statement = TEMPLATES[source].format(**{k: format(givens[k], ".17g") for k in slots(source)})
    return ("Solve the following numerical geometry problem. Give only the requested "
            "numerical value, with at least 10 significant digits when appropriate. "
            "Do not give a proof or explanation.\n\n" + statement)


def setup(args):
    path = Path(args.cases_public).resolve()
    rows = [json.loads(s) for s in path.read_text().splitlines() if s.strip()]
    assert len(rows) == 64 and {x["source_id"] for x in rows} == set(SOURCES)
    assert len({x["case_id"] for x in rows}) == len(rows)
    assert all("private_witness" not in x for x in rows)
    assert all(x["split"] in ("visible", "repair") for x in rows)
    jobs, probes = [], []
    for index, source in enumerate(SOURCES):
        visible = [x for x in rows if x["source_id"] == source and x["split"] == "visible"]
        repair = [x for x in rows if x["source_id"] == source and x["split"] == "repair"]
        assert len(visible) == len(repair) == 4
        assert all(set(x["givens"]) == set(slots(source)) for x in visible + repair)
        jobs.append({"id": f"candidate-{source.lower()}", "source_id": source,
                     "seed": 2026092700 + index, "evaluation_role": "program_candidate_collection",
                     "messages": [{"role": "user", "content": program_prompt(source, visible)}]})
        probes.append({"id": f"program-probe-{source.lower()}", "source_id": source,
                       "seed": 2026092700 + index, "evaluation_role": "program_without_examples",
                       "messages": [{"role": "user", "content": program_prompt(source)}]})
    write(HERE / "candidate-jobs.json", jobs)
    write(HERE / "program-probe-jobs.json", probes)
    for name in ("eval-jobs.json", "eval-answer-key.json", "GRADING.md"):
        (HERE / name).write_bytes((PREVIOUS / name).read_bytes())
    receipt = {"status": "prepared_before_generation", "sources": list(SOURCES),
               "candidate_prompts": 8, "samples_per_prompt": 4, "max_repair_per_candidate": 1,
               "public_case_file": str(path), "public_case_sha256": digest(path),
               "english_template_sha256": digest(TEMPLATES_PATH),
               "files": {name: digest(HERE / name) for name in
                         ("PROTOCOL.md", "prepare.py", "candidate-jobs.json", "program-probe-jobs.json",
                          "eval-jobs.json", "eval-answer-key.json", "GRADING.md")}}
    write(HERE / "prompt-freeze.json", receipt)
    print(json.dumps({"status": receipt["status"], "candidate_jobs": len(jobs), "public_cases": len(rows)}))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases-public", required=True)
    setup(ap.parse_args())
