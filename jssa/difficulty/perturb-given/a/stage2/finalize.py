"""Bind completed Q40a results to external raw files without copying large logs."""
from common import *
import fcntl
import sqlite3


def file_record(path, root):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            digest.update(block)
    return {'path':str(path.relative_to(root)),'bytes':path.stat().st_size,'sha256':digest.hexdigest()}


def main():
    verify_source()
    assert read(HERE/'completion-audit.json')['passed']
    assert read(HERE/'summary.json')['complete']
    assert (HERE.parent/'answer.md').is_file()
    with (EXTERNAL/'runner.lock').open('a') as guard:
        fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
        db=sqlite3.connect(EXTERNAL/'trials.sqlite')
        assert db.execute("SELECT count(*) FROM trials WHERE status IN ('unstarted','started','local_done')").fetchone()[0]==0
        integrity=[row[0] for row in db.execute('PRAGMA integrity_check')]
        assert integrity==['ok'],integrity
        checkpoint=db.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()
        assert checkpoint[0]==0,checkpoint
        db.close()
        files=[file_record(path,EXTERNAL) for path in sorted(EXTERNAL.rglob('*')) if path.is_file()
               and path.name not in ('runner.lock','trials.sqlite-wal','trials.sqlite-shm')]
        write(HERE/'raw-index.json',{
            'at_utc':utc(),'external_root':str(EXTERNAL),'sqlite_integrity_check':integrity,
            'source_hash':SOURCE_HASH,'prediction_lock_sha256':sha((PLAN/'prediction.lock.json').read_bytes()),
            'file_count':len(files),'total_bytes':sum(f['bytes'] for f in files),'files':files,
            'storage_note':'Raw files are external temporary files, not a durable or remote archive.'})
    outputs=[p for p in sorted(HERE.rglob('*')) if p.is_file() and p.name!='artifact-manifest.json']
    outputs.append(HERE.parent/'answer.md')
    assert all(p.stat().st_size<=5000000 for p in outputs)
    write(HERE/'artifact-manifest.json',{
        'at_utc':utc(),'root':str(HERE.parent),'source_hash':SOURCE_HASH,
        'files':[file_record(p,HERE.parent) for p in outputs],
        'external_files_index':'stage2/raw-index.json'})
    print(json.dumps({'sqlite_integrity_check':integrity,'external_files':len(files),
                      'external_bytes':sum(f['bytes'] for f in files),'repository_files':len(outputs),
                      'repository_files_over_5MB':0,'at_utc':utc()}))


if __name__=='__main__':
    main()
