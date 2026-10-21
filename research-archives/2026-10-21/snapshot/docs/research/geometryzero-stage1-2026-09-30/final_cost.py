import json,statistics
from prepare import HERE,RUN,write
def main():
 m=json.loads((HERE/'measurements.json').read_text());g=m['generation_projection']['per_question_mean_seconds'];rs=[m['update_measurements'][k] for k in ['update-DA08','update-DA06']];train=[r['old_logp_seconds']+r['forward_backward_seconds']+r['optimizer_seconds'] for r in rs];amortized=[r['old_logp_seconds']+r['forward_backward_seconds']+r['optimizer_seconds']/4 for r in rs]
 actors=[json.loads((RUN/x/'receipt.json').read_text()) for x in ['actor-base','actor-updated-DA08','actor-updated-DA06']];loads=[a['loading_seconds'] for a in actors]
 # Operational bound assumes a serial worker restart, CPU state allocation and model
 # save at every question. This is a cost scenario, not a resumable training recipe.
 overhead_min=min(r['loading_seconds']+r['optimizer_init_seconds']+r['save_verify_seconds'] for r in rs)+min(loads)+3
 overhead_max=max(r['loading_seconds']+r['optimizer_init_seconds']+r['save_verify_seconds'] for r in rs)+max(loads)+5
 out=dict(hardware='one RTX5090 32GiB, CPU optimizer four threads, 61GiB RAM',generation_seconds_per_question=g,training_seconds_per_question=train,actor_load_seconds=loads,serial_restart_extra_seconds_per_question_range=[overhead_min,overhead_max],estimates={})
 for n in [148,592]:
  out['estimates'][str(n)]=dict(generation_hours=g*n/3600,serial_compute_hours_range=[(g+min(train))*n/3600,(g+max(train))*n/3600],serial_operational_scenario_hours_range=[(g+min(train)+overhead_min)*n/3600,(g+max(train)+overhead_max)*n/3600],batch32_amortized_compute_only_hours_range=[(g+min(amortized))*n/3600,(g+max(amortized))*n/3600])
 out['limits']=['Only Qwen2.5-3B and current cap1024 tested; do not apply to 7B/9B or longer reasoning.','24 originals, not all148 variants; two selected groups measure finite per-group update costs.','Batch32 assumes 32 sequences=4 questions×8 and divides optimizer cost by4; actual accumulated-gradient batch throughput is unmeasured.','Restart scenario reallocation is an overhead bound; real training must retain FP32 master/moments across steps, not restart from quantized BF16 checkpoints each question.','Optimizer full resume, production actor synchronization, KL/reference overhead, stage2 quality evaluations and extra seeds are unmeasured.','Protocol2048 extension was not triggered; cap increases in later training change cost.','Current BF16 fidelity fails; operational estimates do not certify RL correctness.']
 write(HERE/'cost-projection.json',out);print(json.dumps(out,indent=2))
if __name__=='__main__':main()
