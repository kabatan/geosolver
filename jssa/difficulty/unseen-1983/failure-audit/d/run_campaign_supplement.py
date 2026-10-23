"""Q29d: commit-gated frozen-source execution, <=4 workers, compact receipts only."""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import io
import json
import multiprocessing
import os
import subprocess
import sys
import tarfile
import tempfile
import time
import traceback
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
sys.path.insert(0,str(HERE))
sys.dont_write_bytecode=True
sys.setrecursionlimit(10000)
os.environ["PYTHONDONTWRITEBYTECODE"]="1"
for key in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS"):
    os.environ[key]="1"
from prepare import FROZEN, IDS, CORPUS, now, save, sha

EXPECTED_SOURCE="sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5"
RUNTIME=Path("/tmp")/("q29d-frozen-60db4b6-"+hashlib.sha256(str(ROOT).encode()).hexdigest()[:12])
CPU=None
rr=None

def git(*args):
    return subprocess.check_output(["git",*args],cwd=ROOT)

def prepare_runtime():
    # This archive is constructed from the requested Git commit, never from the sealed Q19 tar.
    archive=git("archive",FROZEN,"src","uv.lock")
    RUNTIME.mkdir(exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(archive)) as members:
        for member in members:
            assert (member.name in {"src","uv.lock"} or member.name.startswith("src/")) and ".." not in Path(member.name).parts
            path=RUNTIME/member.name
            if member.isdir():
                path.mkdir(exist_ok=True,parents=True)
            elif member.isfile():
                content=members.extractfile(member).read()
                if path.exists():
                    assert path.read_bytes()==content,"frozen snapshot changed"
                else:
                    path.parent.mkdir(exist_ok=True,parents=True)
                    path.write_bytes(content)
            else:
                raise RuntimeError("unexpected Git archive member")
    hook=RUNTIME/"hook"
    hook.mkdir(exist_ok=True)
    content="import sys\nsys.setrecursionlimit(10000)\nsys.dont_write_bytecode = True\n"
    (hook/"sitecustomize.py").write_text(content)

def bootstrap():
    global rr
    assert (RUNTIME/"src/geosolver/engine-lock.json").is_file(),"run preflight first"
    sys.path[:0]=[str(RUNTIME/"src"),str(ROOT)]
    os.environ["PYTHONPATH"]=os.pathsep.join([str(RUNTIME/"hook"),str(RUNTIME/"src"),str(ROOT)])
    from benchmarks import research_runner
    rr=research_runner
    rr.ROOT=RUNTIME
    from geosolver.runtime.integrity import verify_engine_lock,source_tree_hash
    assert source_tree_hash()==EXPECTED_SOURCE
    assert verify_engine_lock()[0]
    fingerprint=rr.runtime_fingerprint()
    assert not fingerprint["issues"],fingerprint
    return fingerprint

def verify_inputs():
    source=json.loads((HERE/"source-inputs.json").read_text())
    for cid,digest in source["original_dsl_sha256"].items():
        assert sha(CORPUS/"dsl"/(cid+".json"))==digest,cid
    assert sha(CORPUS/"prereg/q19-scored/assessment.jsonl")==source["q19_assessment_sha256"]
    assert rr.validate_corpus(HERE/"cases.jsonl")["valid"]
    assert len(IDS)==9

def tasks():
    main=[{"group":"main","id":cid,"seed":seed} for seed in range(206,211) for cid in IDS]
    diagnostic=[{"group":f"hexagon-repeat{rep}","id":"AIME-1991-14","seed":205} for rep in (1,2)]
    diagnostic += [{"group":"hexagon-new","id":"AIME-1991-14","seed":seed} for seed in range(206,211)]
    return main+diagnostic

def preflight():
    prepare_runtime()
    fingerprint=bootstrap()
    verify_inputs()
    from score import validate_conversions
    import psutil
    load=psutil.cpu_percent(interval=1,percpu=True)
    physical=rr._independent_cpus()
    cpus=sorted(physical,key=lambda cpu:(load[cpu],cpu))[:4]
    assert len(cpus)==4 and None not in cpus
    result={"checked_at_utc":now(),"frozen_commit":FROZEN,"runtime":fingerprint,
            "source_git_tree":git("rev-parse",FROZEN+":src").decode().strip(),
            "current_src_diff_from_frozen_empty":not bool(git("diff",FROZEN,"--","src")),
            "runtime_root":str(RUNTIME),"python_executable":sys.executable,
            "runner_sha256":sha(ROOT/"benchmarks/research_runner.py"),
            "cpus":cpus,"cpu_load_at_preflight_percent":{str(c):load[c] for c in cpus},
            "time_limit_seconds":180,"cores_per_run":1,"max_parallel":4,
            "external_watchdog_seconds":188,"recursion_limit":10000,
            "score_checks":validate_conversions(),"main_runs":45,"diagnostic_runs":7,
            "sealed_raw_accessed":False,"search_executed":False}
    save(HERE/"preflight.json",result)
    print(json.dumps(result,ensure_ascii=False),flush=True)

