"""Freeze existing endpoints, without running any solver or changing sources."""
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime, timezone
import gzip, hashlib, json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
G = ROOT / 'jssa/strategy/astra-consult-17/G'
EXPECTED = '67124e29d631062bbe046961d8cde84b1f6d100ce2f2c7d3ed9bc790e07f70e0'

def stamp():
    return datetime.now(timezone.utc).isoformat()

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    assert sha((HERE/'preregistration.md').read_bytes()) == EXPECTED
    assert not (HERE/'input-manifest.json').exists(), 'Inputs already frozen'
    manifest = {'started_utc':stamp(), 'preregistration_sha256':EXPECTED, 'files':[], 'warnings':[]}
    def read(p, lines=False):
        st = p.stat(); data = p.read_bytes()
        used = data
        if lines and data and not data.endswith(b'\n'):
            used = data[:data.rfind(b'\n')+1]
        manifest['files'].append({'path':str(p.relative_to(ROOT)), 'bytes_read':len(data),
            'bytes_used':len(used), 'sha256':sha(used), 'mtime_ns':st.st_mtime_ns,
            'read_utc':stamp(), 'trailing_bytes_excluded':len(data)-len(used)})
        if lines:
            out=[]
            for i,line in enumerate(used.splitlines()):
                if not line.strip():continue
                try:out.append(json.loads(line))
                except Exception as e:manifest['warnings'].append({'file':str(p),'line':i+1,'error':repr(e)})
            return out
        return json.loads(used)
    cases={r['id']:r for r in read(ROOT/'benchmarks/cases.jsonl', True)}
    packs={}
    excluded=[]
    for p in sorted((ROOT/'jssa/difficulty/minima/raw-323').glob('*.json')):
        raw=read(p)
        if not raw.get('n_vars',0):
            excluded.append({'id':p.stem,'reason':'no_variables','status':raw.get('status')}); continue
        packs[p.stem]={'id':p.stem,'case':cases[p.stem],'box':raw['box'],'records':[], 'G_diagnostics':{}}
    def joint(native):
        if 'wall_reject_joint' in native:return native['wall_reject_joint'],'full_native_joint'
        trials=native.get('trials',native.get('tail',[]))
        count=0
        for t in trials:
            b=t.get('base',{})
            try:
                count+= bool(t['decision']=='rejected' and b.get('F') and not t['F']
                    and t['hard']**2>b['hard']**2 and t['eq_ss']+t['guard']**2<b['eq_ss']+b['guard']**2)
            except (KeyError,TypeError):pass
        return count, 'saved_trials_joint' if 'trials' in native else 'tail_joint_lower_bound'
    def add(cid, source, arm, r, start=None, k=None, file=None):
        if cid not in packs:
            manifest['warnings'].append({'source':source,'id':cid,'reason':'outside_primary_292'});return
        if not isinstance(r,dict) or 'cls' not in r:return
        rec={key:r[key] for key in ('cls','x','start','res','ans','sec','nfev','err','hard','tags') if key in r}
        rec.update(source=source,arm=arm,k=r.get('k',k),source_file=file)
        if start is not None:rec['start']=start
        if 'native' in r:
            rec['native_joint'],rec['native_joint_scope']=joint(r['native'])
        packs[cid]['records'].append(rec)
    for source,rel in [('raw0','minima/raw-323'),('raw1','minima/raw-323-seed1'),
        ('seed2_plain','start-feasibility-1023/seed2-plain'),('seed2_feasible','start-feasibility-1023/seed2-feasible')]:
        for p in sorted((ROOT/'jssa/difficulty'/rel).glob('*.json')):
            if p.stem not in packs:continue
            raw=read(p)
            if raw.get('dsl_override'):
                manifest['warnings'].append({'file':str(p),'reason':'DSL override excluded'});continue
            for r in raw.get('records',[]):add(p.stem,source,'B',r,file=str(p.relative_to(ROOT)))
    for r in read(G/'endpoint-diagnostics.jsonl',True):
        if r['id'] in packs:packs[r['id']]['G_diagnostics'][str(r['k'])]=r
    for obj in read(G/'intervention.json'):
        for r in obj['records']:
            for arm,key in [('B','baseline'),('N','no_hard')]:
                add(obj['id'],'G_intervention',arm,r[key],r.get('start'),r['k'],'G/intervention.json')
    for p in sorted((G/'mechanism-data').glob('*.json')):
        obj=read(p)
        if 'id' not in obj:continue
        for r in obj['records']:
            for arm in ('B','N','S','J','C','CS'):
                if arm in r:add(obj['id'],'G_mechanism',arm,r[arm],r.get('start'),r['k'],str(p.relative_to(ROOT)))
    for r in read(G/'aime-traces.json'):
        for arm,key in [('B','baseline'),('N','no_hard')]:
            add('AIME-2010-II-14','G_aime_trace',arm,r[key],r.get('start'),r['k'],'G/aime-traces.json')
    for r in read(G/'native-aime-traces.json')['records']:
        for arm in ('B','N','S','J','C','CS'):
            add('AIME-2010-II-14','G_native_trace',arm,r[arm],r.get('start'),r['k'],'G/native-aime-traces.json')
    for p in sorted((ROOT/'jssa/difficulty/wall-292/records').glob('*.jsonl')):
        for r in read(p,True):
            for arm in ('B','N','G2','S'):
                if arm in r:add(p.stem,'Q1',arm,r[arm],r.get('start'),r['k'],str(p.relative_to(ROOT)))
    import csv,io
    tables={}
    for key,rel in [('human','ghost-1023/human_feat.csv'),('basins','minima/basins-323.csv'),('feasibility','start-feasibility-1023/per-problem.csv')]:
        p=ROOT/'jssa/difficulty'/rel
        data=p.read_bytes()
        manifest['files'].append({'path':str(p.relative_to(ROOT)),'bytes_used':len(data),'sha256':sha(data),'read_utc':stamp()})
        rr=list(csv.DictReader(io.StringIO(data.decode())))
        idcol='case_id' if key=='human' else 'id'
        if rr and idcol not in rr[0]:idcol=next(k for k in ['case_id','id','problem'] if k in rr[0])
        tables[key]={r[idcol]:r for r in rr}
    out=HERE/'inputs';out.mkdir(exist_ok=True)
    counts=Counter();duplicates=Counter()
    for index,(cid,obj) in enumerate(sorted(packs.items())):
        obj['index']=index
        obj.update({key:tab.get(cid,{}) for key,tab in tables.items()})
        seen=set(); kept=[]
        for r in obj['records']:
            # No-coordinate attempts are distinguished by k; never collapse all missing results.
            key=(r['source'],r['arm'],json.dumps(r.get('start')),json.dumps(r.get('x')),
                 r['k'] if 'x' not in r else None)
            if key in seen:
                duplicates[r['source']+'/'+r['arm']]+=1;continue
            seen.add(key);kept.append(r);counts[r['source']+'/'+r['arm']]+=1
        obj['records']=kept
        data=json.dumps(obj,ensure_ascii=False,separators=(',',':')).encode()
        p=out/(cid+'.json.gz');p.write_bytes(gzip.compress(data,mtime=0))
    manifest.update(finished_utc=stamp(),problems=len(packs),excluded=excluded,
        records=dict(counts),within_source_exact_duplicates=dict(duplicates),
        snapshots={p.name:sha(p.read_bytes()) for p in sorted(out.glob('*.gz'))})
    (HERE/'input-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:manifest[k] for k in ('problems','records','within_source_exact_duplicates','warnings')},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
