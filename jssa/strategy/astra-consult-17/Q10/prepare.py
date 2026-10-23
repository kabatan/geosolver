"""Freeze local sources and answer-free 16-case inputs. No mathematical experiment."""
from pathlib import Path
import csv, json, hashlib, subprocess, shutil, datetime, sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
def sha(raw): return hashlib.sha256(raw).hexdigest()
def save(p,obj): p.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def main():
    for d in ['vendor','inputs','audit_source','tmp','runs']:(HERE/d).mkdir(exist_ok=True)
    provenance=[]
    sources=[('claude/project-thread-fos2rk','benchmarks/exact_comparison/algebraize.py','vendor/algebraize.py'),
             ('claude/project-thread-fos2rk','benchmarks/exact_comparison/run_exact.py','vendor/run_exact.py'),
             ('claude/project-thread-ulho54','jssa/theory/posdim-identities/certify.py','audit_source/certify.py'),
             ('claude/project-thread-ulho54','jssa/theory/posdim-identities/README.md','audit_source/prior-README.md'),
             ('claude/project-thread-ulho54','jssa/theory/posdim-identities/out/batch-summary.csv','audit_source/prior-batch-summary.csv')]
    for branch,path,dest in sources:
        ref='origin/'+branch
        raw=subprocess.check_output(['git','show',ref+':'+path],cwd=ROOT)
        assert len(raw)<16*1024**2
        (HERE/dest).write_bytes(raw)
        provenance.append(dict(source=ref+':'+path,commit=subprocess.check_output(['git','rev-parse',ref],cwd=ROOT,text=True).strip(),sha256=sha(raw),destination=dest))
    for name in ['certificate.py','verify_certificate.py','experiment.py']:
        p=HERE.parent/'L'/name;raw=p.read_bytes()
        dest='vendor/l_'+name
        (HERE/dest).write_bytes(raw)
        provenance.append(dict(source=str(p.relative_to(ROOT)),sha256=sha(raw),destination=dest))
    ids=[r['id'] for r in csv.DictReader((HERE.parent/'H/classification.csv').open()) if r['classification']=='genuine_shape_motion']
    assert len(ids)==16
    cases={c['id']:c for c in map(json.loads,(ROOT/'benchmarks/cases.jsonl').read_text().splitlines())}
    manifest=[]
    for cid in ids:
        raw=(json.dumps({'id':cid,'dsl':cases[cid]['dsl']},sort_keys=True,ensure_ascii=False)+'\n').encode()
        (HERE/'inputs'/f'{cid}.json').write_bytes(raw)
        manifest.append(dict(id=cid,sha256=sha(raw)))
    save(HERE/'input-manifest.json',manifest)
    save(HERE/'provenance.json',provenance)
    save(HERE/'environment.json',dict(python=sys.version,binaries={n:shutil.which(n) for n in ['Singular','singular','msolve']},src_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()))
    save(HERE/'registration-lock.json',dict(timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),preregistration_sha256=sha((HERE/'preregistration.md').read_bytes()),ids=ids,seed=10423,budget_seconds=120))
    print('Prepared',len(ids),'inputs and source snapshots; no search or elimination.')
if __name__=='__main__':main()
