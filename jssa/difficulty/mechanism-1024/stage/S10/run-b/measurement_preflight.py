"""Read-only S10B preflight. Hash/config checks only; never calls a solver."""
import argparse
import importlib.metadata
import json
import os
import platform
import sys
from pathlib import Path
from measurement_common import HERE,load,sha
from select_problems import selection,jobs_for,ARMS,SOURCE_HASH

def main():
    p=argparse.ArgumentParser();p.add_argument('--source-root',type=Path,required=True)
    p.add_argument('--repo-root',type=Path,default=HERE.parents[5]);p.add_argument('--machine',choices=['superPC'],required=True)
    a=p.parse_args();sys.path.insert(0,str(a.source_root.resolve()/'src'))
    from geosolver.runtime.integrity import source_tree_hash,verify_engine_lock
    source=load(HERE/'source-hashes.json')
    assert source_tree_hash()==source['source_hash']==SOURCE_HASH
    assert verify_engine_lock()==(True,SOURCE_HASH)
    for name,h in source['files_sha256'].items():assert sha(a.source_root/name)==h,name
    for name,h in load(HERE/'assignment.json')['provenance_sha256'].items():assert sha(a.repo_root/name)==h,name
    for name,h in load(HERE/'selection-hashes.json')['outputs_sha256'].items():assert sha(HERE/name)==h,name
    assert sha(HERE/'select_problems.py')==load(HERE/'selection-hashes.json')['script_sha256']
    rows,_=selection(a.repo_root);assert rows==load(HERE/'assignment.json')['problems']
    plan=load(HERE/'run-plan.json');assert plan['jobs']==jobs_for(rows) and len(plan['jobs'])==768
    assert plan['execution_authorized'] is False
    cfg=load(HERE/'configs.json');switches=load(HERE.parent/'switches/configs.json')
    assert [c['name'] for c in cfg['configurations']]==ARMS
    assert [c['environment'] for c in cfg['configurations']]==[switches['arms']['B0'],switches['arms']['B046'],switches['arms']['B005_006'],{'SEARCH_MODE':'mads'}]
    assert cfg['thread_environment']==switches['thread_environment']
    installed={};absent=[]
    for name,expected in source['dependency_lock']['packages'].items():
        try:installed[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            assert name=='colorama' and sys.platform=='linux';absent.append(name);continue
        assert installed[name]==expected,(name,installed[name],expected)
    assert sys.version_info[:2]==(3,12)
    refs=load(HERE/'references.json');assert set(refs['cases'])=={r['case_id'] for r in rows}
    assert sha(HERE/'references.json')==load(HERE/'references-hashes.json')['references_sha256']
    # Exercise only the configuration factory and bridge, never worker.execute/main.
    from geosolver.engine.standard.contracts.external_pipeline_config import ExternalPipelineConfig
    from types import SimpleNamespace
    from s10_worker import install
    w=SimpleNamespace(ExternalPipelineConfig=ExternalPipelineConfig);install(w,'mads')
    c=w.ExternalPipelineConfig.production_baseline_tier(seed=701,total_time_budget_sec=178)
    assert c.global_search_mode==c.baseline_search_policy.ordered_attempts[0].search_mode=='mads'
    assert ExternalPipelineConfig.production_baseline_tier(seed=701,total_time_budget_sec=178).global_search_mode=='disco_mads'
    assert verify_engine_lock()==(True,SOURCE_HASH),'adapter must not change source/default identity'
    print(json.dumps(dict(preflight_only=True,solver_executions=0,machine=a.machine,source_root=str(a.source_root),source_hash=SOURCE_HASH,
        engine_lock_valid=True,all_inputs_valid=True,planned_jobs_on_this_machine=768,gradable_references=sum(r['available'] for r in refs['cases'].values()),
        python=sys.executable,python_realpath=str(Path(sys.executable).resolve()),python_sha256=sha(Path(sys.executable).resolve()),python_version=sys.version,
        installed_dependencies=installed,absent_platform_only_dependencies=absent,host=platform.node(),platform=platform.platform(),
        eligible_cpus=sorted(os.sched_getaffinity(0)),mads_adapter_config_only_verified=True),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
