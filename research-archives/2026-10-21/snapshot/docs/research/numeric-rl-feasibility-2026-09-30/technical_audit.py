"""Verify technical receipts and same-engine update deltas, not capability gains."""
import json,math,statistics,sys,time
from pathlib import Path
from signal_analysis import sha,write

def stats(x):
    return dict(mean_abs=statistics.mean(abs(v) for v in x),max_abs=max(abs(v) for v in x),rms=math.sqrt(statistics.mean(v*v for v in x)))
def main():
    run=Path(sys.argv[1]).resolve();selection=json.loads((run/'selection.json').read_text());probes=[]
    for c in selection['selections']:
        p=run/('probe-'+c['label']+'-tis');r=json.loads((p/'receipt.json').read_text())
        assert r['rows_sha256']==sha(c['rows']) and r['no_training_truncation']
        if r['status']=='complete':
            assert r['actual_updates']==1 and r['optimizer_steps']==[1]
            assert math.isfinite(r['grad_norm_before_clipping']) and r['grad_norm_before_clipping']>0
            assert r['changed_lora_tensors']>0 and r['saved_adapter_tensors_verified']==r['total_lora_tensors']
            assert sha(p/'adapter/adapter_model.safetensors')==r['adapter_sha256']
            assert sha(p/'adapter-vllm/adapter_model.safetensors')==r['vllm_adapter_sha256']
            assert sha(p/'optimizer.pt')==r['optimizer_sha256']
            d=json.loads((p/'details.json').read_text());rows=json.loads(Path(c['rows']).read_text())
            assert len(d)==len(rows)==4
            assert sum(a['tokens'] for a in d)==r['denominator']
            for a,b in zip(d,rows):
                assert a['tokens']==len(b['completion_ids']) and a['advantage']==b['advantage']
                fid=a['actor_learner'];assert fid['original_gate_pass']==(fid['mean_abs']<=.02 and fid['max_abs']<=.2)
                cor=a['importance_correction'];assert all(math.isfinite(v) for v in cor.values())
                assert 0<cor['min_weight']<=cor['max_weight']<=2 and 0<cor['relative_ess']<=1.000001
            fixed=json.loads((p/'fixed-probes.json').read_text());changes=[]
            for a in fixed:
                before=a['before_logps'];after=a['after_logps']
                assert len(before)==len(after)>0 and all(math.isfinite(v) for v in before+after)
                changes.extend(b-a for a,b in zip(before,after))
            assert max(abs(v) for v in changes)>0
            r['fixed_learner_delta']=stats(changes)
        else:
            assert r['status']=='failed' and 'error' in r
        probes.append(dict(label=c['label'],id=c['group']['id'],receipt=r))
    original=[]
    for c in selection['selections']:
        path=run/('probe-'+c['label'])/'receipt.json';orig=json.loads(path.read_text())
        assert orig['status']=='failed' and orig['actual_updates']==0 and 'fidelity' in orig['error']
        original.append(dict(label=c['label'],receipt=orig,sha256=sha(path)))
    for path,h in json.loads((run/'importance-amendment-freeze.json').read_text())['sha256'].items():assert sha(path)==h
    actor=None;p=run/'actor-reload'
    if (p/'receipt.json').exists():
        ar=json.loads((p/'receipt.json').read_text());actor=dict(receipt=ar)
        if ar['status']=='complete':
            short=next(x for x in probes if x['label']=='short')['receipt']
            assert ar['adapter_sha256']==short['vllm_adapter_sha256']
            zero=json.loads((run/'actor-zero-control-receipt.json').read_text());assert zero['source_sha256']==ar['adapter_sha256'] and zero['zero_sha256']==ar['zero_adapter_sha256']
            for path,h in json.loads((run/'controlled-actor-freeze.json').read_text())['sha256'].items():assert sha(path)==h
            checks=json.loads((p/'actor-verification.json').read_text());actor_delta=[];learner_delta=[];before_res=[];after_res=[];zero_path_delta=[]
            for v in checks:
                ab,aa,lb,la=[v[k] for k in ('actor_before_logps','actor_after_logps','learner_before_logps','learner_after_logps')]
                assert len(ab)==len(aa)==len(lb)==len(la)>0
                assert all(math.isfinite(x) for x in ab+aa+lb+la)
                zero_path_delta.extend(a-b for a,b in zip(ab,v['actor_unadapted_logps']));actor_delta.extend(b-a for a,b in zip(ab,aa));learner_delta.extend(b-a for a,b in zip(lb,la))
                before_res.extend(a-b for a,b in zip(ab,lb));after_res.extend(a-b for a,b in zip(aa,la))
            assert max(abs(x) for x in actor_delta)>0
            residual=[a-b for a,b in zip(actor_delta,learner_delta)]
            actor.update(zero_lora_vs_no_lora_delta=stats(zero_path_delta),actor_delta=stats(actor_delta),learner_delta=stats(learner_delta),delta_residual=stats(residual),base_backend_residual=stats(before_res),updated_backend_residual=stats(after_res),delta_cosine=sum(a*b for a,b in zip(actor_delta,learner_delta))/math.sqrt(sum(a*a for a in actor_delta)*sum(b*b for b in learner_delta)))
    out=dict(status='pass',unix=time.time(),scope='Receipt/hash/full-trajectory/actual-update/actor-reflection checks; not transfer or improvement',original_fidelity_gate='failed in both groups; preserved with zero updates',original_probes=original,probes=probes,actor=actor)
    write(run/'technical-audit.json',out);print(json.dumps(out,indent=2))
if __name__=='__main__':main()
