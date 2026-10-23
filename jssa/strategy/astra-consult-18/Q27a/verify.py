"""Independent arithmetic/input-hash audit; no solver work and no outside writes."""
from pathlib import Path
from collections import Counter
from statistics import median
import csv, hashlib, json, math

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]

def rows(path): return list(csv.DictReader(path.open()))
def main():
    mismatches=[]; hashes={}
    for name in ['input-manifest-explore.json','input-manifest-confirm.json','input-manifest-supplement.json']:
        for r in json.loads((OUT/name).read_text()):
            if r['path'] in hashes: assert hashes[r['path']]==r['sha256']
            hashes[r['path']]=r['sha256']
    for path,digest in hashes.items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=digest: mismatches.append(path)
    assert not mismatches,mismatches
    lock=json.loads((OUT/'registration-lock.json').read_text())
    for path,digest in lock['hashes'].items(): assert hashlib.sha256((OUT/path).read_bytes()).hexdigest()==digest
    started=json.loads((OUT/'confirmation-start.json').read_text())
    assert hashlib.sha256((OUT/'confirm.py').read_bytes()).hexdigest()==started['code_sha256']
    sel=json.loads((OUT/'selection.json').read_text()); saved={r['id']:r for r in rows(OUT/'confirmation-per-problem.csv')}
    sign=Counter(); medians={}; ratios={}; strict=Counter()
    for x in sel:
        j=json.loads((ROOT/'jssa/difficulty/minima/raw-323-seed1'/f"{x['id']}.json").read_text()); rr=j['records']; m=x['threshold']
        fast=[r for r in rr if r['nfev']<=m]; slow=[r for r in rr if r['nfev']>m]
        delta=sum(r['cls']=='hit' for r in slow)/len(slow)-sum(r['cls']=='hit' for r in fast)/len(fast)
        assert math.isclose(delta,float(saved[x['id']]['delta1']),abs_tol=1e-12)
        b=x['cutoff'] if x['cutoff'] is not None else math.inf
        base=sum(r['nfev'] for r in rr)/sum(r['cls']=='hit' for r in rr)
        count=sum(r['cls']=='hit' and r['nfev']<=b for r in rr)
        c=sum(min(r['nfev'],b) for r in rr)/count if count else math.inf
        assert math.isclose(c/base,float(saved[x['id']]['ratio1']),rel_tol=1e-12)
        g=x['group']; medians.setdefault(g,[]).append(delta); ratios.setdefault(g,[]).append(c/base)
        valid=min(len(fast),len(slow))>=20
        if valid and (g=='L' and delta>=.1 or g=='E' and delta<=-.1): sign[g]+=1
        if valid and (g=='L' and delta>=.2 or g=='E' and delta<=-.2): strict[g]+=1
    assert sign['L']>=8 and median(medians['L'])>=.25
    assert sign['E']>=62
    assert median(ratios['E'])<=.85 and median(ratios['L'])>=.9
    extra=[]
    for seed,dirname in [(0,'raw-323'),(1,'raw-323-seed1')]:
        n=0; extreme={}; incomplete=[]; hits=0
        for p in (ROOT/'jssa/difficulty/minima'/dirname).glob('*.json'):
            j=json.loads(p.read_text()); rr=j.get('records',[]); n+=len(rr); hits+=sum(r['cls']=='hit' for r in rr)
            nn=sum(r['nfev']>1000 for r in rr)
            if nn: extreme[j['case_id']]=nn
            if rr and len(rr)<j['starts_requested']: incomplete.append(j['elapsed'])
        extra.append(dict(seed=seed,records=n,hits=hits,extreme_nfev_problem_count=len(extreme),extreme_nfev_problems=extreme,incomplete=len(incomplete),incomplete_elapsed_range=[min(incomplete),max(incomplete)]))
    basins={r['id']:r for r in rows(ROOT/'jssa/difficulty/minima/basins-323.csv')}
    local=rows(OUT/'local-seed0.csv')
    for r in local:
        assert int(r['n'])==int(basins[r['id']]['n_starts'])
        assert math.isclose(float(r['p']),float(basins[r['id']]['p']),abs_tol=1e-12)
    files=[p for p in OUT.iterdir() if p.is_file()]
    result=dict(passed=True,unique_input_hashes_checked=len(hashes),preregistration_unchanged=True,confirmation_code_unchanged=True,independent_cases_checked=len(sel),group_counts=dict(Counter(x['group'] for x in sel)),replication_at_registered_0p1=dict(sign),descriptive_replication_at_0p2=dict(strict),P1=True,P2=True,P3=True,basins_csv_agreement=len(local),raw_diagnostics=extra,largest_output_bytes=max(p.stat().st_size for p in files),total_output_bytes=sum(p.stat().st_size for p in files))
    (OUT/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
