"""Fixed scoring, paired question-level summaries; no training or reward changes."""
import argparse, importlib.util, json, math, random, re, statistics, sys
from collections import Counter,defaultdict
from pathlib import Path
from formalize import HERE,ROOT,RUN,OLD,sha,write
OLD_DOC=ROOT/'docs/research/geometryzero-stage1-2026-09-30'
sys.path.insert(0,str(OLD_DOC))
spec=importlib.util.spec_from_file_location('fixed_signals',OLD_DOC/'signals.py')
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)

def collect(partial):
    from transformers import AutoTokenizer
    tok=AutoTokenizer.from_pretrained(json.loads((OLD_DOC/'model.json').read_text())['snapshot'],local_files_only=True)
    labels=json.loads((OLD/'labels.json').read_text());scored=[];provenance=[]
    for arm in ('text','logic'):
        for rep in (1,2):
            for pid,label in labels.items():
                for group in ('without','with','main'):
                    p=(OLD/'screen1024'/(pid+'-'+group+'.json')) if (arm,rep)==('text',1) else RUN/'screen1024-v2'/f'{pid}-{arm}-s{rep}-{group}.json'
                    if not p.exists():
                        if partial:continue
                        raise FileNotFoundError(p)
                    rows=json.loads(p.read_text());assert len(rows)==8
                    for row in rows:
                        assert row['problem_id']==pid and row['group']==group
                        a=s.score(row,label['answer_exact'],tok)
                        # Secondary parser sensitivity: repeated equivalent committed answers.
                        tags=re.findall(r'<answer>(.*?)</answer>',row['raw_text'],re.S)
                        vals=[]
                        for t in tags:
                            try:vals.append(float(s.parse_numeric(t.strip())))
                            except (ValueError,TypeError,OverflowError):vals=[];break
                        want=float(s.parse_numeric(label['answer_exact']))
                        repeated_match=bool(len(tags)>1 and len(vals)==len(tags) and max(vals)-min(vals)<1e-8 and abs(vals[-1]-want)<=.02*max(abs(want),1e-30))
                        aux_bodies=re.findall(r'<auxiliary>(.*?)</auxiliary>',row['raw_text'],re.S)
                        a.update(id=f'{pid}-{arm}-s{rep}-{group}-{row["sample"]}',problem_id=pid,arm=arm,replicate=rep,group=group,sample=row['sample'],tokens=len(row['completion_ids']),source=str(p.resolve()),source_sha256=sha(p),question_integer=bool(s.parse_numeric(label['answer_exact']).is_Integer),repeated_equivalent_answer_match=repeated_match,aux_contains_predicate=bool(any(re.search(r'(?:Line|PointLiesOnLine|Parallel|Perpendicular|Circle|IntersectAt)\(',t) for t in aux_bodies)))
                        scored.append(a)
                    provenance.append(dict(path=str(p.resolve()),sha256=sha(p),arm=arm,replicate=rep,group=group,problem_id=pid))
    return scored,provenance

