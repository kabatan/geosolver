"""Exact answer-set grading, complete denominators, paired summaries; no search."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

HERE=Path(__file__).resolve().parent

def load(path): return json.loads(path.read_text())
def save(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def encoded(x):return json.dumps(x,separators=(',',':'),sort_keys=True)
def answer_key(answer):
    def value_key(v):return [v['minimal_polynomial'],v['real_root_index']]
    if answer['kind']=='algebraic':return ['algebraic',*value_key(answer['value'])]
    return ['affine_pi',value_key(answer['pi_coefficient']),value_key(answer['constant'])]
def decimal(answer):return answer.get('decimal',answer.get('value',{}).get('decimal'))
def write_csv(path,rows):
    if not rows:return
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader()
        for row in rows:writer.writerow({k:encoded(v) if isinstance(v,(list,dict)) else v for k,v in row.items()})

def collect(include_missing=True):
    manifest=load(HERE/'manifest.json'); amendment=load(HERE/'execution-amendment.json')
    raw=Path(amendment['raw_directory']);rows=[]; results={}
    for inp in manifest['inputs']:
        for seed in manifest['solver_seeds']:
            p=raw/'runs'/inp['id']/inp['arm']/f'{seed}.receipt.json'
            if p.exists():
                r=load(p); r.pop('load_start',None);r.pop('load_end',None)
                result=load(Path(r['raw_path'])) if Path(r['raw_path']).exists() else {}
            elif not include_missing:continue
            else:r=dict(id=inp['id'],group=inp['group'],arm=inp['arm'],seed=seed,status='not_completed',elapsed_seconds=None);result={}
            answers=result.get('answers',[]);keys=sorted(set(encoded(answer_key(a)) for a in answers))
            ref=encoded(inp['reference_key'])
            normal=r['status'] in ('solved','no_answer_found') and not r.get('contract_issues') and r.get('returncode')==0
            dia=result.get('diagnostics',{});summary=dia.get('pipeline_summary',{})
            source_info=dia.get('process_info',{})
            r.update(reference=inp['reference'],reference_key=ref,reference_recovered=bool(normal and ref in keys),
                reference_singleton=bool(normal and keys==[ref]),returned_answer_count=len(keys),
                returned_keys=keys,returned_values=[decimal(a) for a in answers],
                other_value_count=sum(k!=ref for k in keys),normal_completion=normal,
                cpu_seconds=source_info.get('cpu_seconds'),numeric_feasible=dia.get('numeric_feasible',False),
                accepted_figures=sum(c.get('accepted',False) for c in dia.get('candidate_records',[])),
                refined_candidates=len(dia.get('candidate_records',[])),
                category=(inp['choice'] or {}).get('category','forward'),
                unknown_expression=(inp['choice'] or {}).get('expression'),
                phase_timings=dia.get('phase_timings',{}),
                search_evaluations=summary.get('search',{}).get('evaluation_count'),
                refinement_attempted=summary.get('refinement',{}).get('attempted_count'),
                refinement_converged=summary.get('refinement',{}).get('converged_count'),
                rejection_tags=dia.get('rejection_tags',[]))
            r['capped_time_to_reference']=min(180,float(r['elapsed_seconds'])) if r['reference_recovered'] else 180.
            for phase in ['search','refinement','exact_assembly','initial_probe']:
                r['seconds_'+phase]=r['phase_timings'].get(phase)
            rows.append(r);results[(inp['id'],inp['arm'],seed)]=result
    return manifest,rows,results

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--partial',action='store_true');args=parser.parse_args()
    manifest,rows,_=collect(not args.partial)
    if args.partial:
        print(json.dumps(dict(completed=len(rows),statuses=dict(Counter(r['status'] for r in rows)),
                              recovered=sum(r['reference_recovered'] for r in rows),
                              extra=sum(r['other_value_count']>0 for r in rows)),ensure_ascii=False));return
    assert all(r['status']!='not_completed' for r in rows),'campaign incomplete'
    write_csv(HERE/'per-run.csv',rows)
    forward={(r['id'],r['seed']):r for r in rows if r['arm']=='forward'}
    by_arm=defaultdict(list)
    for r in rows:by_arm[(r['id'],r['arm'])].append(r)
    arms=[];paired=[]
    for (cid,arm),rs in by_arm.items():
        rs=sorted(rs,key=lambda r:r['seed']);base=[forward[(cid,r['seed'])] for r in rs]
        ratios=[r['capped_time_to_reference']/b['capped_time_to_reference'] for r,b in zip(rs,base)]
        actual=[r['elapsed_seconds'] for r in rs]
        a=dict(id=cid,group=rs[0]['group'],arm=arm,category=rs[0]['category'],unknown_expression=rs[0]['unknown_expression'],
               reference=rs[0]['reference'],runs=len(rs),recovered=sum(r['reference_recovered'] for r in rs),
               singleton=sum(r['reference_singleton'] for r in rs),other_value_runs=sum(r['other_value_count']>0 for r in rs),
               median_seconds=st.median(actual),seconds_by_seed=actual,
               baseline_median_seconds=st.median(b['elapsed_seconds'] for b in base),
               baseline_recovered=sum(b['reference_recovered'] for b in base),
               median_time_ratio=st.median(ratios),ratios_by_seed=ratios,
               reference_hits_by_seed=[r['reference_recovered'] for r in rs],
               values_by_seed=[r['returned_values'] for r in rs],
               same_returned_set_all_seeds=len({encoded(r['returned_keys']) for r in rs})==1,
               cpu_seconds_by_seed=[r['cpu_seconds'] for r in rs],
               baseline_cpu_seconds_by_seed=[b['cpu_seconds'] for b in base],
               cpu_ratios_by_seed=[r['cpu_seconds']/b['cpu_seconds'] if r['cpu_seconds'] is not None and b['cpu_seconds'] else None for r,b in zip(rs,base)],
               faster_all_seeds=all(x<1 for x in ratios),slower_all_seeds=all(x>1 for x in ratios),
               median_search_seconds=st.median(r['seconds_search'] or 0 for r in rs),
               median_refinement_seconds=st.median(r['seconds_refinement'] or 0 for r in rs),
               median_exact_seconds=st.median(r['seconds_exact_assembly'] or 0 for r in rs))
        arms.append(a)
        if arm=='forward':continue
        for r,b,ratio in zip(rs,base,ratios):
            paired.append(dict(id=cid,group=r['group'],arm=arm,seed=r['seed'],category=r['category'],
                forward_recovered=b['reference_recovered'],inverse_recovered=r['reference_recovered'],
                forward_singleton=b['reference_singleton'],inverse_singleton=r['reference_singleton'],
                inverse_other_values=r['other_value_count'],forward_seconds=b['elapsed_seconds'],
                inverse_seconds=r['elapsed_seconds'],capped_time_ratio=ratio,
                raw_time_ratio=r['elapsed_seconds']/b['elapsed_seconds'],
                forward_status=b['status'],inverse_status=r['status']))
    write_csv(HERE/'per-arm.csv',arms);write_csv(HERE/'paired.csv',paired)
    def summarize(rs):
        return dict(runs=len(rs),recovered=sum(r['reference_recovered'] for r in rs),
            singleton=sum(r['reference_singleton'] for r in rs),other_value_runs=sum(r['other_value_count']>0 for r in rs),
            statuses=dict(Counter(r['status'] for r in rs)),median_seconds=st.median(r['elapsed_seconds'] for r in rs),
            total_wall_seconds=sum(r['elapsed_seconds'] for r in rs),
            median_capped_time_to_reference=st.median(r['capped_time_to_reference'] for r in rs))
    summary=dict(problems=manifest['selected_problem_count'],conditions=len(manifest['inputs']),
                 forward=summarize([r for r in rows if r['arm']=='forward']),
                 inverse=summarize([r for r in rows if r['arm']!='forward']),
                 per_seed={str(s):{kind:summarize([r for r in rows if r['seed']==s and (r['arm']=='forward')==(kind=='forward')])
                                   for kind in ['forward','inverse']} for s in manifest['solver_seeds']},
                 per_group={g:{kind:summarize([r for r in rows if r['group']==g and (r['arm']=='forward')==(kind=='forward')])
                               for kind in ['forward','inverse']} for g in sorted({r['group'] for r in rows})},
                 contract_issues=[(r['id'],r['arm'],r['seed'],r['contract_issues']) for r in rows if r.get('contract_issues')])
    inverse=[a for a in arms if a['arm']!='forward']
    summary['stable_3_of_3_vs_0_of_3_improvements']=[a for a in inverse if a['recovered']==3 and a['baseline_recovered']==0]
    summary['stable_3_of_3_vs_0_of_3_losses']=[a for a in inverse if a['recovered']==0 and a['baseline_recovered']==3]
    summary['fastest_inverse_ratios']=sorted(inverse,key=lambda a:a['median_time_ratio'])[:12]
    summary['slowest_inverse_ratios']=sorted(inverse,key=lambda a:-a['median_time_ratio'])[:12]
    summary['other_values_problems']=sorted({a['id'] for a in inverse if a['other_value_runs']})
    initial=Path(load(HERE/'execution-amendment.json')['initial_attempt_directory'])
    failed=[load(p) for p in sorted(initial.glob('*/*/*.receipt.json'))]
    assert len(failed)==228
    write_csv(HERE/'initial-launch-failures.csv',failed)
    summary['all_attempts']=dict(initial_invalid_configuration=228,production_runs=len(rows),
                               total=228+len(rows),reference_recovered=sum(r['reference_recovered'] for r in rows),
                               note='Initial 228 failures precede engine entry; all kept, no substitutions.')
    save(HERE/'summary.json',summary)
    print(json.dumps({k:summary[k] for k in ['forward','inverse','per_seed','all_attempts']},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
