"""Consistency and input-integrity audit of the Q27c measurements."""
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from mpmath import mp

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    manifest = json.loads((OUT/'input-manifest.json').read_text())
    changed = [p for p,h in manifest['inputs'].items() if sha(ROOT/p)!=h]
    lock = json.loads((OUT/'replay-lock.json').read_text())
    assert sha(OUT/'preregistration.md')==lock['preregistration_sha256']
    assert sha(OUT/'replay.py')==lock['script_sha256']
    replay=list(csv.DictReader((OUT/'replay.csv').open()))
    assert len(replay)==786
    assert len({(r['id'],r['answer_index'],r['declared_precision'],r['seed']) for r in replay})==786
    assert not [r for r in replay if r['status'] not in ['correct','wrong','none']]
    values={(r['id'],r['answer_index']):r for r in json.loads((ROOT/'jssa/strategy/astra-consult-18/q21b-number-theory/values.json').read_text())}
    errors=[]
    with mp.workdps(180):
        for r in json.loads((OUT/'replay-inputs.json').read_text()):
            a=mp.mpf(values[r['id'],r['answer_index']]['value_180'])
            errors.append(float(-mp.log10(abs(mp.mpf(r['value'])-a)/max(1,abs(a)))))
    assert min(errors)>129
    old={r['id']:json.loads(r['got']) for r in csv.DictReader((ROOT/'jssa/strategy/astra-consult-18/q21b-number-theory/precision.csv').open()) if r['precision']=='80' and r['status']=='wrong'}
    wrong=[r for r in replay if r['seed']=='270023' and r['declared_precision']=='80' and r['status']=='wrong']
    same_wrong=all(json.loads(r['got'])==old[r['id']] for r in wrong)
    original=[r for r in csv.DictReader((OUT/'refinement-observations.csv').open()) if r['variant']=='O']
    counts={key:dict(Counter(Counter(r['id'] for r in original if r[key]=='True').values()))
            for key in ['plateau','rescued_plateau','zero_rebound']}
    result=dict(input_files=len(manifest['inputs']), changed_inputs=changed,
        preregistration_hash_matches=True, replay_script_hash_matches=True,
        all_registered_calls_unique=True, calls=786,
        actual_digits_relative_to_source180_min=min(errors),
        actual_digits_relative_to_source180_max=max(errors),
        all_four_p80_wrong_polynomials_match_old=same_wrong,
        same_seed_start_replication_counts=counts,
        note='Digits compare to stored reference, not an independent exact-arithmetic certificate.')
    assert not changed and same_wrong
    (OUT/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
