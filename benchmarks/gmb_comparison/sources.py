"""Retrieve the public original statements; never run either geometry solver."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import urllib.request
from pathlib import Path

UPSTREAM_COMMIT = "f070afe18ed874b3a31db519ea6f593f40a1be00"
DEFAULT_ASSETS = Path(
    "/home/kabatan/work/solver-research-assets/gmb-comparison-source-materials/imo"
)
HERE = Path(__file__).resolve().parent
DEFAULT_UPSTREAM = HERE.parent / "gmb/.runtime/source"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def retrieve_pdf(url: str, pdf: Path, txt: Path) -> None:
    if not pdf.exists():
        request = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (research source retrieval)"}
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            content = response.read(10_000_001)
        if not content.startswith(b"%PDF-") or len(content) > 10_000_000:
            raise ValueError(f"Not a bounded PDF response: {url}")
        with tempfile.NamedTemporaryFile(dir=pdf.parent, delete=False) as temporary:
            temporary.write(content)
            pending = Path(temporary.name)
        pending.replace(pdf)
    if not pdf.read_bytes().startswith(b"%PDF-"):
        raise ValueError(f"Invalid stored PDF: {pdf}")
    if not txt.exists():
        subprocess.run(["pdftotext", "-layout", str(pdf), str(txt)], check=True, timeout=30)


def retrieve(assets: Path, upstream: Path) -> dict:
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=upstream, text=True
    ).strip()
    if revision != UPSTREAM_COMMIT:
        raise ValueError(f"Unexpected GMB revision: {revision}")
    inputs = sorted((upstream / "problems/IMO").glob("*.smt2"))
    if len(inputs) != 36:
        raise ValueError(f"Expected 36 original inputs, found {len(inputs)}")
    years = sorted({int(path.stem.split("_")[1]) for path in inputs})
    assets.mkdir(parents=True, exist_ok=True)
    statements = {}
    for year in years:
        url = f"https://www.imo-official.org/assets/documents/problems/{year}/{year}_eng.pdf"
        pdf = assets / f"{year}-eng.pdf"
        txt = assets / f"{year}-eng.txt"
        retrieve_pdf(url, pdf, txt)
        statements[str(year)] = {
            "official_page": f"https://www.imo-official.org/problems/{year}/",
            "url": url,
            "pdf_filename": pdf.name,
            "pdf_sha256": sha256(pdf),
            "text_filename": txt.name,
            "text_sha256": sha256(txt),
        }
        print(f"{year}: {statements[str(year)]['pdf_sha256']}", flush=True)
    uk_url = "https://www.imo-register.org.uk/2000-report.pdf"
    uk_pdf, uk_txt = assets / "2000-uk-report.pdf", assets / "2000-uk-report.txt"
    retrieve_pdf(uk_url, uk_pdf, uk_txt)
    return {
        "schema_version": 1,
        "gmb_commit": UPSTREAM_COMMIT,
        "asset_directory": str(assets.resolve()),
        "statements": statements,
        "supplementary_statements": {
            "2000-uk-team-leader-report": {
                "url": uk_url,
                "author": "Imre Leader (UK Team Leader)",
                "problem_statement_page": 4,
                "pdf_filename": uk_pdf.name,
                "pdf_sha256": sha256(uk_pdf),
                "text_filename": uk_txt.name,
                "text_sha256": sha256(uk_txt),
                "reason": (
                    "Clarifies support lines and near-M tangent branch omitted in shortened wording"
                ),
            }
        },
        "inputs": [
            {
                "case_id": path.stem,
                "gmbl_relative_path": str(path.relative_to(upstream)),
                "gmbl_sha256": sha256(path),
                "year": int(path.stem.split("_")[1]),
            }
            for path in inputs
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, default=DEFAULT_ASSETS)
    parser.add_argument("--upstream", type=Path, default=DEFAULT_UPSTREAM)
    parser.add_argument("--manifest", type=Path, default=HERE / "source-manifest.json")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Regenerate this preparation catalog, never overwrite original PDFs",
    )
    args = parser.parse_args()
    result = retrieve(args.assets, args.upstream)
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.manifest.exists() and not args.refresh:
        if args.manifest.read_text() != encoded:
            raise ValueError("Existing source manifest differs; do not overwrite evidence")
    else:
        args.manifest.write_text(encoded)


if __name__ == "__main__":
    main()
