"""Fetch primary HMMT PDFs, serially, with a strict per-file size cap. No solver."""
from __future__ import annotations
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
CACHE = Path('/tmp/q30b-hmmt-source')
LIMIT = 5_000_000

def fetch(year, section, kind, ingest=False):
    name = f'{year}-{section}-{kind}'
    url = f'https://hmmt-archive.s3.amazonaws.com/tournaments/{year}/feb/{section}/{kind}.pdf'
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / (name + '.pdf')
    meta = CACHE / (name + '.source.json')
    if not meta.exists():
        if not ingest:
            subprocess.run(['curl', '-sS', '-L', '--fail', '--max-filesize', str(LIMIT-1),
                            '--connect-timeout', '8', '--max-time', '20', url, '-o', str(path)], check=True, timeout=22)
        assert path.stat().st_size < LIMIT and path.read_bytes().startswith(b'%PDF')
        subprocess.run(['pdftotext', '-layout', str(path), str(path.with_suffix('.txt'))], check=True, timeout=5)
        meta.write_text(json.dumps(dict(url=url, retrieved_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(), bytes=path.stat().st_size), indent=2)+'\n')
    print(name, path.stat().st_size, flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('section')
    parser.add_argument('kind', choices=['problems','solutions'])
    parser.add_argument('year', type=int)
    parser.add_argument('--ingest', action='store_true', help='Record a PDF just fetched by the approved curl command')
    args = parser.parse_args()
    fetch(args.year, args.section, args.kind, args.ingest)
