"""Verify fixed inputs, every planned slot, starts, receipts, and reported totals."""
from common import *
from collections import Counter
import sqlite3
import numpy as np


def main():
    verify_source()
    lock=read(PLAN/'prediction.lock.json')
    for name,meta in lock['files'].items():
        assert (PLAN/name).read_bytes()==(HERE.parent/name).read_bytes(), name
        assert sha((PLAN/name).read_bytes())==meta['sha256'], name
    receipt=read(HERE/'receipt.json')
    assert receipt==read(EXTERNAL/'receipt.json')
    assert receipt['authorization']['prediction_and_common_contract_commit']==COMMIT
    assert receipt['authorization']['commit_push_confirmed_utc']=='2026-10-23T18:02:20Z'
    assert receipt['prediction_lock_sha256']==sha((PLAN/'prediction.lock.json').read_bytes())
    assert read(HERE/'instrumentation-checks.json')['passed']
    summary=read(HERE/'summary.json'); selected=read(PLAN/'selected.json')
    db=sqlite3.connect(f'file:{EXTERNAL}/trials.sqlite?mode=ro',uri=True)
    statuses=Counter(); methods=Counter(); primary=Counter(); attempts=0; order_index=0
    max_seconds=0.; unknown_starts=0; maximum_seconds_by_status={}
    for case in selected:
        cid=case['canonical_id']
        builds={v:json.loads(data) for v,data in db.execute('SELECT variant,data FROM builds WHERE case_id=?',(cid,))}
        rows=db.execute('SELECT idx,seed,k,variant,position,status,data FROM trials WHERE case_id=? ORDER BY idx',(cid,)).fetchall()
        assert len(rows)==3600
        original=builds.get('original',{})
        arrays={s:starts(cid,s,original['original_bounds']) for s in SEEDS} if original.get('status')=='built' else {}
        last_started=''
        for row,expected in zip(rows,schedule(cid),strict=True):
            idx,seed,k,variant,position,status,payload=row
            assert idx==order_index; order_index+=1
            assert (seed,k,variant,position)==expected
            assert status not in ('unstarted','started','local_done')
            statuses[status]+=1; data=json.loads(payload)
            if 'started_at_utc' in data:
                assert data['started_at_utc']>=receipt['recorded_at_utc']
                assert data['started_at_utc']>=last_started
                last_started=data['started_at_utc']
                x0=arrays[seed][k,builds[variant]['positions']]
                assert np.array_equal(x0,np.asarray(data['x0'])), (cid,seed,k,variant,'start')
                assert sha(x0.astype('<f8').tobytes())==data['start_sha256']
                assert data['source_hash']==SOURCE_HASH
                attempts+=1; methods[data['method']]+=1
                unknown_starts+=not bool(data.get('attempted'))
                max_seconds=max(max_seconds,data.get('local_seconds',0))
                maximum_seconds_by_status[status]=max(maximum_seconds_by_status.get(status,0.),data.get('local_seconds',0))
            if data.get('hit'): primary[seed]+=1
    assert order_index==144000
    assert dict(statuses)==summary['statuses']
    assert sum(primary.values())==sum(int(r['hits']) for r in __import__('csv').DictReader((HERE/'per-condition.csv').open()))
    assert unknown_starts==0, 'Some started slots have uncertain call entry; disclose instead of claiming an exact call count'
    assert attempts==summary['actual_local_calls'] and dict(methods)==summary['local_methods']
    batches=[read(p) for p in sorted((EXTERNAL/'batches').glob('*.json'))]
    assert all(b['seconds']<200 and len(b['cpus'])<=2 for b in batches)
    completed_by_batches=sum(sum(b['counts'].values()) for b in batches)
    assert completed_by_batches==144000, (completed_by_batches,'batch receipts do not cover all slots')
    assert all(b['source_hash']==SOURCE_HASH for b in batches)
    assert not [p for p in HERE.rglob('*') if p.is_file() and p.stat().st_size>5000000]
    result={'passed':True,'at_utc':utc(),'planned_slots':144000,'unique_slots':144000,
            'starts_recomputed':attempts,'extra_seeds':0,'replacement_slots':0,'retries':0,
            'stage1_files_unchanged':len(lock['files']),'source_hash':SOURCE_HASH,
            'statuses':dict(statuses),'method_counts':dict(methods),'primary_hits_by_seed':dict(primary),
            'batches':len(batches),'maximum_batch_seconds':max(b['seconds'] for b in batches),
            'maximum_observed_local_call_seconds':max_seconds,
            'maximum_local_seconds_by_status':maximum_seconds_by_status,'repository_files_over_5MB':0,
            'external_raw_directory':str(EXTERNAL),'unknown_call_entry_slots':unknown_starts}
    write(HERE/'completion-audit.json',result)
    print(json.dumps(result))


if __name__=='__main__':
    main()
