"""Freeze preregistration-12 stage (2), using immutable stage (1) classifications."""
import csv
import hashlib
import json
import os
import platform
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

OUT=Path(__file__).resolve().parent
S5=OUT.parent
STAGE=S5.parent
REPO=OUT.parents[5]
sys.dont_write_bytecode=True
sys.path.insert(0,'/tmp/s3-impl/src')
from geosolver.runtime.integrity import source_tree_hash, installed_dependencies

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def treehash(root):
    h=hashlib.sha256()
    for p in sorted((root/'geosolver').rglob('*')):
        if p.is_file() and p.suffix in {'.py','.json','.toml'} and p.name!='engine-lock.json' and '__pycache__' not in p.parts and 'frontend' not in p.parts:
            h.update(str(p.relative_to(root/'geosolver')).encode()+b'\0'+p.read_bytes().replace(b'\r\n',b'\n')+b'\0')
    return 'sha256:'+h.hexdigest()

assert not (OUT/'pre-run-hashes.json').exists()
OLD=json.loads((STAGE/'S3/run/pre-run-hashes.json').read_text())
SRC=Path('/tmp/s3-impl/src');FROZEN=Path(OLD['frozen_origin'])
assert source_tree_hash()==OLD['source_hash']=='sha256:add5afaf829806ca3cbd11fb07b69d956102752e1c6738b0630581a3ceb121eb'
assert treehash(FROZEN)==OLD['frozen_source_hash']
for name,expected in json.loads((STAGE/'S3/impl-hashes.json').read_text())['implementation_files_sha256'].items():
    assert sha(SRC/name)==expected,name
classes=list(csv.DictReader((S5/'classification.csv').open()))
targets=json.loads((S5/'targets.json').read_text())['targets']
assert len(targets)==len(classes)==32
by_id={r['case_id']:r for r in classes}
assert set(by_id)=={t['case_id'] for t in targets}
ROOT=Path(tempfile.mkdtemp(prefix='mechanism-S5-'))
tasks=[];files=set(OUT.glob('*.py'))|{OUT/'rules.md',S5/'classification.csv',S5/'targets.json',STAGE/'S3/preregistration-12.md',STAGE/'S3/rules.md',STAGE/'S3/impl-hashes.json'}
files |= set((STAGE/'S3/run').glob('*.py'))|{STAGE/'S1/worker.py',STAGE/'S1/pre-run-hashes.json',STAGE/'S5/pre-run-hashes.json'}
for i,t in enumerate(targets):
    c=by_id[t['case_id']];p=REPO/t['dsl_path'];assert sha(p)==t['sha256']==c['dsl_sha256']
    inp=S5/'inputs'/(t['case_id']+'.json');meta=json.loads(inp.read_text());files.update([p,inp])
    d=ROOT/'runs'/t['case_id'];d.mkdir(parents=True)
    shutil.copyfile(p,d/'input.json')
    tasks.append(dict(case_id=t['case_id'],type=c['type'],prediction=c['prediction'],classification_reason=c['reason'],
        classification_reference_status=c['reference_status'],seed=0,dsl_path=str(p),input_copy=str(d/'input.json'),sha256=t['sha256'],
        reference_expressions=meta['reference_expressions'],arm_order=['T0','T1','T2'][i%3:]+['T0','T1','T2'][:i%3],
        sigma={k:c[k] for k in ['T1_sigma','T1_sigma_check','T2_sigma','T2_sigma_check']}))
M=dict(created_utc=datetime.now(timezone.utc).isoformat(),repository=str(REPO),output=str(OUT),scratch=str(ROOT),
    source_origin=str(SRC),frozen_origin=str(FROZEN),source_hash=source_tree_hash(),frozen_source_hash=OLD['frozen_source_hash'],
    inputs=tasks,files={str(p):sha(p) for p in sorted(files)},
    source_files={str(p):sha(p) for root in [SRC,FROZEN] for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts},
    cpus=sorted(os.sched_getaffinity(0))[:8],parallel=min(8,len(os.sched_getaffinity(0))),cores=1,seeds=[0],
    python=OLD['python'],python_version=sys.version,dependencies=installed_dependencies(),host=platform.node(),platform=platform.platform(),
    thread_environment={k:'1' for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS']},
    seconds=dict(search_pipeline_budget=178,search_outer=180,refine=90,verify=90,measurement_outer=90),
    switch_settings=dict(search={},refine={a:{'GEOSOLVER_S3_TANGENCY_MODE':a} for a in ['T0','T1','T2']},verify={},references={},ablations='all unset'),
    initial_loadavg=list(os.getloadavg()),search_retries=0,refinement_retries=0,optional_no_reference='measure all five, no predictions; exclude from U1/U2/U3',
    missing_policy='separate missing; success >=80% of fixed type total; missing never counted as success; if lower/upper bounds straddle 80%, indeterminate')
text=json.dumps(M,ensure_ascii=False,indent=2)+'\n'
(ROOT/'manifest.json').write_text(text);(OUT/'pre-run-hashes.json').write_text(text)
print(ROOT)
