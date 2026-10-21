"""Read-only reconstruction of the earlier RL's actual usable signal and cost."""
import json,statistics,sys
from pathlib import Path
from signal_analysis import sha,write
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];RUN=ROOT/'qwen/.runtime/numeric_rl_feasibility_20260930'
def main():
    parent=ROOT/'qwen/.runtime/exp03_staged/study/training';groups=[];updates=[];hashes={};generation=[]
    for d in sorted(parent.glob('round-*')):
        for p in sorted((d/'generation').glob('group-*.json')):
            rr=json.loads(p.read_text());hashes[str(p)]=sha(p);rewards=[r['reward'] for r in rr];natural=[r for r in rr if r['finish_reason']=='stop']
            groups.append(dict(round=d.name,id=rr[0]['id'],variant=rr[0].get('variant'),rewards=rewards,tokens=[len(r['completion_ids']) for r in rr],natural=len(natural),mixed=0<sum(rewards)<len(rr),complete_mixed=len(natural)==len(rr) and 0<sum(rewards)<len(rr),active_natural=sum(r['valid_tokens']>0 and r['advantage']!=0 for r in rr)))
        p=d/'generation/generation_metrics.json'
        if p.exists():hashes[str(p)]=sha(p);generation.append(dict(round=d.name,**json.loads(p.read_text())))
        p=d/'update/COMPLETE.json'
        if p.exists():hashes[str(p)]=sha(p);u=json.loads(p.read_text());updates.append(dict(round=d.name,**{k:v for k,v in u.items() if not isinstance(v,list)}))
    lengths=[t for g in groups for t in g['tokens']]
    summary=dict(groups=len(groups),answers=len(lengths),numeric_correct=sum(sum(g['rewards']) for g in groups),mixed_groups=sum(g['mixed'] for g in groups),complete_mixed_groups=sum(g['complete_mixed'] for g in groups),censored_answers=sum(4-g['natural'] for g in groups),active_natural_answers=sum(g['active_natural'] for g in groups),generation_tokens=sum(lengths),generation_seconds=sum(g['generation_seconds'] for g in generation),generation_process_seconds=sum(g['elapsed_seconds_this_process'] for g in generation),length_mean=statistics.mean(lengths),length_median=statistics.median(lengths),length_max=max(lengths),update_receipts=len(updates))
    write(RUN/'historical-rl-audit.json',dict(summary=summary,groups=groups,updates=updates,generation=generation,sha256=hashes))
    print(json.dumps(dict(summary=summary,update_metric_keys=sorted(set(k for u in updates for k in u))),indent=2))
if __name__=='__main__':main()
