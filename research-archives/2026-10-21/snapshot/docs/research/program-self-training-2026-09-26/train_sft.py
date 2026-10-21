"""Fixed-update assistant-only Qwen3.5-9B LoRA SFT for numeric/code targets.

CPU preflight/tokenization does not load model weights. GPU work requires an
explicit --config/--out run; there is no automatic generation or evaluation.
"""
import os
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")

import argparse
import gc
import hashlib
import importlib.util
import importlib.metadata
import json
import math
from pathlib import Path
import random
import time

import torch

HERE = Path(__file__).resolve().parent
MAPPING_HELPER = HERE.parent / "answer-opd-pilot-2026-09-26/train_worker.py"
MODULES = ["q_proj", "k_proj", "v_proj", "o_proj", "in_proj_qkv", "in_proj_z", "out_proj", "gate_proj", "up_proj", "down_proj"]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    temp.replace(path)


def mapping_helpers():
    spec = importlib.util.spec_from_file_location("verified_opd_mapping", MAPPING_HELPER)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.verify_saved_adapter, module.export_vllm_adapter


class ChunkedCrossEntropy(torch.autograd.Function):
    """Exact mean full-vocabulary CE with FP32 normalization in token chunks.

    Retain BF16 model logits, recompute chunk softmax in backward, and never
    retain a full-sequence FP32 softmax graph. This is not vocabulary sampling.
    """
    @staticmethod
    def forward(ctx, logits, target, chunk_tokens):
        if logits.ndim != 2 or target.ndim != 1 or len(target) != len(logits) or not len(target) or chunk_tokens < 1:
            raise ValueError("invalid CE shape/chunk")
        ctx.save_for_backward(logits, target); ctx.chunk_tokens = chunk_tokens
        total = torch.zeros((), device=logits.device, dtype=torch.float32)
        for start in range(0, len(target), chunk_tokens):
            end = min(start+chunk_tokens, len(target))
            total += torch.nn.functional.cross_entropy(logits[start:end].float(), target[start:end], reduction="sum")
        return total / len(target)

    @staticmethod
    def backward(ctx, grad_output):
        logits, target = ctx.saved_tensors
        grad = torch.empty_like(logits)
        for start in range(0, len(target), ctx.chunk_tokens):
            end = min(start+ctx.chunk_tokens, len(target))
            probabilities = logits[start:end].float().softmax(-1)
            probabilities[torch.arange(end-start, device=logits.device), target[start:end]] -= 1
            grad[start:end] = (probabilities * (grad_output / len(target))).to(logits.dtype)
        return grad, None, None


def cpu_check():
    torch.manual_seed(2026092701)
    errors = []
    for n, chunk, dtype in [(1, 64, torch.float32), (9, 4, torch.float32), (17, 3, torch.bfloat16)]:
        x = torch.randn(n, 29, dtype=dtype, requires_grad=True)
        y = torch.randint(29, (n,))
        dense = torch.nn.functional.cross_entropy(x.float(), y)
        dg, = torch.autograd.grad(dense, x)
        z = x.detach().clone().requires_grad_(True)
        actual = ChunkedCrossEntropy.apply(z, y, chunk)
        ag, = torch.autograd.grad(actual, z)
        assert torch.allclose(dense, actual, atol=1e-6, rtol=1e-6)
        assert torch.allclose(dg, ag, atol=1e-7, rtol=1e-6)
        errors.append(dict(tokens=n, dtype=str(dtype), loss_difference=float((dense-actual).detach().abs()), gradient_max_difference=float((dg-ag).abs().max())))
    return dict(status="pass", equivalence=errors)


