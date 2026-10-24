"""Freeze all 323 development DSLs and permitted procedure inputs, no run reads."""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from datetime import datetime,timezone
sys.dont_write_bytecode=True
OUT=Path(__file__).resolve().parent
REPO=OUT.parents[4]
FROZEN=Path('/tmp/mech-inv-clean/src')
sys.path.insert(0,str(FROZEN))
from geosolver.runtime.integrity import source_tree_hash,installed_dependencies
SOURCE='sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):
    data=json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    assert len(data.encode())<3_000_000
    Path(p).write_text(data)
def reference_expressions(value):
    counted=re.fullmatch(r'(.+)\s*\((\d+)個\)',value.strip())
    expression=(counted.group(1) if counted else value).strip()
    expression=re.sub(r'\\+sqrt\{(\d+)\}',r'sqrt(\1)',expression)
    expression=re.sub(r'√(\d+)',r'sqrt(\1)',expression).replace('π','pi')
    expression=re.sub(r'∛(\d+)',r'root(\1,3)',expression)
    expression=re.sub(r'(?<=\d)(?=sqrt\(|root\(|pi\b|\()', '*',expression)
    node=ast.parse(expression,mode='eval').body
    result=[ast.get_source_segment(expression,n) for n in node.elts] if isinstance(node,ast.Tuple) else [expression]
    if counted: assert len(result)==int(counted.group(2))
    return result
def main():
    assert not (OUT/'pre-run-hashes.json').exists()
    assert source_tree_hash()==SOURCE
    # Benchmark mathematical reference answers only: no solver outcome/digit table.
    records={}
    cases=REPO/'benchmarks/cases.jsonl'
    for line in cases.read_text().splitlines():
        row=json.loads(line)
        if row.get('dsl_path'):
            records[Path(row['dsl_path']).name]=row.get('answer')
    (OUT/'inputs').mkdir()
    files=list(OUT.glob('*.py'))+[OUT/'README.md',cases,OUT.parent/'S3/preregistration-14.md',OUT.parent/'S4/prepare.py',OUT.parent/'S4/worker.py',OUT.parent/'S4/sigma_min.py',OUT.parent/'S5/reference.py',OUT.parent/'S5/measure.py',OUT.parent/'S5/worker.py',REPO/'benchmarks/research_runner.py']
    items=[]
    for path in sorted((REPO/'benchmarks/dsl').glob('*.json')):
        dsl=json.loads(path.read_text()); key=dsl['id']
        answer=records.get(path.name)
        expressions=[];error=None
        try:
            assert answer is not None,'benchmark mathematical answer missing'
            refs=answer if isinstance(answer,list) else [answer]
            expressions=[e for r in refs for e in reference_expressions(str(r))]
        except Exception as e: error=repr(e)
        ip=OUT/'inputs'/(key+'.json')
        save(ip,dict(case_id=key,dsl=dsl,selection=None,reference_expressions=expressions,reference_parse_error=error))
        items.append(dict(case_id=key,input=str(ip),sha256=sha(ip),dsl_path=str(path),dsl_sha256=sha(path)))
        files.extend([path,ip])
    assert len(items)==323 and len({t['case_id'] for t in items})==323
    import mpmath
    source_files={str(p):sha(p) for p in sorted(FROZEN.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
    save(OUT/'pre-run-hashes.json',dict(created_utc=datetime.now(timezone.utc).isoformat(),frozen_commit='60db4b679b04167175c51c479c87c22fa663fda0',frozen_source=str(FROZEN),source_hash=SOURCE,source_files=source_files,files={str(p):sha(p) for p in sorted(files)},dependencies=installed_dependencies(),mpmath_version=mpmath.__version__,python=sys.executable,python_version=sys.version,parallel=8,cpus=sorted(os.sched_getaffinity(0))[-8:],threads={k:'1' for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS']},solve_seed=0,solve_seconds=180,solve_retries=0,per_problem_seconds=600,reference_closure_seconds=180,reference_dps=620,reference_agreement_digits=300,jacobian_dps=200,step_exponents=[70,60],stage_2_executed=False,items=items))
    print('Prepared',len(items),'DSLs',flush=True)
if __name__=='__main__': main()