def freeze():
    assert (HERE/"preflight.json").is_file()
    assert not (HERE/"prediction.lock.json").exists(),"never overwrite an existing prediction lock"
    assert not (HERE/"campaign").exists(),"cannot predict after running"
    validation=json.loads((HERE/"witness-validation.json").read_text())
    assert len([r for r in validation["checks"] if r["variant"]=="rewritten"])==9
    paths=sorted(p for p in HERE.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    assert sum(p.stat().st_size for p in paths)<5_000_000
    locked={str(p.relative_to(HERE)):sha(p) for p in paths}
    locked["@research_runner.py"]=sha(ROOT/"benchmarks/research_runner.py")
    lock={"prediction_sha256":sha(HERE/"prediction.md"),"locked_at_utc":now(),
          "frozen_commit":FROZEN,"source_hash":EXPECTED_SOURCE,"files_sha256":locked,
          "solver_search_executed_before_lock":False,"user_commit_required_before_execution":True}
    save(HERE/"prediction.lock.json",lock)
    print("予測固定",flush=True)
    print(json.dumps({"prediction_sha256":lock["prediction_sha256"],"locked_at_utc":lock["locked_at_utc"]}),flush=True)

def commit_gate():
    lock_path=HERE/"prediction.lock.json"
    lock=json.loads(lock_path.read_text())
    prefix=HERE.relative_to(ROOT).as_posix()
    try:
        committed=git("show","HEAD:"+prefix+"/prediction.lock.json")
    except subprocess.CalledProcessError:
        raise RuntimeError("prediction lock is not committed; user commit required before execution") from None
    assert committed==lock_path.read_bytes(),"committed lock differs from working lock"
    for relative,digest in lock["files_sha256"].items():
        path=ROOT/"benchmarks/research_runner.py" if relative=="@research_runner.py" else HERE/relative
        assert sha(path)==digest,"working preregistration file changed: "+relative
        committed_bytes=git("show","HEAD:"+path.relative_to(ROOT).as_posix())
        assert hashlib.sha256(committed_bytes).hexdigest()==digest,"uncommitted locked file: "+relative
    return {"verified_at_utc":now(),"prediction_commit":git("rev-parse","HEAD").decode().strip(),
            "prediction_sha256":lock["prediction_sha256"],"prediction_lock_sha256":sha(lock_path)}

def compact(value,depth=0):
    if isinstance(value,dict):
        if depth>=8:
            return {"omitted_deep_mapping_keys":list(value)}
        return {k:compact(v,depth+1) for k,v in value.items()}
    if isinstance(value,list):
        if len(value)>12:
            return {"original_count":len(value),"first_8":[compact(v,depth+1) for v in value[:8]],
                    "last_2":[compact(v,depth+1) for v in value[-2:]]}
        return [compact(v,depth+1) for v in value]
    if isinstance(value,str) and len(value)>2000:
        return value[:2000]+f" [truncated; original_chars={len(value)}]"
    return value

def write_summary(path,raw):
    from score import assess
    result=raw.get("solver_result") or {}
    diagnostics=result.get("diagnostics") or {}
    summary={"schema":"q29d-summary-v1","raw_full_record_saved":False,
             "raw_canonical_sha256":hashlib.sha256(rr._canonical_json(raw).encode()).hexdigest(),
             "recorded_at_utc":now(),"assessment":assess(raw),
             "execution":{k:raw[k] for k in ("case_id","seed","problem_hash","source_hash",
                           "dependency_lock_hash","config","execution_contract_issues")},
             "process":{k:v for k,v in raw.get("process",{}).items() if k not in {"stdout","stderr"}},
             "process_stdout_excerpt":raw.get("process",{}).get("stdout","")[:1000],
             "process_stderr_excerpt":raw.get("process",{}).get("stderr","")[:2000],
             "answers":result.get("answers",[]),"engine":result.get("engine"),
             "diagnostics":compact(diagnostics)}
    payload=json.dumps(summary,ensure_ascii=False,indent=2)+"\n"
    if len(payload.encode())>80_000:
        # Retain assessment/identity; diagnostics are evidence, not a scoring input.
        summary["diagnostics"]={"omitted_due_to_size":True,"keys":list(diagnostics),
                                 "numeric_feasible":diagnostics.get("numeric_feasible"),
                                 "exact_identified":diagnostics.get("exact_identified"),
                                 "pipeline_summary":compact(diagnostics.get("pipeline_summary",{}),depth=5)}
        payload=json.dumps(summary,ensure_ascii=False,indent=2)+"\n"
    assert len(payload.encode())<4_900_000,"summary unexpectedly large"
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(payload)

def initialize_worker(queue):
    global CPU
    CPU=queue.get()
    import psutil
    psutil.Process().cpu_affinity([CPU])
    bootstrap()
    rr._atomic_json=write_summary

def worker(task):
    cid,seed,group=task["id"],task["seed"],task["group"]
    dest=HERE/"campaign"/group
    path=dest/"runs"/cid/(str(seed)+".json")
    assert not path.exists(),"never overwrite a completed run"
    dsl_path=(HERE if group=="main" else CORPUS)/"dsl"/(cid+".json")
    dsl=json.loads(dsl_path.read_text())
    record=rr.CaseRecord(cid,dsl_path,dsl,"Q29d",(),"runnable","verified",cid)
    started=now()
    with tempfile.TemporaryDirectory(prefix="q29d-",dir=RUNTIME) as temp:
        os.environ.update({"TMPDIR":temp,"TMP":temp,"TEMP":temp})
        tempfile.tempdir=temp
        try:
            rr._run_one(record,seed,dest,CPU)
            stored=json.loads(path.read_text())
            stored["group"]=group
            stored["started_at_utc"]=started
            stored["finished_at_utc"]=now()
            save(path,stored)
            assessed=stored["assessment"]
            return {**task,"matched":assessed["matched"],"status":assessed["status"],
                    "seconds":assessed["wall_seconds"],"answers":assessed["answer_expressions"]}
        except BaseException as error:
            if path.exists():
                # Contract failure can raise after writing a scored failure receipt.
                data=json.loads(path.read_text());data["runner_error"]=traceback.format_exc()[-4000:]
                data["group"]=group;data["started_at_utc"]=started;data["finished_at_utc"]=now();save(path,data)
            else:
                path.parent.mkdir(parents=True,exist_ok=True)
                save(path,{"schema":"q29d-summary-v1","group":group,"started_at_utc":started,
                           "finished_at_utc":now(),"assessment":{"case_id":cid,"seed":seed,"matched":False,
                           "status":"runner_error","normal_completion":False,"n_answers":0},
                           "runner_error":traceback.format_exc()[-4000:]})
            return {**task,"matched":False,"status":"runner_error","error":str(error)}
        finally:
            tempfile.tempdir=None

def run():
    fingerprint=bootstrap()
    gate=commit_gate()  # Must pass before the first solver process.
    verify_inputs()
    from score import validate_conversions
    validate_conversions()
    pf=json.loads((HERE/"preflight.json").read_text())
    assert sha(ROOT/"benchmarks/research_runner.py")==pf["runner_sha256"]
    cpus=pf["cpus"]
    assert len(cpus)==4 and rr.CANONICAL_CORES==1 and rr.CANONICAL_TIME_LIMIT_SECONDS==180
    destination=HERE/"campaign"
    destination.mkdir(exist_ok=False)
    plan=tasks()
    save(destination/"execution-manifest.json",{**gate,"started_at_utc":now(),"runtime":fingerprint,
         "frozen_commit":FROZEN,"cpus":cpus,"jobs":4,"tasks":plan,"preflight_sha256":sha(HERE/"preflight.json")})
    ctx=multiprocessing.get_context("spawn")
    queue=ctx.Queue()
    for cpu in cpus: queue.put(cpu)
    completed=0
    with concurrent.futures.ProcessPoolExecutor(max_workers=4,mp_context=ctx,
            initializer=initialize_worker,initargs=(queue,)) as pool:
        futures=[pool.submit(worker,task) for task in plan]
        for future in concurrent.futures.as_completed(futures):
            result=future.result();completed+=1
            print(json.dumps({"completed":completed,"total":len(plan),**result},ensure_ascii=False),flush=True)
    files=list(destination.rglob("*.json"))
    size=sum(p.stat().st_size for p in files)
    assert completed==52 and size<5_000_000
    save(destination/"completion.json",{"completed_at_utc":now(),"completed_runs":completed,
         "json_bytes":size,"max_parallel":4,"sealed_raw_accessed":False})

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=["preflight","freeze","check-commit","run"])
    action=parser.parse_args().action
    if action=="preflight":preflight()
    elif action=="freeze":freeze()
    elif action=="check-commit":print(json.dumps(commit_gate()))
    else:run()

if __name__=="__main__":main()