def parameters(spec):
    defaults = dict(seed=2026092701, learning_rate=5e-6, grad_accumulation=4, grad_clip=1.0,
                    lora_rank=8, lora_alpha=16, lora_modules=MODULES, ce_chunk_tokens=64,
                    max_target_tokens=4096, max_sequence_tokens=8192, enable_thinking=False)
    fixed = {k: spec.get(k, v) for k, v in defaults.items()}
    for key in ['seed','grad_accumulation','lora_rank','lora_alpha','ce_chunk_tokens','max_target_tokens','max_sequence_tokens']:
        if type(fixed[key]) is not int:
            raise ValueError(f"{key} must be integer")
    if fixed['learning_rate'] != 5e-6 or fixed['grad_accumulation'] != 4 or fixed['lora_rank'] != 8 or fixed['lora_alpha'] != 16 or fixed['lora_modules'] != MODULES or fixed['enable_thinking'] is not False:
        raise ValueError("config changes frozen SFT recipe")
    if fixed['grad_clip'] != 1 or not 1 <= fixed['ce_chunk_tokens'] <= 256 or not 1 <= fixed['max_target_tokens'] <= 8192 or not 1 <= fixed['max_sequence_tokens'] <= 16384:
        raise ValueError("invalid bounds")
    if spec.get('updates') not in (16, 32):
        raise ValueError("updates must be16or32")
    return fixed


def load_inputs(config_path):
    spec = json.loads(config_path.read_text()); fixed = parameters(spec)
    source = Path(spec['dataset']).resolve(); meta_path = Path(spec['model_metadata']).resolve()
    if digest(source) != spec['dataset_sha256'] or digest(meta_path) != spec['model_metadata_sha256']:
        raise ValueError("frozen input hash mismatch")
    meta = json.loads(meta_path.read_text())
    if meta['model_id'] != 'Qwen/Qwen3.5-9B' or meta['revision'] != spec['model_revision'] or not Path(meta['snapshot']).is_dir():
        raise ValueError("unexpected model metadata")
    raw = json.loads(source.read_text())
    if not raw or len({x['id'] for x in raw}) != len(raw):
        raise ValueError("empty/duplicate training examples")
    kinds = {x['kind'] for x in raw}
    if len(kinds) != 1 or not kinds.issubset({'numeric', 'code'}):
        raise ValueError("each arm dataset must contain one target kind")
    for row in raw:
        if not isinstance(row['source_id'], str) or not isinstance(row['target'], str) or not row['target'].strip():
            raise ValueError("invalid row target/source")
        if any(token in row['target'] for token in ['<|im_', '<think>', '</think>']):
            raise ValueError("target contains chat control tokens")
        if row['kind'] == 'numeric':
            value = float(row['target'])
            if not math.isfinite(value):
                raise ValueError("nonfinite numeric target")
        else:
            # The orchestrator must execute this exact normalized program on all
            # selection cases. The trainer verifies normalization, never repairs.
            from execution_harness import extract_program
            parsed = extract_program(row['target'], 'stop')
            expected = '```python\n' + parsed['normalized_code'] + '```'
            if row['target'].strip() != expected:
                raise ValueError("code target must be exactly one python fence around the normalized program")
        messages = row['messages']
        if not isinstance(messages, list) or not messages or any(x['role'] not in {'user','system'} or not isinstance(x['content'], str) for x in messages):
            raise ValueError("messages must contain user/system context only")
    return spec, fixed, source, meta_path, meta, raw


def tokenize_rows(raw, tokenizer, fixed):
    rows = []
    for row in raw:
        target = row['target'].strip()
        prompt = tokenizer.apply_chat_template(row['messages'], tokenize=False, add_generation_prompt=True, enable_thinking=False)
        full = tokenizer.apply_chat_template(row['messages']+[{'role':'assistant','content':target}], tokenize=False, enable_thinking=False)
        if not full.startswith(prompt):
            raise ValueError(f"chat alignment failed: {row['id']}")
        prompt_ids = tokenizer.encode(prompt, add_special_tokens=False)
        target_ids = tokenizer.encode(full[len(prompt):].rstrip(), add_special_tokens=False)
        if not target_ids or target_ids[-1] != tokenizer.eos_token_id:
            raise ValueError("assistant target must include exactly the template EOS")
        if len(target_ids) > fixed['max_target_tokens'] or len(prompt_ids)+len(target_ids) > fixed['max_sequence_tokens']:
            raise ValueError(f"complete target exceeds bound; no truncation: {row['id']}")
        rows.append(dict(id=row['id'], source_id=row['source_id'], kind=row['kind'], prompt_ids=prompt_ids, target_ids=target_ids,
                         target_text_sha256=hashlib.sha256(target.encode()).hexdigest()))
    return rows


