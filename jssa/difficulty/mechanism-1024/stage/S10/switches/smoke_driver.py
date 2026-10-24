"""Bounded foreground smoke only. No campaign/measurement mode."""
import hashlib
import json
import os
import signal
import subprocess
import time
from pathlib import Path

OUT=Path(__file__).resolve().parent
PYTHON='/home/kabatan/work/solver/.venv/bin/python'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    configs=json.loads((OUT/'configs.json').read_text())
    sources=json.loads((OUT/'source-hashes.json').read_text())
    freeze=json.loads((OUT/'pre-smoke-hashes.json').read_text())
    for p,h in freeze['files_sha256'].items():
        assert sha(OUT/p)==h,p
    for root_key, files_key in [('base_source','base_files_sha256'),
                                ('patched_source','patched_files_sha256'),
                                ('frozen_source','frozen_files_sha256')]:
        root=Path(sources[root_key])
        actual={str(p.relative_to(root)):sha(p) for p in sorted(root.rglob('*'))
                if p.is_file() and '__pycache__' not in p.parts}
        assert actual==sources[files_key],root_key
    dest=OUT/'smoke'
    dest.mkdir(exist_ok=False)
    cpu=sorted(os.sched_getaffinity(0))[-1]
    def env(arm,source=None):
        e={k:v for k,v in os.environ.items() if not k.startswith('GEOSOLVER_ABLATE_')}
        e.update(configs['thread_environment'])
        e.update(arm)
        e.update(PYTHONPATH=str(Path(source or sources['patched_source'])/'src'),
                 PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1', TMPDIR=str(Path(sources['patched_source']).parent))
        return e
    def command(script,*args):
        return ['nice','-n','15','taskset','-c',str(cpu),PYTHON,'-B',str(OUT/script),*args]
    rows={}
    baseline=subprocess.run(command('probe_worker.py'),env=env({},sources['base_source']),
        stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=10,check=True).stdout
    (dest/'probe.BASE1.json').write_bytes(baseline)
    variants=dict(configs['arms'])
    variants['B005_plus_B006']={**variants['B005'],**variants['B006']}
    variants['ALL_ZERO']={k:'0' for a in configs['arms'].values() for k in a}
    for arm,flags in variants.items():
        p=subprocess.run(command('probe_worker.py'),env=env(flags),stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL,timeout=10,check=True)
        (dest/f'probe.{arm}.json').write_bytes(p.stdout)
        rows[arm]=json.loads(p.stdout)
        if arm in ('B0','ALL_ZERO'):
            assert p.stdout==baseline,arm
    b=rows['B0']
    for arm,row in rows.items():
        assert row['lock_valid']
        assert row['guard_boundary']==[False,True]
        assert row['deadline']==b['deadline']
        assert row['box']['mathematical']==b['box']['mathematical']
        assert row['box']['original_guards']==b['box']['original_guards']
        assert row['explicit_box']==[[7.,9.],[0.,1.]]
        for kind,f in row['floors'].items():
            assert f['tiny_hp'] and not f['zero_hp'] and not f['zero_float']
            assert f['tiny_float']==('NO_FLOAT_MARGIN_FLOOR' in row['active'])
        for i,entry in enumerate(row['adapter']):
            assert entry['records']==b['adapter'][i]['records']
            if i<2:
                assert float(entry['payload'])==([25.,5.][i] if 'NO_NOMAD_GUARD_PENALTY' in row['active'] else [1000025.,1000005.][i])
            elif i==2:
                assert entry==b['adapter'][i]
            else:
                off='NO_HIDDEN_CONSTRAINT_MODE' in row['active']
                assert entry['returncode']==int(off)
                assert entry['payload']==('1e+30' if off else None)
                assert entry['failures']==1
        for mode,params in row['params'].items():
            off='NO_HIDDEN_CONSTRAINT_MODE' in row['active']
            assert ('DISCO_MADS_HID_CONST '+str(not off).lower()) in params
            assert ('DISCO_MADS_OPTIMIZATION '+str(mode=='disco_mads').lower()) in params
    expected={'B0':[[2.,402.],[0.,1.]],'B005':[[-200.,200.],[0.,1.]],
              'B006':[[2.,22.],[0.,1.]],'B005_006':[[-10.,10.],[0.,1.]]}
    for arm,value in expected.items():
        assert rows[arm]['box']['raw']==value,(arm,rows[arm]['box'])
    assert rows['B005_plus_B006']['box']==rows['B005_006']['box']
    assert rows['B005_006']['box']['expanded']==[[-15.,15.],[0.,1.]]
    jobs=[]
    inputs=json.loads((OUT/'inputs.json').read_text())
    for arm in configs['smoke']['full_process_arms']:
        for task in inputs:
            start=time.monotonic()
            process=subprocess.Popen(command('smoke_worker.py',arm,task['case_id']),
                env=env(configs['arms'][arm]),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                start_new_session=True)
            timeout=False
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                timeout=True
                os.killpg(process.pid,signal.SIGKILL)
                process.wait()
            job=dict(arm=arm,case_id=task['case_id'],group=task['group'],
                     wall_seconds=time.monotonic()-start,returncode=process.returncode,
                     outer_timeout=timeout)
            jobs.append(job)
            (dest/'driver.json').write_text(json.dumps(dict(max_parallel=1,cpu=cpu,jobs=jobs),indent=2)+'\n')
            print(arm,task['case_id'],process.returncode,flush=True)
    for job in jobs:
        assert not job['outer_timeout'] and job['returncode']==0,job
        row=json.loads((dest/f"{job['arm']}.{job['case_id']}.json").read_text())
        assert row['process_state'] in ('returned','deadline'),row
        assert row['calls']['run_external_pipeline']==1
        assert row['active']==[k.removeprefix('GEOSOLVER_ABLATE_') for k in configs['arms'][job['arm']]]
    result=dict(contract_assertions_passed=True,default_probe_byte_identical=True,
                default_zero_flags_byte_identical=True,full_process_jobs=len(jobs),
                max_parallel=1,outer_seconds=10,quality_compared=False,measurement_run=False,retries=0)
    (dest/'checks.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    main()
