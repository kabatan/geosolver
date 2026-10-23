"""Losslessly compress generated complete-solver evidence; no measurements change."""
import gzip
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

OUT=Path(__file__).resolve().parent
rows=[]
for folder in ('full','full-mp','full-recheck'):
    for p in sorted((OUT/folder).rglob('*.json')):
        raw=p.read_bytes(); packed=gzip.compress(raw,compresslevel=9,mtime=0)
        assert len(raw)<5_000_000 and len(packed)<5_000_000
        dst=Path(str(p)+'.gz')
        if dst.exists():assert gzip.decompress(dst.read_bytes())==raw
        else:dst.write_bytes(packed)
        assert gzip.decompress(dst.read_bytes())==raw
        rows.append({'path':str(dst.relative_to(OUT)),'uncompressed_bytes':len(raw),
            'compressed_bytes':len(packed),'uncompressed_sha256':hashlib.sha256(raw).hexdigest()})
        p.unlink()  # Only our generated file, after exact round-trip verification.
if rows:
    (OUT/'compression.json').write_text(json.dumps({'utc':datetime.now(timezone.utc).isoformat(),
        'files':rows,'raw_bytes':sum(r['uncompressed_bytes'] for r in rows),
        'gzip_bytes':sum(r['compressed_bytes'] for r in rows)},indent=2)+'\n')
print('compressed',len(rows),'files',sum(r['uncompressed_bytes'] for r in rows),
      '->',sum(r['compressed_bytes'] for r in rows),'bytes')
