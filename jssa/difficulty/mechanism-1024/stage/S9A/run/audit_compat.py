"""Path coercion for a fixed read-only audit helper; no measurement or rules change."""
import hashlib,importlib.util,json
from pathlib import Path
OUT=Path(__file__).resolve().parent
record=json.loads((OUT/'audit-finalization-hashes.json').read_text())
for p,h in record['files'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h,p
spec=importlib.util.spec_from_file_location('fixed_s9a_audit',OUT/'audit.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
module.sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
module.main()
