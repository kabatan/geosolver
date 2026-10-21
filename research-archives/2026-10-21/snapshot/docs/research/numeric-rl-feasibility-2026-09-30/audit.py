"""Mechanical audit and descriptive statistics; does not grade mathematics."""
import json,math,statistics,sys,time
from pathlib import Path
from signal_analysis import analyze,sha,write

def main():
    run=Path(sys.argv[1]).resolve();s,rows,extensions=analyze(run)
    assert len(s)==12 and len(rows)==48
    assert json.loads((run/'screen16384/receipt.json').read_text())['status']=='complete'
    for id in extensions:assert (run/'screen32768'/(id+'.json')).exists()
    if extensions:assert json.loads((run/'screen32768/receipt.json').read_text())['status']=='complete'
    for r in rows:
        assert len(r['completion_ids'])==len(r['rollout_logps'])>0
        assert all(math.isfinite(x) for x in r['rollout_logps'])
        assert r['policy_adapter_sha256'] is None
        assert r['raw_file_sha256']==sha(r['raw_file'])
        assert len(r['prompt_ids'])+len(r['completion_ids'])<=40960
    mixed={g['id'] for g in s if g['mixed']}
    required={(r['raw_file_sha256'],r['sample']) for r in rows if r['reward']==1 or r['id'] in mixed}
    notes=json.loads((run/'math-review.json').read_text());note_map={}
    for n in notes:
        key=(n['raw_file_sha256'],n['sample']);assert key not in note_map
        raw=json.loads(Path(n['raw_file']).read_text())[n['sample']]
        assert sha(n['raw_file'])==n['raw_file_sha256']
        assert __import__('hashlib').sha256(raw['raw_text'].encode()).hexdigest()==n['raw_text_sha256']
        assert len(raw['raw_text'])==n['read_characters']
        note_map[key]=n
    assert required<=note_map.keys(),('missing required full review',required-note_map.keys())
    selection=json.loads((run/'selection.json').read_text());eligible=sorted((g for g in s if g['mixed']),key=lambda g:(g['total_tokens'],g['id']))
    assert selection['selections'][0]['group']['id']==eligible[0]['id']
    if len(selection['selections'])==2:assert selection['selections'][1]['group']['id']==eligible[-1]['id']
    for chosen in selection['selections']:
        assert sha(chosen['rows'])==chosen['rows_sha256']
    stage_records=[]
    for d in ('screen16384','screen32768'):
        if not (run/d).exists():continue
        receipt=json.loads((run/d/'receipt.json').read_text());raw=[]
        for p in (run/d).glob('*.json'):
            if p.name!='receipt.json':raw+=json.loads(p.read_text())
        stage_records.append(dict(stage=d,answers=len(raw),tokens=sum(len(r['completion_ids']) for r in raw),generation_seconds=sum(r['generation_seconds_group'] for r in raw[::4]),loading_seconds=receipt['loading_seconds'],process_seconds=receipt['elapsed_seconds']))
    strata={}
    for stratum in ('continuous','simple'):
        ss=[g for g in s if next(r for r in rows if r['id']==g['id'])['stratum']==stratum];rr=[r for r in rows if r['stratum']==stratum]
        positives=[r for r in rr if r['reward']==1]
        strata[stratum]=dict(problems=len(ss),answers=len(rr),natural=sum(r['finish_reason']=='stop' for r in rr),parsed=sum(r['status']=='parsed' for r in rr),numeric_correct=len(positives),mixed=sum(g['mixed'] is True for g in ss),eligible=sum(g['eligible'] for g in ss),geometry_valid_positive=sum(note_map[(r['raw_file_sha256'],r['sample'])]['geometry_valid'] is True for r in positives),geometry_and_final_arithmetic_valid_positive=sum(note_map[(r['raw_file_sha256'],r['sample'])]['geometry_valid'] is True and note_map[(r['raw_file_sha256'],r['sample'])]['arithmetic_consistent'] is True for r in positives))
    quality=[]
    for g in s:
        if not g['mixed']:continue
        rr=[r for r in rows if r['id']==g['id']];nn=[note_map[(r['raw_file_sha256'],r['sample'])] for r in rr]
        quality.append(dict(id=g['id'],rewards=g['rewards'],geometry_valid=[n['geometry_valid'] for n in nn],final_arithmetic_consistent=[n['arithmetic_consistent'] for n in nn],geometry_valid_positive=sum(r['reward']==1 and n['geometry_valid'] for r,n in zip(rr,nn)),geometry_invalid_negative=sum(r['reward']==0 and not n['geometry_valid'] for r,n in zip(rr,nn)),geometry_valid_negative=sum(r['reward']==0 and n['geometry_valid'] for r,n in zip(rr,nn))))
    lengths=[len(r['completion_ids']) for r in rows];elapsed=sum(g['seconds'] for g in s);tokens=sum(lengths)
    write(run/'mechanical-audit.json',dict(status='pass',unix=time.time(),scope='binding/completeness/metadata/selection; not an independent mathematics grade',final_answers=48,final_problems=12,distinct_configurations=len({r['source_id'] for r in rows}),final_tokens=tokens,length_mean=statistics.mean(lengths),length_median=statistics.median(lengths),length_max=max(lengths),final_generation_seconds=elapsed,tokens_per_generation_second=tokens/elapsed,stages=stage_records,strata=strata,mixed_quality=quality,required_full_reviews=len(required),reviewed_characters=sum(note_map[k]['read_characters'] for k in required),source_hashes={str(run/p):sha(run/p) for p in ['jobs.json','keys.researcher-only.json','screen-scores.json','signal-summary.json','math-review.json','selection.json']}))
    print(json.dumps(dict(status='pass',strata=strata,mixed_quality=quality,stages=stage_records),indent=2))
if __name__=='__main__':main()