def data_order(n_rows, n_examples, seed):
    order = []; epoch = 0
    while len(order) < n_examples:
        indices = list(range(n_rows)); random.Random(seed+epoch).shuffle(indices)
        order.extend((epoch, idx) for idx in indices); epoch += 1
    return order[:n_examples]


def order_digest(order, rows, n_examples):
    sequence = [{'epoch':epoch,'id':rows[idx]['id']} for epoch,idx in order[:n_examples]]
    return hashlib.sha256(json.dumps(sequence, sort_keys=True, separators=(',',':')).encode()).hexdigest()


def save_checkpoint(model, optimizer, out, receipt, verify_saved, export_adapter):
    out.mkdir(parents=True, exist_ok=False)
    model.save_pretrained(out/'adapter', safe_serialization=True)
    verified = verify_saved(model, out/'adapter')
    mapping = export_adapter(out/'adapter', out/'adapter-vllm')
    state = optimizer.state_dict(); torch.save(state, out/'optimizer.pt')
    loaded = torch.load(out/'optimizer.pt', map_location='cpu', weights_only=True)
    if state['param_groups'] != loaded['param_groups'] or state['state'].keys() != loaded['state'].keys():
        raise AssertionError("optimizer serialization structure differs")
    for key, values in state['state'].items():
        for name, value in values.items():
            other = loaded['state'][key][name]
            if torch.is_tensor(value):
                if not torch.equal(value.cpu(), other): raise AssertionError("optimizer tensor reload differs")
            elif value != other: raise AssertionError("optimizer value reload differs")
    row = dict(receipt, status='complete', adapter_sha256=digest(out/'adapter/adapter_model.safetensors'),
               vllm_adapter_sha256=mapping['vllm_adapter_sha256'], optimizer_sha256=digest(out/'optimizer.pt'),
               saved_adapter_tensors_verified=verified, vllm_adapter_tensors_verified=mapping['n_tensors'],
               optimizer_state_entries=len(loaded['state']))
    steps = [int(x['step'].item()) for x in loaded['state'].values()]
    if not steps or min(steps) != receipt['global_updates'] or max(steps) != receipt['global_updates']:
        raise AssertionError('optimizer step count differs from actual global updates')
    row.update(optimizer_step_min=min(steps),optimizer_step_max=max(steps))
    write_json(out/'receipt.json', row)
    return row


