"""Bind parent-assistant full-text mathematics notes to immutable raw output."""
import argparse,json,time
from pathlib import Path
from signal_analysis import sha,write

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);ap.add_argument('--raw',type=Path,required=True);ap.add_argument('--notes',type=Path,required=True);a=ap.parse_args()
    raw=json.loads(a.raw.read_text());new=json.loads(a.notes.read_text())
    p=a.run/'math-review.json';notes=json.loads(p.read_text()) if p.exists() else []
    seen={(n['raw_file_sha256'],n['sample']) for n in notes}
    for n in new:
        r=raw[n['sample']]
        if (sha(a.raw),n['sample']) in seen:raise ValueError('already reviewed')
        n.update(id=r['id'],raw_file=str(a.raw.resolve()),raw_file_sha256=sha(a.raw),raw_text_sha256=__import__('hashlib').sha256(r['raw_text'].encode()).hexdigest(),read_characters=len(r['raw_text']),review_scope='complete raw answer read by parent assistant; not blind or independent human review',reviewed_unix=time.time())
        notes.append(n)
    write(p,notes)
if __name__=='__main__':main()
