"""Descriptive one-pass cost scenarios, conditional on this selected screen."""
import json,sys
from pathlib import Path
from signal_analysis import write

def main():
    run=Path(sys.argv[1]);a=json.loads((run/'mechanical-audit.json').read_text());t=json.loads((run/'technical-audit.json').read_text());s=json.loads((run/'signal-summary.json').read_text())['groups'];r=json.loads((run/'screen-scores.json').read_text())
    n=a['final_problems'];mix=sum(g['mixed'] for g in s)/n
    final_gen=a['final_generation_seconds']/n
    actual_gen=sum(stage['generation_seconds'] for stage in a['stages'])/n
    fb=[p['receipt']['forward_backward_seconds'] for p in t['probes'] if p['receipt']['status']=='complete']
    steps=[p['receipt']['optimizer_seconds'] for p in t['probes'] if p['receipt']['status']=='complete']
    ar=json.loads((run/'actor-reload/receipt.json').read_text());assert ar['status']=='complete'
    actor_rows=json.loads((run/'actor-reload/simple-H04.json').read_text());actor_speed=sum(len(x['completion_ids']) for x in actor_rows)/ar['generation_seconds']
    lora_gen=sum(stage['tokens'] for stage in a['stages'])/n/actor_speed
    scenarios=[]
    for count in (256,1024,3443):
        item=dict(problems=count,answers_per_problem=4,passes=1,generation_hours_final_only=count*final_gen/3600,generation_hours_including_observed_extension_policy=count*actual_gen/3600,assumed_mixed_fraction=mix,expected_active_groups=count*mix)
        if fb:
            item.update(learning_hours_min=count*mix*(min(fb)+min(steps))/3600,learning_hours_max=count*mix*(max(fb)+max(steps))/3600)
            item['generation_plus_learning_hours_min']=item['generation_hours_including_observed_extension_policy']+item['learning_hours_min']
            item['generation_plus_learning_hours_max']=item['generation_hours_including_observed_extension_policy']+item['learning_hours_max']
        item['lora_actor_generation_hours_conditional']=count*lora_gen/3600
        if fb:
            item['lora_actor_generation_plus_learning_hours_min']=item['lora_actor_generation_hours_conditional']+item['learning_hours_min']
            item['lora_actor_generation_plus_learning_hours_max']=item['lora_actor_generation_hours_conditional']+item['learning_hours_max']
        scenarios.append(item)
    token_geometry=[]
    for g in s:
        rr=[x for x in r if x['id']==g['id']]
        token_geometry.append(dict(id=g['id'],mixed=g['mixed'],total_tokens=sum(len(x['completion_ids']) for x in rr),reward_positive_tokens=sum(len(x['completion_ids']) for x in rr if x['reward']==1),signed_advantage_token_sum=sum(len(x['completion_ids'])*(x['advantage'] or 0) for x in rr)))
    write(run/'cost-projection.json',dict(scope='conditional descriptive extrapolation; 12 purposively selected problems are not representative of a population; no throughput scaling claim for G=8',lora_actor_tokens_per_second=actor_speed,lora_actor_seconds_per_group_conditional=lora_gen,seconds_per_four_answers_final=final_gen,seconds_per_four_answers_with_extensions=actual_gen,full_update_fb_range_seconds=fb,load_save_actor_reload_not_in_projection=True,overhead_formula='per learner batch: load+save+actor load; failed attempts and guard startup require separate budget; for K batches add K measured overheads; multiple passes multiply generation and learning terms',answers_naturally_ended_within_1024=sum(x['finish_reason']=='stop' and len(x['completion_ids'])<=1024 for x in r),scenarios=scenarios,token_weighting=token_geometry))
    print(json.dumps(scenarios,indent=2))
if __name__=='__main__':main()
