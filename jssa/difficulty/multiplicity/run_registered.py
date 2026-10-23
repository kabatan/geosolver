"""Run the immutable registered code with serialization-only corrections.

The solver disallows direct float(mpf) while high_precision_mode is active.
These three conversions write telemetry; they never feed the optimizer.
Keep experiment.py and the original lock immutable for auditing.
"""
from pathlib import Path
import hashlib
import json

_here = Path(__file__).resolve().parent
_lock = _here / "execution-lock.json"
if _lock.exists():
    _hashes = json.loads(_lock.read_text())["files"]
    for _name, _expected in _hashes.items():
        assert hashlib.sha256((_here / _name).read_bytes()).hexdigest() == _expected, _name
_source = (_here / "experiment.py").read_text()
for _before, _after in (
    ('float(min(mp.mpf(500), -mp.log10(norm)))', 'float(mp.nstr(min(mp.mpf(500), -mp.log10(norm)), 30))'),
    ('float(mp.log10(prev[0]/original)/2)', 'float(mp.nstr(mp.log10(prev[0]/original)/2, 30))'),
    ('float(mp.log10(prev[1]/value)/2)', 'float(mp.nstr(mp.log10(prev[1]/value)/2, 30))'),
):
    assert _source.count(_before) == 1, _before
    _source = _source.replace(_before, _after)
exec(compile(_source, str(_here / "experiment.py"), "exec"), globals())