def describe(scored):
    by=defaultdict(list)
    for r in scored:by[(r['arm'],r['replicate'],r['problem_id'],r['group'])].append(r)
    blocks=[]
    for arm,rep,pid,g in by:
        if g!='main' or not all((arm,rep,pid,k) in by for k in ('with','without')):continue
        groups={k:sorted(by[(arm,rep,pid,k)],key=lambda x:x['sample']) for k in ('without','with','main')}
        w=[r['relaxed'] for r in groups['with']];b=[r['relaxed'] for r in groups['without']]
        bounds=s.mask_bounds(w,b);m=s.mask(w,b) if all(x is not None for x in w+b) else bounds['certain_mask']
        xs=groups['main'];ns=[r['relaxed'] for r in xs];natural=all(x is not None for x in ns)
        full=None
        if natural and m is not None:
            full=[r['relaxed']+r['format']+m*r['aux']+r['length'] for r in xs]
            for r,a,v in zip(xs,s.normalize(full),full,strict=True):r.update(advantage=a,total_reward=v)
        blocks.append(dict(arm=arm,replicate=rep,problem_id=pid,mask=m,mask_bounds=bounds,numeric_mixed=natural and 0<sum(ns)<8,main_natural=natural,main_correct=sum(x or 0 for x in ns),full_mixed=full is not None and statistics.stdev(full)>0,all_numeric_zero=natural and sum(ns)==0,main_tokens=sum(r['tokens'] for r in xs)))
    arms={}
    for arm in ('text','logic'):
        bb=[b for b in blocks if b['arm']==arm];arms[arm]={}
        for group in ('without','with','main'):
            rr=[r for r in scored if r['arm']==arm and r['group']==group];nn=[r for r in rr if not r['censored']]
            integer=[r for r in nn if r['question_integer']];noninteger=[r for r in nn if not r['question_integer']]
            arms[arm][group]=dict(answers=len(rr),natural=len(nn),censored=len(rr)-len(nn),correct=sum(r['relaxed'] for r in nn),strict_correct=sum(r['strict'] for r in nn),exact_correct=sum(r['exact'] for r in nn),accuracy=sum(r['relaxed'] for r in nn)/len(nn) if nn else None,correct_fraction_bounds=[sum(r['relaxed'] for r in nn)/len(rr),(sum(r['relaxed'] for r in nn)+len(rr)-len(nn))/len(rr)] if rr else None,format_count=sum(r['format']>0 for r in rr),aux_count=sum(r['aux']>0 for r in rr),unparsed=sum(r['parsed'] is None for r in nn),tokens=sum(r['tokens'] for r in rr),mean_tokens=statistics.mean(r['tokens'] for r in rr) if rr else None,integer=dict(natural=len(integer),correct=sum(r['relaxed'] for r in integer)),noninteger=dict(natural=len(noninteger),correct=sum(r['relaxed'] for r in noninteger)),repeated_equivalent_matches=sum(r['repeated_equivalent_answer_match'] for r in nn))
        pp=[r for r in scored if r['arm']==arm and r['group']=='main' and r.get('advantage',0)>1e-8]
        arms[arm]['signals']=dict(question_seed_groups=len(bb),numeric_mixed=sum(b['numeric_mixed'] for b in bb),full_mixed=sum(b['full_mixed'] for b in bb),all_wrong_full_mixed=sum(b['full_mixed'] and b['all_numeric_zero'] for b in bb),numeric_correct_structures=sorted({r['problem_id'] for r in scored if r['arm']==arm and r['group']=='main' and r['relaxed']==1}),mask_counts={str(k):v for k,v in Counter(b['mask'] for b in bb).items()},positive_correct_count=sum(r['relaxed']==1 for r in pp),positive_incorrect_count=sum(r['relaxed']==0 for r in pp),positive_correct_coefficient=sum(r['advantage'] for r in pp if r['relaxed']==1),positive_incorrect_coefficient=sum(r['advantage'] for r in pp if r['relaxed']==0))
        mixed={(b['replicate'],b['problem_id']) for b in bb if b['numeric_mixed']}
        arms[arm]['signals'].update(negative_correct_count=sum(r['arm']==arm and r['group']=='main' and r['relaxed']==1 and r.get('advantage',0)<-1e-8 for r in scored),mixed_positive_correct_coefficient=sum(r['advantage'] for r in pp if r['relaxed']==1 and (r['replicate'],r['problem_id']) in mixed),mixed_positive_incorrect_coefficient=sum(r['advantage'] for r in pp if r['relaxed']==0 and (r['replicate'],r['problem_id']) in mixed))
        arms[arm]['replicates']={str(rep):dict(main_correct=sum(r['relaxed'] or 0 for r in scored if r['arm']==arm and r['replicate']==rep and r['group']=='main'),main_natural=sum(not r['censored'] for r in scored if r['arm']==arm and r['replicate']==rep and r['group']=='main'),numeric_mixed=sum(b['numeric_mixed'] for b in bb if b['replicate']==rep),all_wrong_full_mixed=sum(b['full_mixed'] and b['all_numeric_zero'] for b in bb if b['replicate']==rep)) for rep in (1,2)}
        arm_rows=[r for r in scored if r['arm']==arm]
        arms[arm]['aux_predicate_counts']={g:sum(r['aux_contains_predicate'] for r in arm_rows if r['group']==g) for g in ('without','with','main')}
        stable=[]
        for pid in dict.fromkeys(b['problem_id'] for b in bb):
            pair=[b for b in bb if b['problem_id']==pid]
            if len(pair)==2 and all(b['mask'] is not None for b in pair):stable.append(pair)
        arms[arm]['mask_stability']=dict(both_certain=len(stable),same_sign=sum(p[0]['mask']==p[1]['mask'] for p in stable),opposite_nonzero_sign=sum(p[0]['mask']*p[1]['mask']==-1 for p in stable),details=[dict(problem_id=p[0]['problem_id'],replicate1=p[0]['mask'],replicate2=p[1]['mask']) for p in stable])
    paired=[]
    for pid in dict.fromkeys(r['problem_id'] for r in scored):
        a={}
        for arm in ('text','logic'):
            rr=[r for r in scored if r['problem_id']==pid and r['arm']==arm and r['group']=='main'];nn=[r for r in rr if not r['censored']]
            a[arm]=dict(correct=sum(r['relaxed'] for r in nn),natural=len(nn),accuracy=sum(r['relaxed'] for r in nn)/len(nn) if nn else None)
        if all(a[k]['natural']>=8 for k in a):paired.append(dict(problem_id=pid,**a,difference=a['logic']['accuracy']-a['text']['accuracy']))
    ci=None
    if len(paired)==24:
        rng=random.Random(2026100101);d=[p['difference'] for p in paired]
        boot=sorted(statistics.mean(rng.choices(d,k=len(d))) for _ in range(20000))
        ci=dict(unit='problem_id; two seeds kept in same cluster',replications=20000,paired_mean_difference=statistics.mean(d),percentile_95=[boot[499],boot[19499]],improved=sum(x>0 for x in d),unchanged=sum(x==0 for x in d),declined=sum(x<0 for x in d),note='Conditional on these 24 fixed selected structures, not population or causal estimate of syntax alone.')
    return dict(arms=arms,blocks=blocks,paired=paired,paired_bootstrap=ci)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--partial',action='store_true');a=ap.parse_args()
    rows,provenance=collect(a.partial);result=describe(rows)
    result.update(status='partial' if a.partial else 'complete',score_source_sha256=sha(OLD_DOC/'signals.py'),comparison_source_sha256=sha(__file__),new_actor_receipt=json.loads((RUN/'screen1024-v2/receipt.json').read_text()))
    prefix='partial-' if a.partial else ''
    write(HERE/(prefix+'summary.json'),result)
    if not a.partial:
        assert len(rows)==2304 and result['new_actor_receipt']['status']=='complete'
        write(RUN/'scores.json',rows);write(HERE/'provenance.json',provenance)
        chosen=[r for r in rows if r['arm']=='logic' and r['group']=='main' and r['relaxed']==1]
        write(HERE/'positive-main.json',chosen)
        sections=[]
        for x in chosen:
            raw=next(r for r in json.loads(Path(x['source']).read_text()) if r['sample']==x['sample'])['raw_text']
            sections.append(f'## {x["id"]}\n\n'+raw+'\n')
        (HERE/'positive-main-fulltext.md').write_text('\n'.join(sections))
    print(json.dumps(dict(status=result['status'],arms=result['arms'],paired_bootstrap=ci if (ci:=result['paired_bootstrap']) else None),ensure_ascii=False))

if __name__=='__main__':main()
