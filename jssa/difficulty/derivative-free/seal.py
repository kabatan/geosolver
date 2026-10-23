"""Seal the preregistration before the first selected-case search."""
import datetime
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent
assert not (OUT/'prediction.lock.json').exists()
assert not (OUT/'runs').exists()
files=[p for p in OUT.rglob('*') if p.is_file() and p.suffix in {'.py','.md','.json','.csv'}]
hashes={str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
lock={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'prediction_sha256':hashes['prediction.md'],'solver_commit':'60db4b679b04167175c51c479c87c22fa663fda0','files':hashes,'environment':{n:metadata.version(n) for n in ['numpy','scipy','PyNomadBBO','sympy','mpmath']},'selected_case_searches_before_lock':0,'synthetic_only_checks_before_lock':True,'git_commit_created':False}
(OUT/'prediction.lock.json').write_text(json.dumps(lock,ensure_ascii=False,indent=2)+'\n')
print('予測固定',lock['utc'],lock['prediction_sha256'],flush=True)