def run(args):
    from transformers import AutoTokenizer
    config_path = Path(args.config).resolve()
    spec, fixed, source, meta_path, meta, raw = load_inputs(config_path)
    tokenizer = AutoTokenizer.from_pretrained(meta['snapshot'], local_files_only=True)
    rows = tokenize_rows(raw, tokenizer, fixed)
    order = data_order(len(rows), spec['updates']*fixed['grad_accumulation'], fixed['seed'])
    out = Path(args.out).resolve(); out.mkdir(parents=True, exist_ok=False)
    tokenization = [dict(id=x['id'], source_id=x['source_id'], kind=x['kind'], prompt_tokens=len(x['prompt_ids']), target_tokens=len(x['target_ids']), target_text_sha256=x['target_text_sha256']) for x in rows]
    write_json(out/'tokenization.json', tokenization)
    write_json(out/'example-order.json', [{'epoch':epoch,'id':rows[idx]['id']} for epoch,idx in order])
    receipt = dict(status='preflight_complete' if args.preflight else 'running', start_unix=time.time(),
                   updates=0, global_updates=0, examples_processed=0, config_sha256=digest(config_path),
                   dataset_sha256=digest(source), model_metadata_sha256=digest(meta_path), model_revision=meta['revision'],
                   driver_sha256=digest(__file__), mapping_helper_sha256=digest(MAPPING_HELPER),
                   harness_sha256=digest(HERE/'execution_harness.py'), training_parameters=fixed,
                   planned_updates=spec['updates'], target_kind=raw[0]['kind'], n_examples=len(rows),
                   sources=sorted({x['source_id'] for x in rows}), tokenization_sha256=digest(out/'tokenization.json'),
                   example_order_sha256=digest(out/'example-order.json'), unique_target_tokens=sum(len(x['target_ids']) for x in rows),
                   planned_target_tokens=sum(len(rows[idx]['target_ids']) for _,idx in order), loss_mask='assistant target including EOS only',
                   cpu_check=cpu_check(), versions={k:importlib.metadata.version(k) for k in ['torch','transformers','peft','safetensors']})
    write_json(out/'receipt.json', receipt)
    if args.preflight:
        print(json.dumps(receipt, ensure_ascii=False)); return
    from peft import LoraConfig, PeftModel, TaskType, get_peft_model
    from transformers import AutoModelForCausalLM
    prior = Path(spec['prior_checkpoint']).resolve() if spec.get('prior_checkpoint') else None
    start_update = 0
    started = time.monotonic()
    try:
        if prior:
            prev = json.loads((prior/'receipt.json').read_text())
            if prev.get('status') != 'complete' or prev['training_parameters'] != fixed or prev['dataset_sha256'] != digest(source) or prev['model_revision'] != meta['revision']:
                raise ValueError('incompatible prior checkpoint/deterministic order')
            for key, file in [('adapter_sha256','adapter/adapter_model.safetensors'),('vllm_adapter_sha256','adapter-vllm/adapter_model.safetensors'),('optimizer_sha256','optimizer.pt')]:
                if prev[key] != digest(prior/file): raise ValueError('prior file hash mismatch')
                receipt['prior_'+key] = prev[key]
            start_update = prev['global_updates']
            if not 0 < start_update < spec['updates']: raise ValueError('prior update count is not before target')
            if prev['processed_order_sha256'] != order_digest(order,rows,start_update*4):
                raise ValueError('prior deterministic processed-example order differs')
        random.seed(fixed['seed']); torch.manual_seed(fixed['seed']); torch.cuda.manual_seed_all(fixed['seed'])
        model = AutoModelForCausalLM.from_pretrained(meta['snapshot'], dtype=torch.bfloat16, device_map='cuda', attn_implementation='sdpa', local_files_only=True)
        if prior:
            model = PeftModel.from_pretrained(model, prior/'adapter', is_trainable=True)
        else:
            model = get_peft_model(model, LoraConfig(r=8,lora_alpha=16,lora_dropout=0,target_modules=MODULES,bias='none',task_type=TaskType.CAUSAL_LM))
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False}); model.enable_input_require_grads(); model.train()
        named = [(n,p) for n,p in model.named_parameters() if p.requires_grad]
        if not named or any('lora_' not in n for n,p in named): raise AssertionError('only LoRA may train')
        trainable = [p for n,p in named]; before = {n:p.detach().float().cpu().clone() for n,p in named}
        optimizer = torch.optim.AdamW(trainable,lr=fixed['learning_rate'],weight_decay=0)
        if prior: optimizer.load_state_dict(torch.load(prior/'optimizer.pt',map_location='cpu',weights_only=True))
        receipt.update(prior_checkpoint=str(prior) if prior else None, optimizer_state_loaded=bool(prior),
                       global_updates=start_update, trainable_parameters=sum(p.numel() for p in trainable))
        verify_saved, export_adapter = mapping_helpers(); optimizer.zero_grad(set_to_none=True)
        torch.cuda.reset_peak_memory_stats()
        for position in range(start_update*4, len(order)):
            epoch, idx = order[position]; row = rows[idx]; tick=time.monotonic(); n=len(row['target_ids'])
            ids=torch.tensor([row['prompt_ids']+row['target_ids']],dtype=torch.long,device='cuda')
            target=torch.tensor(row['target_ids'],dtype=torch.long,device='cuda')
            output=model(input_ids=ids,use_cache=False,logits_to_keep=n+1)
            logits=output.logits[0,:-1,:]
            if len(logits)!=n:raise AssertionError('causal assistant alignment mismatch')
            loss=ChunkedCrossEntropy.apply(logits,target,fixed['ce_chunk_tokens'])
            if not torch.isfinite(loss):raise AssertionError('nonfinite loss')
            (loss/4).backward()
            event=dict(position=position,epoch=epoch,id=row['id'],source_id=row['source_id'],loss=float(loss.detach()),target_tokens=n)
            del ids,target,output,logits,loss
            gc.collect(); torch.cuda.empty_cache()
            receipt['examples_processed']+=1
            if (position+1)%4==0:
                norm=torch.nn.utils.clip_grad_norm_(trainable,fixed['grad_clip'])
                if not torch.isfinite(norm):raise AssertionError('nonfinite gradient')
                optimizer.step();optimizer.zero_grad(set_to_none=True)
                receipt['updates']+=1;receipt['global_updates']+=1
                receipt['processed_order_sha256']=order_digest(order,rows,(position+1))
                event.update(global_update=receipt['global_updates'],grad_norm_before_clipping=float(norm))
                if receipt['global_updates'] in spec.get('save_checkpoints', []):
                    saved=save_checkpoint(model,optimizer,out/f"checkpoint-{receipt['global_updates']:03d}",receipt,verify_saved,export_adapter)
                    receipt.setdefault('intermediate_checkpoints',[]).append({'global_updates':saved['global_updates'],'adapter_sha256':saved['adapter_sha256'],'optimizer_sha256':saved['optimizer_sha256']})
            torch.cuda.synchronize();event['seconds']=time.monotonic()-tick
            with (out/'examples.jsonl').open('a') as stream:stream.write(json.dumps(event)+'\n')
            write_json(out/'receipt.json',receipt);print(json.dumps(event),flush=True)
        changed=sum(not torch.equal(before[n],p.detach().float().cpu()) for n,p in named)
        if not changed:raise AssertionError('no adapter weights changed')
        receipt.update(changed_lora_tensors=changed,total_lora_tensors=len(named),
                       peak_allocated_gib=torch.cuda.max_memory_allocated()/2**30,
                       peak_reserved_gib=torch.cuda.max_memory_reserved()/2**30,
                       trained_target_tokens=sum(len(rows[idx]['target_ids']) for _,idx in order[start_update*4:]))
        # save_checkpoint requires a new directory. Final artifacts sit below
        # final/; its complete receipt also makes it an explicit resume target.
        final=save_checkpoint(model,optimizer,out/'final',receipt,verify_saved,export_adapter)
        receipt.update({k:final[k] for k in ['adapter_sha256','vllm_adapter_sha256','optimizer_sha256','saved_adapter_tensors_verified','vllm_adapter_tensors_verified','optimizer_state_entries','optimizer_step_min','optimizer_step_max']},status='complete',final_checkpoint=str(out/'final'))
    except BaseException as exc:
        receipt.update(status='failed',error=repr(exc));raise
    finally:
        receipt.update(end_unix=time.time(),elapsed_seconds=time.monotonic()-started);write_json(out/'receipt.json',receipt);print(json.dumps(receipt),flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--cpu-check',action='store_true');ap.add_argument('--preflight',action='store_true');ap.add_argument('--config');ap.add_argument('--out');args=ap.parse_args()
    if args.cpu_check:print(json.dumps(cpu_check()))
    elif args.config and args.out:run(args)
    else:ap.error('use --cpu-check or --config and --out (optionally --preflight)')
