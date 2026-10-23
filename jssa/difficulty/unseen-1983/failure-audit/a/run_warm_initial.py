"""Full-search warm starts, 180s each, one CPU, separate from all frozen scoring."""
from common import *
import resource
from geosolver.application.service import solve
from geosolver.engine.runner import EngineRunner
from warm_worker import near_point

if __name__ == '__main__':
    os.sched_setaffinity(0,{3})
    resource.setrlimit(resource.RLIMIT_FSIZE,(4_900_000,4_900_000))
    os.environ['PYTHONPATH'] = os.pathsep.join([str(HERE),str(ROOT/'src'),str(ROOT)])
    save(HERE/'warm-initial-plan.json',dict(identity=identity(), time_limit_seconds=180, cpu=3,
        purpose='Distinguish initial-point injection with original global search from post-discovery completion injection.',
        intervention='Only pipeline.run_initial_probe replaced; normal run_search and its original bounds retained.',
        cases=list(IDS),seed=2901,perturbation='x_i + 0.01*(-1)^i'))
    for cid in IDS:
        path = HERE/'warm-initial'/f'{cid}.json'
        if path.exists():
            print(f'Skip existing {path.name}',flush=True)
            continue
        result = solve(problem(cid),dict(seed=2901,time_limit_seconds=180,cores=1),
            runner=EngineRunner(worker_module='warm_initial_worker',memory_limit_bytes=2*1024**3))
        data = result.model_dump(mode='json')
        save(path,dict(experiment='posthoc_original_DSL_full_search_near_initial_probe',
            original_DSL=True, solver_src=FROZEN, time_limit_seconds=180,cpu=3,
            near_point=near_point(cid,problem(cid).variables),solver_result=data))
        print(cid,data['status'],data['answers'],data['elapsed_seconds'],flush=True)
