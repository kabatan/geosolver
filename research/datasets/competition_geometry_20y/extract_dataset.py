#!/usr/bin/env python3
"""Build the auditable 2006--2025 competition geometry inventory.

The extractor deliberately separates keyword/round extraction from the manual
solver-scope decision. It never turns a keyword hit into a DSL case by itself.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Iterable

WINDOW = range(2006, 2026)
GEOM_RE = re.compile(
    r"\b(?:triangle|circle|angle|perpendicular|parallel|quadrilateral|polygon|"
    r"trapezoid|rectangle|square|circumcircle|circumcenter|incircle|excircle|"
    r"semicircle|tangent|area|distance|segment|rhombus|diagonal|isosceles|"
    r"equilateral|altitude|orthocenter|midpoint|radius|chord|cyclic|convex)\b",
    re.I,
)
NON_GEOM_RE = re.compile(
    r"\b(?:probability|polynomial|prime|digit|sequence|integer|remainder|"
    r"modulo|game|function|subset|permutation|graph|base|divisor|factorial)\b",
    re.I,
)
JMO_GEOM_RE = re.compile(
    r"(三角形|四角形|五角形|六角形|円|角|垂直|平行|面積|長さ|台形|"
    r"正方形|正三角形|内接|外接|circum|triangle|circle|angle|perpendicular|"
    r"parallel|quadrilateral|polygon|trapezoid|rectangle|square|area|distance)",
    re.I,
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def clean_statement(text: str) -> str:
    lines = []
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw.replace("\f", " ")).strip()
        if not line or re.fullmatch(r"\d+", line):
            continue
        lines.append(line)
    return " ".join(lines).strip()


def load_aime(csv_path: Path, aime_2025: Path | None) -> list[dict]:
    records = []
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            year = int(row["Year"])
            if year not in WINDOW:
                continue
            statement = row["Question"].strip()
            if not GEOM_RE.search(statement):
                continue
            mixed = bool(NON_GEOM_RE.search(statement))
            records.append(
                {
                    "problem_id": f"AIME-{year}-{row.get('Part', 'I')}-{int(row['Problem Number']):02d}",
                    "contest": "AIME",
                    "year": year,
                    "round": row.get("Part", ""),
                    "source_kind": "AIME-CSV",
                    "source_url": "https://huggingface.co/datasets/gneubig/aime-1983-2024/resolve/main/AIME_Dataset_1983_2024.csv",
                    "statement": statement,
                    "answer": row.get("Answer", ""),
                    "topic_evidence": "keyword:" + ",".join(sorted(set(m.group(0).lower() for m in GEOM_RE.finditer(statement)))),
                    "extraction_status": "geometry_candidate_mixed_terms" if mixed else "geometry_candidate",
                    "scope_status": "needs_manual_review",
                    "scope_reason": "keyword extraction only; no DSL is inferred automatically",
                }
            )
    if aime_2025 and aime_2025.exists():
        payload = json.loads(aime_2025.read_text(encoding="utf-8"))
        rows = payload.get("rows", payload if isinstance(payload, list) else [])
        for pos, wrapped in enumerate(rows):
            row = wrapped.get("row", wrapped)
            statement = (row.get("problem") or row.get("Question") or "").strip()
            if not statement or not GEOM_RE.search(statement):
                continue
            idx = int(row.get("id", pos))
            part = "I" if idx < 15 else "II"
            records.append(
                {
                    "problem_id": f"2025-{part}-{idx % 15 + 1}",
                    "contest": "AIME",
                    "year": 2025,
                    "round": part,
                    "source_kind": "AIME-2025-rows",
                    "source_url": row.get("url", "https://datasets-server.huggingface.co/rows?dataset=yentinglin%2Faime_2025&config=default&split=train&offset=0&length=100"),
                    "statement": statement,
                    "answer": str(row.get("answer", "")),
                    "topic_evidence": "keyword:" + ",".join(sorted(set(m.group(0).lower() for m in GEOM_RE.finditer(statement)))),
                    "extraction_status": "geometry_candidate",
                    "scope_status": "needs_manual_review",
                    "scope_reason": "keyword extraction only; no DSL is inferred automatically",
                }
            )
    return records


def split_hmmt(text: str) -> list[tuple[int, str]]:
    starts = list(re.finditer(r"(?m)^\s*(\d{1,2})\s*\.\s+", text.replace("\f", "\n")))
    out = []
    for i, match in enumerate(starts):
        number = int(match.group(1))
        if number < 1 or number > 20:
            continue
        end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        body = clean_statement(text[match.end():end])
        if body:
            out.append((number, body))
    seen = set()
    return [(n, b) for n, b in out if not (n in seen or seen.add(n))]


def load_hmmt(hmmt_dir: Path) -> list[dict]:
    records = []
    for path in sorted(hmmt_dir.glob("*_feb_*.txt")):
        match = re.match(r"(\d{4})_feb_(.+)\.txt", path.name)
        if not match or int(match.group(1)) not in WINDOW:
            continue
        year = int(match.group(1))
        flavor = match.group(2)
        dedicated = flavor == "geo"
        for number, statement in split_hmmt(path.read_text(encoding="utf-8", errors="replace")):
            if not dedicated and not GEOM_RE.search(statement):
                continue
            records.append(
                {
                    "problem_id": f"HMMT-{year}-FEB-{flavor.upper()}-{number:02d}",
                    "contest": "HMMT",
                    "year": year,
                    "round": f"February {flavor}",
                    "source_kind": "HMMT-official-PDF-text",
                    "source_url": f"https://hmmt-archive.s3.amazonaws.com/tournaments/{year}/feb/{flavor}/problems.pdf",
                    "statement": statement,
                    "answer": None,
                    "topic_evidence": "dedicated Geometry Round" if dedicated else f"keyword:{flavor}",
                    "extraction_status": "geometry_round" if dedicated else "theme_round_geometry_candidate",
                    "scope_status": "needs_manual_review",
                    "scope_reason": "round extraction; finite-configuration and branch audit pending",
                }
            )
    return records


def infer_jmo_year(competition: str) -> int | None:
    m = re.search(r"20(0[6-9]|1[0-9]|2[0-5])", competition)
    if m:
        return int(m.group(0))
    m = re.search(r"(16|17|18|19|20|21|22|23|24|25)(?:th|st|nd|rd)", competition, re.I)
    if m:
        return 1990 + int(m.group(1))
    return None


def load_jmo(rows_path: Path | None) -> list[dict]:
    if not rows_path or not rows_path.exists():
        return []
    records = []
    for line in rows_path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        competition = str(row.get("competition", ""))
        year = row.get("year") or infer_jmo_year(competition)
        if year not in WINDOW:
            continue
        statement = str(row.get("problem", "")).strip()
        if not statement or not JMO_GEOM_RE.search(statement):
            continue
        records.append(
            {
                "problem_id": f"JMO-{year}-MATHNET-{row.get('mathnet_id', len(records))}",
                "contest": "JMO preliminary",
                "year": year,
                "round": competition,
                "source_kind": "MathNet-supplement",
                "source_url": "https://huggingface.co/datasets/LLParallax/MathNet-filtered",
                "statement": statement,
                "answer": row.get("answer"),
                "topic_evidence": "MathNet topic/keyword geometry",
                "extraction_status": "geometry_candidate",
                "scope_status": "needs_manual_review",
                "scope_reason": "official wording/source-image cross-check pending",
            }
        )
    return records


def official_jmo_placeholders() -> list[dict]:
    """Keep image-only official years visible without inventing their text."""
    return [
        {
            "problem_id": f"JMO-{year}-OFFICIAL-LINKS",
            "contest": "JMO preliminary",
            "year": year,
            "round": "official annual page",
            "source_kind": "JMO-official-index",
            "source_url": "https://www.imojp.org/domestic/jmo_overview.html",
            "statement": "",
            "answer": None,
            "topic_evidence": "official annual link; individual page may be image-only",
            "extraction_status": "image_only_or_manual_review",
            "scope_status": "needs_manual_review",
            "scope_reason": "no OCR or guessed wording; retrieve official scan before DSL authoring",
        }
        for year in WINDOW
    ]


def write_jsonl(path: Path, records: Iterable[dict]) -> list[dict]:
    rows = list(records)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aime-csv", type=Path, required=True)
    ap.add_argument("--aime-2025-json", type=Path)
    ap.add_argument("--hmmt-dir", type=Path, required=True)
    ap.add_argument("--jmo-rows", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    aime = load_aime(args.aime_csv, args.aime_2025_json)
    hmmt = load_hmmt(args.hmmt_dir)
    jmo = load_jmo(args.jmo_rows)
    official = official_jmo_placeholders()
    write_jsonl(args.output / "aime_geometry.jsonl", aime)
    write_jsonl(args.output / "hmmt_geometry.jsonl", hmmt)
    write_jsonl(args.output / "jmo_geometry.jsonl", jmo + official)
    all_rows = aime + hmmt + jmo + official
    write_jsonl(args.output / "all_geometry.jsonl", all_rows)
    scope = [
        {
            "problem_id": row["problem_id"],
            "contest": row["contest"],
            "year": row["year"],
            "scope_status": row["scope_status"],
            "scope_reason": row["scope_reason"],
            "dsl_path": None,
        }
        for row in all_rows
    ]
    write_jsonl(args.output / "scope_inventory.jsonl", scope)
    manifest_path = args.output / "source_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"sources": []}
    local_inputs = []
    for p in [args.aime_csv, args.aime_2025_json, args.jmo_rows]:
        if p and p.exists():
            local_inputs.append({"path": str(p), "sha256": sha256(p), "bytes": p.stat().st_size})
    for p in sorted(args.hmmt_dir.glob("*.txt")):
        local_inputs.append({"path": str(p), "sha256": sha256(p), "bytes": p.stat().st_size})
    manifest["local_inputs"] = local_inputs
    manifest["generated_at"] = date.today().isoformat()
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "window": [2006, 2025],
        "counts": {
            "aime_geometry_candidates": len(aime),
            "hmmt_geometry_round_or_candidates": len(hmmt),
            "jmo_text_geometry_candidates": len(jmo),
            "jmo_official_year_placeholders": len(official),
            "all_records": len(all_rows),
        },
        "scope_count_from_static_inventory": sum(1 for x in scope if x["scope_status"] == "in_scope"),
        "notes": [
            "Keyword/round extraction and finite-scope auditing are intentionally separate.",
            "Image-only JMO years are visible but not counted as confirmed scope cases.",
        ],
    }
    (args.output / "extraction_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
