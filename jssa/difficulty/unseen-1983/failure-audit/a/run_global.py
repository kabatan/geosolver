"""Separate exploratory 900s runs, one previously failing seed per original DSL."""
from common import *
import argparse
import datetime
import resource
import subprocess
import time

def run_one(cid, seed, cpu):
    os.sched_setaffinity(0, {cpu})
    resource.setrlimit(resource.RLIMIT_FSIZE, (4_900_000, 4_900_000))
    from geosolver.application.service import solve
    from geosolver.engine.runner import EngineRunner
    result = solve(problem(cid), dict(seed=seed, time_limit_seconds=900, cores=1),
                   runner=EngineRunner(memory_limit_bytes=2*1024**3))
    data = result.model_dump(mode="json")
    save(HERE / "global-900" / f"{cid}-seed-{seed}.json", dict(
        experiment="posthoc_original_DSL_900s", source_identity=identity(), cpu=cpu,
        time_limit_seconds=900, seed=seed, original_DSL=True, solver_result=data))
    print(json.dumps(dict(id=cid, seed=seed, status=data['status'], elapsed=data['elapsed_seconds'],
                          answers=data['answers']), ensure_ascii=False), flush=True)

def campaign():
    # Three solve workers leave one of the allowed four slots for witness/local work.
    cpus = sorted(os.sched_getaffinity(0))[:3]
    tasks = [(cid, 205 if cid == "AIME-1991-14" else 201) for cid in IDS]
    save(HERE / "experiment-plan.json", dict(
        created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), identity=identity(),
        scope="Q29a; posthoc diagnostics; NEVER merged into frozen 85/130",
        chosen_seed_rule="first failed seed in existing assessment; one per case",
        global_tasks=[dict(id=c, seed=s, seconds=900) for c,s in tasks],
        maximum_parallel_global=3, maximum_parallel_total=4, cpus=cpus,
        per_worker_memory_limit_bytes=2*1024**3, file_size_limit_bytes=4_900_000,
        local_plan="Analytic witness; deterministic +-0.01 absolute perturbation of every variable; frozen local refiner then final verifier. Diagnostic only."))
    pending = list(tasks)
    active = {}
    while pending or active:
        for cpu in cpus:
            if cpu not in active and pending:
                cid, seed = pending.pop(0)
                out = HERE / "global-900" / f"{cid}-seed-{seed}.json"
                if out.exists():
                    raise RuntimeError(f"Refuse overwrite: {out}")
                child = subprocess.Popen([sys.executable, __file__, "one", cid, str(seed), str(cpu)])
                active[cpu] = (child, cid, time.monotonic())
                print(f"started {cid} seed={seed} cpu={cpu}", flush=True)
        for cpu, (child, cid, started) in list(active.items()):
            if child.poll() is not None:
                print(f"finished {cid} returncode={child.returncode}", flush=True)
                del active[cpu]
            elif time.monotonic()-started > 930:
                child.terminate()
                child.wait(timeout=10)
                raise RuntimeError(f"outer watchdog: {cid}")
        time.sleep(0.5)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "one":
        run_one(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
    else:
        campaign()
