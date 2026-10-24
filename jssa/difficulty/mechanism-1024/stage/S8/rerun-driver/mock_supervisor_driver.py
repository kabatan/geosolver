"""Synthetic crash/resume fixture; never imports solver."""
import sys
from pathlib import Path
from measurement_common import save

mode=sys.argv[1];out=Path(sys.argv[2]);out.mkdir(exist_ok=True)
if mode=='run':
    (out/'receipts').mkdir()
    save(out/'measurement-freeze.json',dict(jobs=[dict(queue_index=0),dict(queue_index=1)]))
    save(out/'receipts/0000.start.json',dict(queue_index=0))
    sys.exit(9)
if mode=='resume':
    assert (out/'receipts/0000.start.json').exists()
    save(out/'receipts/0000.end.json',dict(queue_index=0,state='interrupted_prior_start_no_retry'))
    save(out/'receipts/0001.start.json',dict(queue_index=1))
    save(out/'receipts/0001.end.json',dict(queue_index=1,state='completed'))
else:
    save(out/'mock-grade-only.json',dict(mock=True))
