#!/usr/bin/env python3
"""Run the isolated DSL cases on the frozen geosolver pipeline."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from fractions import Fraction
import math
import re


def _expected_parts(expected: str | list[str] | None) -> list[str]:
    if expected in (None, ""):
        return []
    if isinstance(expected, list):
        return [str(x).strip() for x in expected if str(x).strip()]
    # A semicolon is reserved in the audit map for a problem whose statement
    # explicitly has multiple possible scalar answers.  It is not used by
    # the single-answer radical parser below.
    return [part.strip() for part in str(expected).split(";") if part.strip()]


def _to_float(expected: str) -> float:
    text = str(expected).replace(" ", "")
    # Official answer ledgers sometimes use LaTeX ``\\sqrt{n}`` while the
    # JSON DSL uses the compact radical glyph.  Normalize both spellings
    # before evaluating; this does not alter any problem definition.
    text = re.sub(r"\\sqrt\{(\d+)\}", r"√\1", text)
    text = re.sub(r"sqrt\{(\d+)\}", r"√\1", text)
    # Some source ledgers use Python-style ``sqrt(33)`` rather than a LaTeX
    # radical.  Normalize that spelling through the same safe evaluator path
    # as ``√33``; this changes only answer parsing, never a DSL definition.
    text = re.sub(r"sqrt\((\d+(?:\.\d+)?)\)", r"√\1", text)
    text = text.replace("π", "pi")
    # Published answer ledgers use implicit multiplication (e.g. ``27π/40``).
    # Normalize the coefficient before ``pi`` so the safe evaluator sees
    # ``27*pi/40`` rather than attempting to call the integer 27.
    text = re.sub(r"(?<=\d)pi", "*pi", text)
    if "pi" in text:
        text = text.replace("pi", "(pi)")
        return float(eval(text, {"__builtins__": {}}, {"pi": math.pi}))
    if "∛" in text or "cbrt" in text:
        text = re.sub(r"∛(\d+(?:\.\d+)?)", r"cbrt(\1)", text)
        return float(eval(text, {"__builtins__": {}}, {"sqrt": math.sqrt, "cbrt": lambda x: x ** (1.0 / 3.0)}))
    if "√" in text:
        text = re.sub(r"(\d+(?:\.\d+)?)√(\d+(?:\.\d+)?)", r"\1*sqrt(\2)", text)
        text = re.sub(r"√(\d+(?:\.\d+)?)", r"sqrt(\1)", text)
        text = re.sub(r"(\d+(?:\.\d+)?)\(", r"\1*(", text)
        return float(eval(text, {"__builtins__": {}}, {"sqrt": math.sqrt}))
    if "/" in text:
        return float(Fraction(text))
    return float(text)


def close_to_expected(selected: str | None, expected: str | list[str] | None) -> bool | None:
    parts = _expected_parts(expected)
    if selected is None or not parts:
        return None
    for part in parts:
        try:
            target = _to_float(part)
            if abs(float(selected) - target) <= 1e-7 * max(1.0, abs(target)):
                return True
        except (ValueError, ZeroDivisionError, SyntaxError, TypeError):
            if str(selected).strip() == str(part).strip():
                return True
    return False


def answer_set_complete(accepted: list[str] | tuple[str, ...], expected: str | list[str] | None) -> bool | None:
    parts = _expected_parts(expected)
    if not parts:
        return None
    if not accepted:
        return False
    return all(any(close_to_expected(str(part), part_expected) is True for part in accepted) for part_expected in parts)


def answer_set_exact(accepted: list[str] | tuple[str, ...], expected: str | list[str] | None) -> bool | None:
    """Return whether accepted values equal the expected value set.

    ``answer_set_complete`` intentionally retains the historical *coverage*
    semantics (every expected value appears somewhere in the accepted list).
    For solver evaluation we also need to reject extra candidates, so this
    predicate checks both directions under the same numeric tolerance.
    """
    parts = _expected_parts(expected)
    if not parts:
        return None
    if not accepted:
        return False
    accepted_values = [str(value) for value in accepted]
    accepted_are_expected = all(
        any(close_to_expected(value, part) is True for part in parts)
        for value in accepted_values
    )
    expected_are_accepted = all(
        any(close_to_expected(value, part) is True for value in accepted_values)
        for part in parts
    )
    return accepted_are_expected and expected_are_accepted


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runtime-root", type=Path, required=True)
    ap.add_argument("--seeds", nargs="+", type=int, default=[7, 42, 99])
    ap.add_argument("--budget", type=float, default=30.0)
    ap.add_argument("--output", type=Path, default=Path("benchmark_results.json"))
    args = ap.parse_args()
    here = Path(__file__).resolve().parent
    cases = sorted((here / "dsl").glob("*.json"))
    audits = {}
    audit_path = here / "manual_audit.jsonl"
    if audit_path.exists():
        for line in audit_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                # Source rows may use a compact ID (notably AIME 2025),
                # while the canonical DSL filename uses the dedupe key.  All
                # three identifiers point to the same audited answer.
                keys = [row.get("problem_id"), row.get("dedupe_key")]
                dsl_path = row.get("dsl_path")
                if dsl_path:
                    keys.append(Path(dsl_path).stem)
                for key in keys:
                    if key:
                        audits[key] = row
    py = args.runtime_root / "solver/python/.venv/bin/python"
    geo = args.runtime_root / "geosolver/src"
    child = here / "benchmark_child.py"
    rows = []
    for case in cases:
        for seed in args.seeds:
            env = dict(os.environ)
            env["PYTHONPATH"] = str(geo)
            t0 = time.monotonic()
            proc = subprocess.run(
                [str(py), str(child), str(case), str(seed), str(args.budget)],
                cwd=str(args.runtime_root / "geosolver"),
                env=env,
                text=True,
                capture_output=True,
                timeout=max(90.0, args.budget * 5.0),
            )
            elapsed = time.monotonic() - t0
            payload = None
            for line in reversed(proc.stdout.splitlines()):
                try:
                    payload = json.loads(line)
                    break
                except json.JSONDecodeError:
                    continue
            if payload is None:
                payload = {"status": "runner_error", "stdout_tail": proc.stdout[-2000:], "stderr_tail": proc.stderr[-2000:]}
            expected = audits.get(case.stem, {}).get("published_answer")
            compared_answer = payload.get("reported_answer") or payload.get("selected_answer")
            payload.update({
                "case_id": case.stem,
                "seed": seed,
                "wall_sec": elapsed,
                "expected_answer": expected,
                "raw_selected_answer": payload.get("selected_answer"),
                "answer_match": close_to_expected(compared_answer, expected),
                "answer_set_complete": answer_set_complete(payload.get("accepted_answers", []), expected),
            })
            rows.append(payload)
            print(json.dumps(payload, ensure_ascii=False))
    summary = {
        "runtime_root": str(args.runtime_root),
        "seeds": args.seeds,
        "budget_sec": args.budget,
        "cases": len(cases),
        "runnable_cases": sum(not json.loads(case.read_text(encoding="utf-8")).get("solver_coverage", "").startswith("reference_only") for case in cases),
        "reference_only_cases": sum(json.loads(case.read_text(encoding="utf-8")).get("solver_coverage", "").startswith("reference_only") for case in cases),
        "runs": len(rows),
        "success_runs": sum(x.get("status") == "success" for x in rows),
        "no_solution_runs": sum(x.get("status") == "no_solution" for x in rows),
        "reference_only_runs": sum(x.get("status") == "reference_only" for x in rows),
        "exception_runs": sum(x.get("status") == "exception" for x in rows),
        "correct_runs": sum(x.get("answer_match") is True for x in rows),
        "complete_answer_set_runs": sum(x.get("answer_set_complete") is True for x in rows),
        "results": rows,
    }
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
