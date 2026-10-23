"""Record input hashes and check the p join without changing source data."""
from __future__ import annotations
import ast
import csv
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode=True
import numpy
import scipy
import mpmath

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]


def main():
    inputs=['benchmarks/cases.jsonl','jssa/difficulty/minima/basins-323.csv',
            'jssa/difficulty/ghost-1023/endpoints_v1.csv','jssa/difficulty/ghost-1023/human_feat.csv',
            'jssa/difficulty/holdout-1023/dsl/AIME-2020-II-15.k2.json',
            'jssa/difficulty/holdout-1023/out/AIME-2020-II-15.json']
    hashes={s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in inputs}
    for f in sorted(HERE.glob('*.py')):
        ast.parse(f.read_text())
        hashes[str(f.relative_to(ROOT))]=hashlib.sha256(f.read_bytes()).hexdigest()
    with (HERE/'joined.csv').open() as f:rows=list(csv.DictReader(f))
    mismatches=[];raw_hashes={}
    for r in rows:
        path=ROOT/'jssa/difficulty/minima/raw-323'/f"{r['id']}.json"
        content=path.read_bytes();raw=json.loads(content)
        raw_hashes[r['id']]=hashlib.sha256(content).hexdigest()
        if abs(float(r['p'])-float(raw['p_any']))>1e-12 or int(r['n_starts'])!=int(raw['starts_done']):
            mismatches.append(r['id'])
    report={'python_executable':sys.executable,'python':platform.python_version(),
            'numpy':numpy.__version__,'scipy':scipy.__version__,'mpmath':mpmath.__version__,
            'git_head_read_only':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'inputs_and_code_sha256':hashes,'raw_sha256':raw_hashes,
            'raw_p_and_trial_count_mismatches':mismatches,'n_raw_checked':len(rows),
            'note':'raw files are consulted only to audit the outcome table after feature measurement.'}
    (HERE/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    audit=json.loads((HERE/'audit.json').read_text())
    (HERE/'residual-validation.json').write_text(json.dumps(audit['residual_validation'],indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ['raw_sha256','inputs_and_code_sha256']},indent=2))
    assert not mismatches


if __name__=='__main__':main()
