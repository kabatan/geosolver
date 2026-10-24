"""Overlay only the authorized slots; use unchanged S8 graders on all 1113."""
import csv
import fcntl
from pathlib import Path
import shutil
from measurement_common import HERE, load, save, sha, utc


def replacement_receipt(job, original, fresh=None):
    if fresh is not None:
        assert all(fresh[k]==v for k,v in job.items()),'replacement job changed'
        return fresh
    # An absent rerun is incomplete; never fall back to the invalid old result.
    return dict(original,state='interrupted_driver_fsize',exit_code=None,
                original_exit_code=original['exit_code'],files={},
                wall_seconds=None,total_wall_through_cleanup_seconds=None,
                resource_violations=[],driver_invalidation='FSIZE infrastructure interruption; excluded')


def merge_and_grade(out,freeze):
    from measurement_grade import aggregate
    import report_superpc
    original=HERE.parent/'run-superpc'
    old=load(original/'measurement-freeze.json')
    assert sha(original/'measurement-freeze.json')==freeze['original_freeze_sha256']
    assert old['source_hash']==freeze['source_hash']
    assert old['references_sha256']==freeze['references_sha256']==sha(HERE/'references.json')
    slots={j['queue_index']:j for j in freeze['jobs']}
    assert len(slots)==320 and len(old['jobs'])==1113
    lock=(out/'campaign.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    merged=out/'merged';merged.mkdir(exist_ok=True)
    (merged/'receipts').mkdir(exist_ok=True)
    mapping=[]
    for j in old['jobs']:
        q=j['queue_index'];name=f'{q:04d}'
        oldend=load(original/'receipts'/f'{name}.end.json')
        origin=original
        if q in slots:
            assert slots[q]==j
            endpath=out/'receipts'/f'{name}.end.json'
            fresh=load(endpath) if endpath.exists() else None
            receipt=replacement_receipt(j,oldend,fresh)
            origin=out if fresh is not None else original
            save(merged/'receipts'/f'{name}.end.json',receipt)
        else:
            shutil.copyfile(original/'receipts'/f'{name}.end.json',merged/'receipts'/f'{name}.end.json')
        shutil.copyfile(origin/'receipts'/f'{name}.start.json',merged/'receipts'/f'{name}.start.json')
        mapping.append(dict(queue_index=q,replaced=q in slots,source=str(origin),
                            old_end_sha256=sha(original/'receipts'/f'{name}.end.json'),
                            merged_end_sha256=sha(merged/'receipts'/f'{name}.end.json')))
    combined=dict(old,raw_root='see individual receipts: original + rerun',
                  rerun_freeze_sha256=sha(out/'measurement-freeze.json'))
    save(merged/'measurement-freeze.json',combined)
    save(merged/'replacement-map.json',dict(utc=utc(),originals_preserved=True,slots=mapping))
    analysis=load(HERE/'analysis-freeze-rerun.json')
    assert analysis['original_analysis_freeze_sha256']==sha(original/'analysis-freeze.json')
    assert analysis['supervisor_sha256']==sha(HERE/'supervise_superpc.py')
    assert analysis['grade_sha256']==sha(HERE/'measurement_grade.py')
    assert analysis['reporting_sha256']==sha(HERE/'report_superpc.py')
    save(merged/'analysis-freeze.json',analysis)
    # aggregate()/grade_one()/exact comparisons and load-policy reporter unchanged.
    aggregate(merged,combined)
    report_superpc.OUT=merged
    report_superpc.main()
    # report_superpc uses hard-coded original scope text; this provenance note
    # makes the overlay explicit without changing its statistical policy/code.
    with (merged/'answer.md').open('a') as stream:
        stream.write('\n320 original nonzero_exit slots are infrastructure interruptions; '
                     'only their authorized rerun receipts replace them. '
                     'Original campaign is preserved. See replacement-map.json.\n')
    save(merged/'artifact-hashes.json',dict(created_utc=utc(),files_sha256={
        str(p.relative_to(merged)):sha(p) for p in sorted(merged.rglob('*'))
        if p.is_file() and p.name not in ('artifact-hashes.json','campaign.lock')}))
    for p in merged.rglob('*'):
        if p.is_file():assert p.stat().st_size<3_000_000,p
