"""Alternate complete on-policy generation and exact KL updates, with receipts.

Run under the shared GPU guard. Generation/training use separate processes.
Long retries preserve the current policy, numerical problem and sampling seed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
WORKER_PYTHON = ROOT / "qwen/.runtime/vllm-venv/bin/python"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def launch(command, logfile, timeout):
    with logfile.open('w') as stream:
        proc = subprocess.Popen([str(x) for x in command], stdout=stream, stderr=subprocess.STDOUT,
                                start_new_session=True)
        try:
            code = proc.wait(timeout=timeout)
            if code:
                raise RuntimeError(f'Worker exit {code}; inspect {logfile}')
        except BaseException:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL); proc.wait()
            raise


def read_complete(path):
    value = json.loads(path.read_text())
    if value.get('status') != 'complete':
        raise RuntimeError(f'Incomplete worker receipt: {path}')
    return value


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', type=Path, required=True)
    ap.add_argument('--pool', type=Path, required=True)
    ap.add_argument('--eval-jobs', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--start-round', type=int, default=1)
    ap.add_argument('--end-round', type=int, default=16)
    ap.add_argument('--prior-checkpoint', type=Path)
    ap.add_argument('--preflight', action='store_true')
    args = ap.parse_args()
    config = json.loads(args.config.read_text()); pool = json.loads(args.pool.read_text())
    if not 1 <= args.start_round <= args.end_round <= 16 or len(pool) < args.end_round*8:
        raise ValueError('Only the fixed first 128 scheduled trajectories are allowed')
    if config.get('activation_offload') not in ('none','cpu'):
        raise ValueError('Capacity-tested activation mode must be explicit')
    prior = args.prior_checkpoint.resolve() if args.prior_checkpoint else None
    if bool(prior) != (args.start_round > 1):
        raise ValueError('Fresh first round, otherwise explicit previous checkpoint required')
    if prior:
        previous=read_complete(prior/'receipt.json')
        if previous['round'] != args.start_round-1 or previous['global_updates'] != (args.start_round-1)*2:
            raise ValueError('Resume does not immediately follow requested round')
    evaluation=json.loads(args.eval_jobs.read_text())
    trained={r['source_id'] for r in pool[:128]}
    if trained.intersection(j['source_id'] for j in evaluation):
        raise ValueError('Configuration leakage into primary evaluation')
    if args.preflight:
        print(json.dumps({'status':'preflight_pass','rounds':args.end_round-args.start_round+1,
                          'examples':8*(args.end_round-args.start_round+1),
                          'expected_global_updates':2*args.end_round,'trained_ids':sorted(trained)}));return
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    files=[args.config,args.pool,args.eval_jobs,HERE/'rollout_long.py',HERE/'train_worker.py',
           HERE.parent/'answer-opd-pilot-2026-09-26/rollout_worker.py',
           HERE/'streamed_kl.py',HERE/'PROTOCOL_FORMAL.md',Path(__file__)]
    frozen={str(p.resolve()):digest(p) for p in files}
    receipt=dict(status='running',start_unix=time.time(),inputs=frozen,start_round=args.start_round,
                 end_round=args.end_round,rounds_completed=0,updates=0,global_updates=2*(args.start_round-1),
                 initial_checkpoint=str(prior) if prior else None,trained_completion_tokens=0,
                 extended_trajectories=0,censored_trajectories=0)
    write(out/'receipt.json',receipt);started=time.monotonic()
    try:
        for round_number in range(args.start_round,args.end_round+1):
            if any(digest(p)!=h for p,h in frozen.items()):
                raise RuntimeError('An experiment input changed during the run')
            tick=time.monotonic(); rd=out/f'round-{round_number:03d}';rd.mkdir()
            cfg=json.loads(json.dumps(config));cfg['prior_checkpoint']=str(prior) if prior else None
            cfg['rollout'].update(generation_max_tokens=32768,max_model_len=40960)
            config_path=rd/'config.json';write(config_path,cfg)
            base_cmd=[WORKER_PYTHON,HERE/'rollout_long.py','--pool',args.pool.resolve(),
                      '--round',str(round_number),'--start-index',str((round_number-1)*8)]
            if prior:base_cmd += ['--checkpoint',prior]
            normal=rd/'rollout32k'
            launch(base_cmd+['--config',config_path,'--out',normal],rd/'rollout32k.log',config['rollout_timeout_seconds'])
            rr=read_complete(normal/'receipt.json')
            batch=json.loads((normal/'batch.json').read_text())
            raw=json.loads((normal/'raw_rollouts.json').read_text())
            capped=[r['id'] for r in batch['examples'] if r['finish_reason']=='length']
            selections={r['id']:{'budget':32768,'raw_directory':str(normal)} for r in batch['examples']}
            if capped:
                extended_cfg=json.loads(json.dumps(cfg))
                extended_cfg['rollout'].update(generation_max_tokens=81920,max_model_len=98304)
                extended_path=rd/'config-extended.json';write(extended_path,extended_cfg)
                extended=rd/'rollout81k'
                command=base_cmd+['--config',extended_path,'--out',extended]
                for row_id in capped:command+=['--only-id',row_id]
                launch(command,rd/'rollout81k.log',config['rollout_timeout_seconds'])
                read_complete(extended/'receipt.json')
                newbatch=json.loads((extended/'batch.json').read_text())
                newraw=json.loads((extended/'raw_rollouts.json').read_text())
                if newbatch['policy_adapter_sha256']!=batch['policy_adapter_sha256']:
                    raise RuntimeError('Retry used a different student policy')
                replacements={r['id']:r for r in newbatch['examples']}
                if set(replacements)!=set(capped):raise RuntimeError('Retry lost or added trajectories')
                for row in batch['examples']:
                    if row['id'] in replacements:
                        replacement=replacements[row['id']]
                        selections[row['id']]=dict(budget=81920,raw_directory=str(extended),
                            original_prefix_identical=(replacement['completion_ids'][:len(row['completion_ids'])]==row['completion_ids']))
                batch['examples']=[replacements.get(r['id'],r) for r in batch['examples']]
                raw_by_id={r['id']:r for r in newraw};raw=[raw_by_id.get(r['id'],r) for r in raw]
                receipt['extended_trajectories']+=len(capped)
            write(rd/'selected-batch.json',batch);write(rd/'selected-raw.json',raw)
            write(rd/'selection-provenance.json',selections)
            if len(batch['examples'])!=8 or len({r['id'] for r in batch['examples']})!=8:
                raise RuntimeError('Each update round must keep all eight scheduled examples')
            scheduled=pool[(round_number-1)*8:round_number*8]
            if [r['id'] for r in batch['examples']] != [r['id'] for r in scheduled]:
                raise RuntimeError('Selected trajectories differ from the frozen scheduled order')
            incomplete=[r['id'] for r in batch['examples'] if r['finish_reason']!='stop']
            if incomplete:
                receipt['censored_trajectories']+=len(incomplete)
                raise RuntimeError(f'Incomplete after long retry; refusing prefix training: {incomplete}')
            training=rd/'train'
            launch([WORKER_PYTHON,HERE/'train_worker.py','--config',config_path,
                    '--batch',rd/'selected-batch.json','--out',training],rd/'train.log',config['train_timeout_seconds'])
            tr=read_complete(training/'receipt.json')
            if tr['n_examples']!=8 or tr['updates']!=2 or tr['global_updates']!=2*round_number or tr['truncated_prefixes']:
                raise RuntimeError('Trainer did not complete the fixed full-trajectory updates')
            prior=training
            receipt['rounds_completed']+=1;receipt['updates']+=2;receipt['global_updates']=tr['global_updates']
            receipt['trained_completion_tokens']+=tr['trained_completion_tokens']
            receipt.update(last_checkpoint=str(prior),last_adapter_sha256=tr['adapter_sha256'],
                           last_vllm_adapter_sha256=tr['vllm_adapter_sha256'])
            write(out/'receipt.json',receipt)
            print(json.dumps({'round':round_number,'global_updates':tr['global_updates'],
                              'tokens':tr['trained_completion_tokens'],'extended':len(capped),
                              'seconds':time.monotonic()-tick,'checkpoint':str(prior)}),flush=True)
        receipt['status']='complete'
    except BaseException as error:
        receipt.update(status='failed',error=repr(error));raise
    finally:
        receipt.update(end_unix=time.time(),elapsed_seconds=time.monotonic()-started)
        write(out/'receipt.json',receipt)


if __name__=='__main__':
    main()
