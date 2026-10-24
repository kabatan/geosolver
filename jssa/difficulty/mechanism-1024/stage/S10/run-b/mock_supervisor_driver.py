"""Contract fixture ONLY. Writes synthetic receipts; never imports geosolver/driver."""
import json
from pathlib import Path
import sys
out=Path(sys.argv[2]);mode=sys.argv[1]
if mode=='run':
    (out/'receipts').mkdir()
    (out/'measurement-freeze.json').write_text(json.dumps(dict(jobs=[0,1])))
    (out/'receipts/0000.start.json').write_text('{"mock":true}')
    raise SystemExit(9)
if mode=='resume':
    assert (out/'receipts/0000.start.json').exists()
    (out/'receipts/0000.end.json').write_text('{"state":"interrupted_prior_start_no_retry"}')
    (out/'receipts/0001.end.json').write_text('{"state":"completed"}')
    raise SystemExit(0)
if mode=='grade':
    (out/'mock-grade-only.json').write_text('{"mock":true,"solver_calls":0}')
    raise SystemExit(0)
raise SystemExit(99)
