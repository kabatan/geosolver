"""Archive already-downloaded official PDFs. Offline; no solver or network."""
from __future__ import annotations

import datetime
import hashlib
import json
import re
import shutil
from pathlib import Path

from source_plan import SELECTED, identifier

HERE = Path(__file__).resolve().parent
CACHE = Path('/tmp/q30b-hmmt-source')


def main():
    assert not (HERE / 'prediction.lock.json').exists(), 'Prediction already locked'
    out = HERE / 'source-evidence'
    out.mkdir(exist_ok=True)
    records = []
    for year, section, number, reference, official, conversion in SELECTED:
        record = dict(id=identifier(year, section, number), geometric_reference=reference,
                      official_output=official, output_conversion=conversion, sources=[])
        for kind in ('problems', 'solutions'):
            stem = f'{year}-{section}-{kind}'
            pdf = CACHE / f'{stem}.pdf'
            meta = json.loads((CACHE / f'{stem}.source.json').read_text())
            assert pdf.stat().st_size < 5_000_000
            assert hashlib.sha256(pdf.read_bytes()).hexdigest() == meta['sha256']
            for suffix in ('.pdf', '.txt', '.source.json'):
                shutil.copyfile(CACHE / (stem + suffix), out / (stem + suffix))
            text = (CACHE / f'{stem}.txt').read_text().replace('\f', '\f\n')
            match = re.search(rf'(?m)^[ \t]*{number}\.\s', text)
            assert match, (stem, number)
            following = re.search(rf'(?m)^[ \t]*{number+1}\.\s', text[match.end():])
            end = match.end() + following.start() if following else len(text)
            start_page = text[:match.start()].count('\f') + 1
            # Keep the complete solution, including a continuation page if any.
            last_nonempty = len(text[:end].rstrip())
            end_page = text[:last_nonempty].count('\f') + 1
            excerpt_path = f'{record["id"]}-{kind}-excerpt.txt'
            (out / excerpt_path).write_text(text[match.start():end])
            record['sources'].append(dict(kind=kind, **meta, pdf=f'{stem}.pdf',
                pages=list(range(start_page, end_page + 1)), excerpt=excerpt_path,
                provenance='Existing local download and its original retrieval metadata; offline copy, unchanged PDF bytes'))
        records.append(record)
    (out / 'manifest.json').write_text(json.dumps(dict(
        archived_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        network_used_this_task=False, original_cache=str(CACHE), records=records),
        ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'sources': 2 * len(records), 'cases': len(records),
                      'network_used': False, 'solver_executed': False}))


if __name__ == '__main__':
    main()
