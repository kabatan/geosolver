"""Score final numeric commitments after manual review and integrity checks."""
import hashlib
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'qwen/.runtime/proof_numeric_pilot_20260928'
sys.path.insert(0, str(ROOT))
from qwen.answer_check import parse_numeric


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def score(cid, arm, job, source, audit, expected):
    raw = read(source)
    assert audit['reviewed_final_commitment'] is True
    assert audit['file_sha256'] == sha(source), cid
    expr = audit['parsed_expression']
    value = float(parse_numeric(expr)) if expr is not None else None
    want = float(expected[job]['solver_value'])
    error = abs(value - want) if value is not None else None
    relative = error / abs(want) if error is not None else None
    censored = raw['finish_reason'] == 'length'
    return {
        'case_id': cid, 'arm': arm, 'original_job_id': job,
        'expected': want, 'committed_expression': expr, 'value': value,
        'absolute_error': error, 'relative_error': relative,
        'numeric_correct': error <= max(1e-4, abs(want)*1e-5)
            if error is not None and not censored else None,
        'within_1_percent': relative <= .01
            if relative is not None and not censored else None,
        'censored': censored, 'finish_reason': raw['finish_reason'],
        'tokens': raw.get('tokens', len(raw.get('completion_ids', []))),
        'source': str(source), 'source_sha256': sha(source),
    }


def summary(rows):
    out = {}
    for arm in sorted({r['arm'] for r in rows}):
        subset = [r for r in rows if r['arm'] == arm]
        relatives = [r['relative_error'] for r in subset
                     if r['relative_error'] is not None and not r['censored']]
        out[arm] = {
            'correct': sum(r['numeric_correct'] is True for r in subset),
            'n': len(subset), 'censored': sum(r['censored'] for r in subset),
            'unparsed': sum(r['value'] is None for r in subset),
            'within_1_percent': sum(r['within_1_percent'] is True for r in subset),
            'median_relative_error': statistics.median(relatives) if relatives else None,
            'tokens_total': sum(r['tokens'] for r in subset),
        }
    return out


def main():
    integrity = read(OUT / 'diagnostic-integrity.json')
    assert integrity['status'] == 'pass'
    expected = {r['id']: r for r in read(OUT / 'data/numeric-private-key.json')}
    fit_audit = read(OUT / 'fit512-answer-audit.json')
    jobs = read(OUT / 'fit512-probe-jobs.json')
    assert set(fit_audit) == {r['id'] for r in jobs}
    fit = [score(j['id'], 'sft512', j['id'], Path(fit_audit[j['id']]['source']),
                 fit_audit[j['id']], expected) for j in jobs]
    style_audit = read(OUT / 'prior-format-answer-audit.json')
    private = read(OUT / 'prior-format-private-key.json')
    assert set(style_audit) == set(private)
    style = []
    for cid, key in private.items():
        source = OUT / 'prior-format-review' / f'{cid}.json'
        original_path = Path(key['source'])
        assert key['source_sha256'] == sha(original_path)
        expected_folder = 'prior-format-' + key['arm'] + ('-81k' if key['cap'] == 81920 else '')
        assert original_path.parent == OUT / expected_folder
        raw, blind = read(original_path), read(source)
        assert raw['id'] == key['job_id']
        assert raw['original_job_id'] == key['original_job_id']
        for field in ['messages', 'raw_text', 'final_text', 'finish_reason']:
            assert raw[field] == blind[field], (cid, field)
        assert len(raw['completion_ids']) == blind['tokens']
        style.append(score(cid, key['arm'], key['original_job_id'], source,
                           style_audit[cid], expected))
    # Same four questions under the original short-decimal instruction.
    original = read(OUT / 'results.json')['numeric_cases']
    selected = {j['original_job_id'] for j in read(OUT / 'prior-format-jobs.json')}
    original4 = [dict(r, original_job_id=r['job_id']) for r in original
                 if r['job_id'] in selected]
    assert len(original4) == 8
    result = {
        'scope': 'post-hoc diagnostics; four fixed heldout shapes, one training seed',
        'fit512': summary(fit), 'fit512_cases': fit,
        'prior_format': summary(style), 'prior_format_cases': style,
        'same_four_original_format': summary(original4),
        'same_four_original_format_cases': original4,
    }
    (OUT / 'diagnostic-results.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if not k.endswith('_cases')},
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
