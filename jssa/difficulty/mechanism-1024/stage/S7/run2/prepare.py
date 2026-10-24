"""Freeze the fixed stage-(1) population, S1 procedures, sources and references."""
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

OUT = Path(__file__).resolve().parent
S7 = OUT.parent
REPO = OUT.parents[5]
ORIGIN = Path('/tmp/mechanism-7b-lkdjle5l/final/src')


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(path, value):
    data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n'
    assert len(data.encode()) < 3_000_000
    path.write_text(data)


def main():
    assert not (OUT/'pre-run-hashes.json').exists(), 'No re-preparation'
    root = Path(tempfile.mkdtemp(prefix='mechanism-S7-run2-'))
    shutil.copytree(ORIGIN, root/'final/src', ignore=shutil.ignore_patterns('__pycache__'))
    sys.path.insert(0, str(root/'final/src'))
    from geosolver.runtime.integrity import source_tree_hash, installed_dependencies
    source = source_tree_hash()
    assert source == 'sha256:03a44bfbb743b972d95306c63a14c04b78c7d12b96a1ba83d147c56eea7f86a3'
    classified = list(csv.DictReader((S7/'classification.csv').open()))
    selected = [r for r in classified if r['status']=='ok']
    assert len(selected)==266
    assert sum(r['W3_target']=='True' for r in selected)==5
    inputs=[]
    files=list(OUT.glob('*.py'))+[OUT/'README.md',S7/'classification.csv',S7/'README.md',
        S7/'helpers.py',S7/'measure.py',S7/'pre-run-hashes.json', S7.parent/'S3/preregistration-14.md']
    files += [S7.parent/'S1'/n for n in ('prepare.py','driver.py','worker.py','analyze.py','rules.md')]
    (root/'inputs').mkdir()
    for i,row in enumerate(selected):
        case=row['case_id']
        stage1_input=S7/'inputs'/(case+'.json')
        item=json.loads(stage1_input.read_text())
        copied=root/'inputs'/(case+'.json')
        save(copied,item['dsl'])
        ref_path=S7/'results'/case/'reference.json'
        details=S7/'results'/case/'sigma-details.json'
        ref=json.loads(ref_path.read_text())
        assert ref['status']=='ok'
        inputs.append(dict(case_id=case,seed=0,input_copy=str(copied),sha256=sha(copied),
            stage1_input=str(stage1_input),reference_path=str(ref_path),sigma_details=str(details),
            reference_answer=ref['answer'],reference_coordinate_dps=ref['refinement_dps'],
            classification=row,arm_order=['BASE','RAW'] if i%2==0 else ['RAW','BASE']))
        files.extend([stage1_input,ref_path,details])
    manifest=dict(created_utc=datetime.now(timezone.utc).isoformat(),scratch=str(root),
        source_origin=str(ORIGIN),source_hash=source,reference_value='stage1 reference.json answer',
        source_files={str(p.relative_to(root)):sha(p) for p in sorted((root/'final/src').rglob('*')) if p.is_file()},
        files={str(p):sha(p) for p in files},inputs=inputs,python=sys.executable,python_version=sys.version,
        dependencies=installed_dependencies(),host=platform.node(),platform=platform.platform(),
        cpus=sorted(os.sched_getaffinity(0))[-10:],parallel=10,cores=1,seeds=[0],retries=0,
        thread_environment={k:'1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS','VECLIB_MAXIMUM_THREADS')},
        switch_settings={'search':{},'BASE':{},'RAW':{'GEOSOLVER_ABLATE_NO_RESIDUAL_REWRITE':'1','GEOSOLVER_S7_RAW_T1':'1'}},
        seconds={'search_pipeline_budget':178,'search_outer':180,'refine':90,'refine_outer':98,'scales_outer':90,'measurement_outer':90},
        initial_loadavg=list(os.getloadavg()),repository=str(REPO),output=str(OUT),final_verification=False,
        preflight='No target search/refinement. Validate raw/T1 at stage1 reference coordinates before campaign.')
    save(root/'manifest.json',manifest)
    save(OUT/'pre-run-hashes.json',manifest)
    with (OUT/'progress.md').open('a') as f:
        f.write(f"# S7 段階(2) 進捗\n\n{manifest['created_utc']} 準備完了: 固定266問・seed 0・再試行なし。最大10並列、各1コア/内部1スレッド。生データ `{root}`。\n")
    print(root,flush=True)


if __name__=='__main__':
    main()
