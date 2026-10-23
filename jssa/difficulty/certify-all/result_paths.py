"""Resolve the predeclared infrastructure recovery, without best-result selection."""
from pathlib import Path
import json

HERE=Path(__file__).resolve().parent


def result_path(cid):
    second=HERE/"recovery2-plan.json"
    if second.exists() and cid in json.loads(second.read_text())["ids"]:
        p=HERE/"recovery2"/cid/"result.json"
        if p.exists():return p
    plan=HERE/"recovery-plan.json"
    if plan.exists():
        ids=json.loads(plan.read_text())["ids"]
        if cid in ids and (HERE/"recovery"/cid/"result.json").exists():
            return HERE/"recovery"/cid/"result.json"
    return HERE/"runs"/cid/"result.json"


def results():
    manifest=json.loads((HERE/"input-manifest.json").read_text())
    for row in manifest["cases"]:
        p=result_path(row["id"])
        if p.exists():yield p
