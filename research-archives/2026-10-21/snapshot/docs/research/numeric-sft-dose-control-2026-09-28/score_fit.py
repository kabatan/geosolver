"""Score the frozen dose/control comparison and its prospective transfer gate."""
import collections, json, math, statistics, sys
from pathlib import Path
import run_study as op
sys.path.insert(0,str(op.DOC))
import analyze as old_score
P,R,O=op.P,op.R,op.O

def summarize(rows):
    errors=[r['relative_error'] for r in rows if r['relative_error'] is not None]
    logs=[r['absolute_log_ratio'] for r in rows if r['absolute_log_ratio'] is not None]
    return {'n':len(rows),'correct':sum(r['numeric_correct'] is True and r['finish_reason']=='stop' for r in rows),
            'length':sum(r['finish_reason']=='length' for r in rows),'unparsed':sum(r['value'] is None for r in rows),
            'nonpositive':sum(r['value'] is not None and r['value']<=0 for r in rows),
            'median_relative_error':statistics.median(errors) if len(errors)==len(rows) else None,
            'mean_relative_error':statistics.mean(errors) if len(errors)==len(rows) else None,
            'mean_absolute_log_ratio':statistics.mean(logs) if len(logs)==len(rows) else None,
            'within_1pct':sum(e<=.01 for e in errors),'within_5pct':sum(e<=.05 for e in errors),'within_10pct':sum(e<=.1 for e in errors)}

def main():
    assert op.read(O/'fit-generation-complete.json')['status']=='complete'
    jobs=op.read(O/'fit-jobs.json');key=op.read(O/'fit-answer-key.json');caps=op.read(O/'final-cap-by-job.json')
    correct_train=op.read(O/'train-correct.json');shuffled_train=op.read(O/'train-shuffled.json')
    true_by_id={r['id']:r for r in correct_train};shuffled_by_id={r['id']:r for r in shuffled_train}
    by_source=collections.defaultdict(list)
    for row in correct_train:by_source[row['source_id']].append(float(row['target']))
    medians={s:statistics.median(v) for s,v in by_source.items()}
    rows=[]
    for arm in op.ARMS:
        for job in jobs:
            cap=caps.get(job['id'],32768);suffix='' if cap==32768 else '-'+str(cap)
            f=O/f'{arm}-fit{suffix}'/(job['id']+'-0.json');raw=op.read(f)
            assert raw['messages']==job['messages'] and raw['seed']==job['seed']
            expected=float(old_score.parse_numeric(key[job['id']]['answer_exact']))
            parsed,method,excerpt=old_score.parse(raw['raw_text']);value=None
            if parsed is not None:
                try:
                    v=float(old_score.parse_numeric(parsed))
                    if math.isfinite(v):value=v
                except (ValueError,TypeError,OverflowError):pass
            err=abs(value-expected)/expected if value is not None else None
            log=abs(math.log(value/expected)) if value is not None and value>0 else None
            row={'arm':arm,'job_id':job['id'],'source_id':job['source_id'],'split':job['split'],
                 'provenance_id':key[job['id']]['provenance_id'],'target':expected,'value':value,
                 'numeric_correct':None if value is None else abs(value-expected)<=1e-4 or err<=1e-5,
                 'relative_error':err,'absolute_log_ratio':log,'finish_reason':raw['finish_reason'],
                 'tokens':len(raw['completion_ids']),'cap':cap,'file':str(f),'file_sha256':op.sha(f),
                 'parse_method':method,'answer_excerpt':excerpt[-600:]}
            if job['split']=='trained_all':
                assigned=float(shuffled_by_id[row['provenance_id']]['target'])
                row['shuffled_target']=assigned
                row['matches_shuffled_target']=value is not None and (abs(value-assigned)<=1e-4 or abs(value-assigned)/assigned<=1e-5)
            rows.append(row)
    assert len(rows)==440
    # Baseline has access to source identity and training values, but no heldout labels.
    constant=[]
    for job in jobs:
        if job['split']!='reserved_shape':continue
        expected=float(key[job['id']]['answer_exact']);value=medians[job['source_id']]
        constant.append({'arm':'source_median','job_id':job['id'],'source_id':job['source_id'],'split':job['split'],
                         'value':value,'target':expected,'relative_error':abs(value-expected)/expected,
                         'absolute_log_ratio':abs(math.log(value/expected)),
                         'numeric_correct':abs(value-expected)<=1e-4 or abs(value-expected)/expected<=1e-5,'finish_reason':'stop'})
    summary={a:{s:summarize([r for r in rows if r['arm']==a and r['split']==s]) for s in ['trained_all','reserved_shape']} for a in op.ARMS}
    summary['source_median']={'reserved_shape':summarize(constant)}
    per_source={s:{a:summarize([r for r in rows+constant if r['source_id']==s and r['arm']==a and r['split']=='reserved_shape']) for a in op.ARMS+['source_median']} for s in sorted(by_source)}
    held={a:summary[a]['reserved_shape'] for a in summary}
    eligible=all(x['n']==30 and x['length']==x['unparsed']==x['nonpositive']==0 for x in held.values()) and all(r['finish_reason']=='stop' for r in rows if r['split']=='reserved_shape')
    refs=['base','correct128','shuffled512'];c=held['correct512']
    precision_gate=eligible and c['correct']>=max(held[a]['correct'] for a in refs)+3
    log_gate=False;wins={a:0 for a in ['shuffled512','source_median']}
    if eligible:
        wins={a:sum(per_source[s]['correct512']['mean_absolute_log_ratio']<per_source[s][a]['mean_absolute_log_ratio'] for s in per_source) for a in wins}
        log_gate=all(c['mean_absolute_log_ratio']<=.8*held[a]['mean_absolute_log_ratio'] and c['mean_absolute_log_ratio']<held[a]['mean_absolute_log_ratio'] for a in refs+['source_median']) and all(v>=7 for v in wins.values())
    gate={'eligible':eligible,'precision_gate':precision_gate,'log_error_gate':log_gate,'source_wins':wins,'run_transfer':bool(precision_gate or log_gate),
          'interpretation':'Exploratory resource-allocation rule fixed in PROTOCOL.md; not a statistical significance test.'}
    assigned={a:sum(r.get('matches_shuffled_target',False) and r['finish_reason']=='stop' for r in rows if r['arm']==a and r['split']=='trained_all') for a in op.ARMS}
    result={'status':'complete','summary':summary,'by_source':per_source,'shuffled_assigned_label_fit_counts':assigned,'transfer_gate':gate,
            'tolerances':{'absolute':1e-4,'relative':1e-5},'rows':rows,'constant_baseline_rows':constant,
            'inputs_sha256':{str(p):op.sha(p) for p in [O/'fit-jobs.json',O/'fit-answer-key.json',O/'train-correct.json',O/'train-shuffled.json',Path(__file__),P/'PROTOCOL.md']}}
    op.write(O/'fit-scores.json',result);op.write(O/'transfer-gate.json',gate)
    print(json.dumps({'summary':summary,'transfer_gate':gate,'assigned_label_fit':assigned},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
