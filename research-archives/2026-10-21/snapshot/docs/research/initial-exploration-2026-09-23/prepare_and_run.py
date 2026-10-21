"""Small inference-only exploration pilot; frozen inputs, no policy updates."""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path
from qwen.common import file_hash, write_json, now
from qwen.models import locked_models
from qwen.grpo_run import run_worker

HERE = Path(__file__).resolve().parent
ROOT = Path('qwen/.runtime/exp04_exploration')
IDS = ['H01', 'H02', 'H04', 'DA01', 'DA03', 'DA04', 'DA05', 'DA15']
COMMON = '\n\n与条件から答えに至る数学的な根拠を示してください。解決の核心となる関係も論証し、既知の点の名称や性質への言及だけで済ませないでください。座標による解法も使用できます。最終的な数値を \\boxed{...} に入れてください。'
EXTRA = '\n必要なら、問題文にない補助点・補助円・補助線を自分で提案してください。それによって得られる関係が正しく、計算や論証を簡単にするかを確かめ、有効なものを解法に使ってください。'

def main():
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument('--run', action='store_true')
    args = ap.parse_args()
    source = Path('benchmarks/humpty_configurations_v2/training_problems.jsonl')
    rows = {r['id']:r for r in map(json.loads, source.read_text().splitlines())}
    selected = [rows[i] for i in IDS]
    jobs = []
    for index, r in enumerate(selected):
        order = ['normal','explore'] if index % 2 == 0 else ['explore','normal']
        for condition in order:
            jobs.append({**r, 'variant':'v0', 'condition':condition, 'source_problem':r['problem'],
                         'problem':r['problem'] + COMMON + (EXTRA if condition == 'explore' else '')})
    models = locked_models(verify_weights=args.run)
    model = models['qwen3_4b']
    command = [sys.executable, '-m', 'qwen.grpo_stage', 'generate', '--route','fp16_native',
               '--jobs',str(HERE / 'jobs.json'),'--output',str(ROOT / 'generation'),
               '--samples','4','--seed','2026092301','--max-seqs','4', '--max-completion','32512']
    protocol = {
        'study':'exp04_initial_exploration', 'model_id':model['model_id'],
        'model_revision':model['revision'], 'model_files':model['files'], 'adapter':None,
        'ids':IDS, 'conditions':['normal','explore'], 'samples_per_condition':4,
        'maximum_answers':64, 'common_instruction':COMMON, 'exploration_instruction':EXTRA,
        'precision':'fp16_native', 'temperature':0.6,'top_p':0.95,'top_k':20,
        'seed':2026092301,'max_completion':32512,'context_limit':32768,'worker_limit_seconds':14400,
        'input_source':str(source), 'input_source_sha256':file_hash(source),
        'code_sha256':{str(p):file_hash(p) for p in [Path(__file__),Path('qwen/grpo_stage.py'),Path('qwen/fast_engine.py'),Path('qwen/models.py'),Path('qwen/answer_check.py'),Path('qwen/common.py')]},
        'command':command,
        'purpose':'Inference-only feasibility: self-proposed useful constructions with no supplied solution or target theorem. Not a transfer/learning efficacy trial.',
        'grading':{
            'C':'Exact numeric match; preserve auto result and any separately justified adjudication.',
            'V':'Final presented solution is valid. Missing core argument, circularity, or using one special configuration as general are not accepted.',
            'U':'A correct structural relation actually simplifies the calculation or proof. Only V=true solutions count as accepted successes.',
            'new_aux':'A point/circle/line absent from the problem, explicitly defined and functionally used. Distinguish structural construction from routine coordinate variables/feet.',
            'target':'Humpty/Dumpty-equivalent structure; record separately from generic valid helpers.',
            'unresolved':'Keep uncertain; never complete a missing proof on behalf of the model.'},
        'decision_reference':'Prior proposal: roughly 8 complete useful-construction examples across ~4 structural families would justify considering learning; not a statistical power criterion.',
        'no_weight_update':True,'no_external_solution_in_prompts':True,
        'label_provenance':'Existing approved v2 numeric labels; independently verified dataset, not newly solver-generated labels in this pilot.',
    }
    for path, value in [(HERE/'jobs.json',jobs),(HERE/'protocol.json',protocol)]:
        if path.exists():
            if json.loads(path.read_text()) != value: raise RuntimeError(f'Frozen input changed: {path}')
        else: write_json(path,value)
    ROOT.mkdir(parents=True, exist_ok=True)
    print(json.dumps({'answers':64,'protocol':str(HERE/'protocol.json'),'run':args.run}),flush=True)
    if not args.run: return
    receipt = ROOT/'worker_receipt.json'
    if receipt.exists(): raise RuntimeError('Prior run receipt exists; inspect before any retry')
    start = time.monotonic()
    record = {'start_utc':now(),'command':command,'protocol_sha256':file_hash(HERE/'protocol.json'),
              'jobs_sha256':file_hash(HERE/'jobs.json'),'status':'running','updates':0}
    write_json(receipt,record)
    try:
        run_worker(command,ROOT/'generate.log',14400)
        record['status']='complete'
    except BaseException as e:
        record['status']='failed';record['error']=str(e);raise
    finally:
        record['end_utc']=now();record['elapsed_seconds']=time.monotonic()-start
        write_json(receipt,record);print(json.dumps(record,ensure_ascii=False),flush=True)

if __name__=='__main__': main()
