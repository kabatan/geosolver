"""research_runner invocation/contract, with public JSON returned over stdout.

Only transport differs: omitting --output uses the CLI's existing stdout path.
This avoids an extra output file that could disappear while a solve is running.
"""
from common import *
import os
import subprocess
import time
from benchmarks import research_runner as research


def execute(record, cpu):
    from geosolver.platform.processes import spawn_process, terminate_process_tree
    command = [sys.executable, "-m", "geosolver.application.cli", "solve", str(record.dsl_path),
               "--time-limit-seconds", "180", "--cores", "1", "--seed", "0"]
    env = os.environ.copy()
    env.update(research.THREAD_ENVIRONMENT)
    started = time.monotonic()
    process = spawn_process(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    affinity = research._pin_process(process,cpu)
    timed_out = False
    try:
        stdout,stderr = process.communicate(timeout=188)
    except subprocess.TimeoutExpired:
        timed_out = True
        terminate_process_tree(process)
        stdout,stderr = process.communicate()
    finally:
        if getattr(process,"_geosolver_owned_group",False):
            terminate_process_tree(process,grace_seconds=0.1)
    elapsed = time.monotonic()-started
    parse_error = None
    try:
        result = json.loads(stdout)
    except (ValueError,TypeError) as error:
        result = None
        parse_error = repr(error)
    issues = []
    if result and result.get("status") in {"solved","no_answer_found"}:
        identity = result.get("engine",{})
        info = result.get("diagnostics",{}).get("process_info",{})
        if identity.get("source_hash") != research._source_hash():
            issues.append("executed_product_hash_mismatch")
        if info.get("import_root") != str((ROOT/"src/geosolver").resolve()):
            issues.append("executed_import_root_mismatch")
        if info.get("cpu_affinity") != [cpu]:
            issues.append("executed_affinity_mismatch")
        for name,version in research.runtime_fingerprint()["runtime_dependencies"].items():
            if name != "geosolver" and info.get("installed_dependencies",{}).get(name) != version:
                issues.append(f"executed_dependency_mismatch:{name}")
    return dict(schema_version=2, execution_contract_issues=issues,
        case_id=record.identifier, seed=0,
        problem_hash=research._sha256_bytes(research._canonical_json(record.dsl).encode()),
        source_hash=research._source_hash(), dependency_lock_hash=research._dependency_hash(),
        config=dict(time_limit_seconds=180,cores=1,thread_environment=research.THREAD_ENVIRONMENT),
        process=dict(assigned_cpu=cpu,actual_affinity=affinity,returncode=process.returncode,
                     timed_out=timed_out,elapsed_seconds=elapsed,
                     stdout="" if result is not None else stdout[-4000:],stderr=stderr[-12000:]),
        transport=dict(kind="existing_cli_stdout",parse_error=parse_error),solver_result=result)
