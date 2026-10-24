"""Portable S8 measurement entry point (Linux / WinPC WSL); no automatic retries."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import tempfile
from measurement_common import HERE, load, save, sha, utc, progress
from measurement_runtime import execute, environment

CUMULATIVE=['N','C1','C2','C3','C4','C5','BASE']
STOP=False

def select_jobs(machine,configs,slots_file=None):
    known=load(HERE/'configs.json');aliases=known['aliases']
    selected={aliases.get(c,c) for item in configs for c in item.split(',')}
    assert selected and selected<={c['name'] for c in known['configurations']},'unknown configs'
    jobs=[j for j in load(HERE/'run-plan.json')['jobs'] if j['machine'].lower()==machine and j['configuration'] in selected]
    assert len(jobs)==53*3*len(selected)
    if slots_file is not None:
        plan=load(slots_file)
        original=HERE.parent/'run-superpc'
        assert sha(original/'per-run.csv')==plan['source_per_run_sha256'],'original CSV changed'
        assert sha(original/'measurement-freeze.json')==plan['source_freeze_sha256'],'original freeze changed'
        import csv
        with (original/'per-run.csv').open() as stream:
            indices=[int(r['queue_index']) for r in csv.DictReader(stream) if r['reason']=='nonzero_exit']
        wanted=plan['jobs']
        assert len(wanted)==320 and len({j['queue_index'] for j in wanted})==320
        assert [j['queue_index'] for j in wanted]==indices,'must replace exactly original nonzero_exit slots'
        assert wanted==[j for j in jobs if j['queue_index'] in set(indices)],'slot specification/order changed'
        return wanted
    return jobs


def stop_handler(signum,frame):
    global STOP
    STOP=True


def preflight(args):
    command=[args.python,'-B',str(HERE/'measurement_preflight.py'),'--machine',{'superpc':'superPC','winpc':'WinPC'}[args.machine],
             '--source-root',str(args.base_src),'--repo-root',str(args.repo_root)]
    r=subprocess.run(command,env=environment('BASE',args.base_src,load(HERE/'configs.json')),capture_output=True,text=True,check=True)
    return json.loads(r.stdout)


def verify_frozen(out):
    freeze=load(out/'measurement-freeze.json')
    for name,h in freeze['measurement_files_sha256'].items():assert sha(HERE/name)==h,('measurement file changed',name)
    for name,h in freeze['preparation_files_sha256'].items():assert sha(HERE/name)==h,('preparation file changed',name)
    assert sha(HERE/'references.json')==freeze['references_sha256']
    assert sha(freeze['slots_file'])==freeze['slots_file_sha256']
    return freeze


def run(args):
    jobs=select_jobs(args.machine,args.configs,args.slots_file)
    assert args.slots_file is not None,'rerun requires --slots-file'
    assert args.output != HERE.parent/'run-superpc','never overwrite original'
    out=args.output;out.mkdir(exist_ok=True,parents=True)
    lock=(out/'campaign.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if args.command=='run':
        assert not (out/'measurement-freeze.json').exists(),'existing campaign: use resume; never restart'
        assert not (out/'receipts').exists(),'receipts already exist'
        contract=load(HERE/'measurement-contract-results.json');assert contract['passed']
        assert contract['tested_files_sha256']==tested_hashes(),'driver changed after contract checks'
        check=preflight(args)
        original=load(HERE.parent/'run-superpc/measurement-freeze.json')
        assert check['source_hash']==original['source_hash'] and check['python_sha256']==original['python_sha256']
        assert check['host']==original['preflight']['host']
        for k in ('memory_mib','address_space_mib'):assert getattr(args,k)==original[k]
        for k in ('base_src','repo_root','python'):assert str(getattr(args,k))==original[k]
        for name in ('configs.json','assignment.json','run-plan.json','source-hashes.json','references-hashes.json'):
            assert sha(HERE/name)==original['preparation_files_sha256'][name]
        assert sha(HERE/'references.json')==original['references_sha256']
        for name in ('measurement_exact.py','measurement_grade.py'):
            assert sha(HERE/name)==original['measurement_files_sha256'][name]
        refs=load(HERE/'references.json');assert len(refs['cases'])==106
        assert sha(HERE/'references.json')==load(HERE/'references-hashes.json')['references_sha256']
        raw=args.raw_root or Path(tempfile.mkdtemp(prefix=f'mechanism-S8-{args.machine}-raw-',dir='/tmp'))
        raw=raw.resolve();assert not raw.is_relative_to(args.repo_root),'raw must be outside repo'
        raw.mkdir(exist_ok=True,parents=True);assert not any(raw.iterdir()),'raw directory must be empty'
        eligible=sorted(os.sched_getaffinity(0));assert len(eligible)>=args.max_parallel
        # Prefer distinct physical cores when sysfs topology is available.
        slots=[];seen=set()
        for cpu in eligible:
            top=Path(f'/sys/devices/system/cpu/cpu{cpu}/topology')
            key=tuple((top/n).read_text().strip() for n in ['physical_package_id','core_id']) if top.exists() else (cpu,)
            if key not in seen:slots.append(cpu);seen.add(key)
        assert len(slots)>=args.max_parallel,'not enough distinct physical cores'
        freeze=dict(created_utc=utc(),machine=args.machine,configs=sorted({j['configuration'] for j in jobs}),jobs=jobs,
            slots_file=str(args.slots_file),slots_file_sha256=sha(args.slots_file),
            original_freeze_sha256=sha(HERE.parent/'run-superpc/measurement-freeze.json'),
            raw_root=str(raw),base_src=str(args.base_src),repo_root=str(args.repo_root),python=args.python,
            python_sha256=check['python_sha256'],source_hash=check['source_hash'],max_parallel=args.max_parallel,
            memory_mib=args.memory_mib,address_space_mib=args.address_space_mib,slot_cpus=slots[:args.max_parallel],
            preflight=check,references_sha256=sha(HERE/'references.json'),measurement_files_sha256=tested_hashes(),
            supervisor_sha256=sha(HERE/'supervise_superpc.py'),
            preparation_files_sha256={n:sha(HERE/n) for n in ['configs.json','assignment.json','run-plan.json','source-hashes.json','references-hashes.json','measurement-contract-results.json']},
            parent_removed_geosolver_keys=sorted(k for k in os.environ if k.startswith('GEOSOLVER_')),
            no_retries=True,no_extra_seeds=True,no_commit_or_push=True,
            time_policy='Parent monotonic before spawn to process exit; hard outer 180s. Total time through cleanup separately recorded. Failure/timeout C=180; interrupted/ungradable C=null.')
        save(out/'measurement-freeze.json',freeze,True);(out/'receipts').mkdir()
        progress(out,f"本計測前固定 jobs={len(jobs)} machine={args.machine} configs={freeze['configs']} reference={freeze['references_sha256']} source={freeze['source_hash']}; raw={raw}")
    else:
        freeze=verify_frozen(out)
        assert jobs==freeze['jobs'],'resume selection mismatch'
        assert str(args.slots_file)==freeze['slots_file'] and sha(args.slots_file)==freeze['slots_file_sha256']
        assert args.raw_root is None or str(args.raw_root.resolve())==freeze['raw_root'],'raw-root mismatch'
        assert args.max_parallel<=freeze['max_parallel'],'resume cannot increase parallelism'
        for k in ['base_src','repo_root','python']:assert str(getattr(args,k))==freeze[k],f'resume {k} mismatch'
        assert args.memory_mib==freeze['memory_mib'] and args.address_space_mib==freeze['address_space_mib']
        check=preflight(args);assert check['python_sha256']==freeze['python_sha256']
        assert platform.node()==freeze['preflight']['host'],'resume on different host'
    signal.signal(signal.SIGTERM,stop_handler);signal.signal(signal.SIGINT,stop_handler)
    completed=execute(jobs,out,freeze,args.max_parallel,lambda:STOP)
    if completed:
        check=preflight(args);assert check['source_hash']==freeze['source_hash']
        progress(out,'計測キュー終了、ソース/入力/依存を再照合。gradeで独立採点。')
    print(json.dumps(dict(queue_finished=completed,output=str(out),planned=len(jobs))))


def tested_hashes():
    return {n:sha(HERE/n) for n in ['driver.py','measurement_common.py','measurement_runtime.py','measurement_launch.py',
        'measurement_preflight.py','measurement_exact.py','measurement_grade.py','test_measurement_contract.py','freeze_measurement_references.py','supervise_superpc.py','merge_and_grade.py','mock_supervisor_driver.py','report_superpc.py','analysis-freeze-rerun.json']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    for cmd in ['run','resume','grade','verify-plan']:
        p=sub.add_parser(cmd)
        p.add_argument('--machine',required=True,type=str.lower,choices=['superpc','winpc'])
        p.add_argument('--configs',nargs='+',default=CUMULATIVE)
        p.add_argument('--output',type=Path)
        p.add_argument('--repo-root',type=Path,default=HERE.parents[5])
        p.add_argument('--slots-file',type=Path,default=HERE.parent/'run-plan-rerun.json')
        p.add_argument('--base-src','--source-root',dest='base_src',type=Path)
        p.add_argument('--python',default=sys.executable)
        p.add_argument('--max-parallel',type=int,default=8)
        p.add_argument('--raw-root',type=Path)
        p.add_argument('--memory-mib',type=int,default=4096)
        p.add_argument('--address-space-mib',type=int,default=16384)
    args=parser.parse_args()
    assert 1<=args.max_parallel<=8
    args.repo_root=args.repo_root.resolve();args.output=(args.output or HERE.parent/'run-superpc-rerun').resolve()
    if args.base_src:args.base_src=args.base_src.resolve()
    if args.slots_file:args.slots_file=args.slots_file.resolve()
    args.python=os.path.abspath(args.python) # keep venv symlink; do not replace by its base binary
    if args.command=='grade':
        freeze=verify_frozen(args.output);assert freeze['machine']==args.machine
        assert select_jobs(args.machine,args.configs,args.slots_file)==freeze['jobs']
        from merge_and_grade import merge_and_grade
        merge_and_grade(args.output,freeze)
    else:
        assert args.base_src,'--base-src required'
        if args.command=='verify-plan':
            jobs=select_jobs(args.machine,args.configs,args.slots_file)
            print(json.dumps(dict(preflight=preflight(args),rerun_slots=len(jobs),slots_sha256=sha(args.slots_file),solver_executions=0),ensure_ascii=False,indent=2))
        else:run(args)

if __name__=='__main__':main()
