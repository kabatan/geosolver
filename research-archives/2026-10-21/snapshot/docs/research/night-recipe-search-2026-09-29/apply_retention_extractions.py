"""Disclosed retention-only extraction repair; native score bytes are preserved."""
import argparse
import collections
import hashlib
import json
import math
import statistics
import sys
from pathlib import Path

import sympy
import campaign as c
sys.path.insert(0, str(c.ROOT))
from qwen.answer_check import parse_numeric


def agree(packets, readers):
    """Check condition-free full-text claims before any expected key is read."""
    by_id = {p['review_id']: p for p in packets}
    assert len(by_id) == len(packets)
    assert all(set(p) == {'review_id', 'messages', 'final_text', 'content_sha256'} for p in packets), 'Not a condition-free extraction packet'
    tables = []
    for reader in readers:
        table = {g['review_id']: dict(g, excerpt=g.get('excerpt', g.get('verbatim_excerpt'))) for g in reader}
        assert len(reader) == len(table) and set(table) == set(by_id)
        for ident, g in table.items():
            p = by_id[ident]
            digest = hashlib.sha256(json.dumps([p['messages'], p['final_text']], ensure_ascii=False).encode()).hexdigest()
            assert g['content_sha256'] == p['content_sha256'] == digest
            assert g['full_text_read'] is True and g['read_characters'] == len(p['final_text'])
            assert isinstance(g['rationale'], str) and g['rationale'].strip()
            assert g['status'] in ('committed', 'unparsed', 'ambiguous')
            assert isinstance(g['excerpt'], str) and g['excerpt'] and g['excerpt'] in p['final_text']
            if g['status'] == 'committed':
                parse_numeric(g['expression'])
            else:
                assert g['expression'] is None
        tables.append(table)
    assert len(tables) == 2
    for ident in by_id:
        a, b = (table[ident] for table in tables)
        assert a['status'] == b['status'], ('Extraction disagreement', ident)
        if a['status'] == 'committed':
            assert sympy.simplify(parse_numeric(a['expression']) - parse_numeric(b['expression'])) == 0, ('Expression disagreement', ident)
    return [tables[0][p['review_id']] for p in packets]


def correction():
    directory = c.RUN / 'review-retention-extraction'
    packets_path = directory / 'blind-packets.json'
    receipt = c.read(directory / 'receipt.json')
    assert c.sha(packets_path) == receipt['packet_sha256']
    assert receipt['original_scorer_sha256'] == c.sha(c.HERE / 'score.py')
    paths = [directory / f'extractions-reader-{i}.json' for i in (1, 2)]
    claims = agree(c.read(packets_path), [c.read(p) for p in paths])
    # Commit the transcriptions and independent agreements before unmasking.
    commitment = dict(state='agreed_extractions_committed', packet_sha256=c.sha(packets_path),
                      readers_sha256={p.name: c.sha(p) for p in paths}, claims=claims,
                      mapping_opened_before_commit=False, expected_values_supplied=False)
    committed = directory / 'extraction-commitment.json'
    if committed.exists():
        assert c.read(committed) == commitment
    else:
        c.write(committed, commitment)
    mapping_path = directory / 'mapping.researcher-only.json'
    assert c.sha(mapping_path) == receipt['mapping_sha256']
    mapping = c.read(mapping_path)
    assert len(mapping) == len(claims) == 28
    assert {m['review_id'] for m in mapping} == {g['review_id'] for g in claims}
    lookup = {g['review_id']: g for g in claims}
    packet_by_id = {p['review_id']: p for p in c.read(packets_path)}
    result = {}
    for m in mapping:
        assert c.sha(m['file']) == m['file_sha256']
        output = c.read(m['file'])
        packet = packet_by_id[m['review_id']]
        assert output['id'] == m['id'] and output['finish_reason'] == 'stop'
        assert output['messages'] == packet['messages'] and output['final_text'] == packet['final_text']
        assert m['file'] not in result
        result[m['file']] = lookup[m['review_id']]
    return result, dict(extraction_commitment_sha256=c.sha(committed), mapping_sha256=c.sha(mapping_path),
                        amendment_sha256=c.sha(c.HERE / 'RETENTION_EXTRACTION_AMENDMENT.md'),
                        original_scorer_sha256=c.sha(c.HERE / 'score.py'), correction_driver_sha256=c.sha(__file__))


def validate_scope(rows, phase, current):
    assert isinstance(rows, list) and rows
    initial_expected = set()
    for arm in c.ARMS:
        for kind in ('short', 'retention', 'main'):
            name = ('main24' if arm in ('Base', 'S128', 'X128') else 'main12') if kind == 'main' else kind
            initial_expected.update((arm, 2026093001, kind, j['id']) for j in c.read(c.RUN / f'jobs/{name}.json'))
    expected = set(initial_expected)
    if phase == 'branch':
        decision = c.read(c.RUN / 'decision.json')
        assert decision['status'] == 'complete'
        if decision['branch'] == 'A':
            selected = decision['selected']
            control = {'S128': 'X128', 'S512': 'X512', 'D512': 'DX512'}[selected]
            expected.update((arm, 2026093002, 'confirmation', j['id']) for arm in ('Base', selected, control)
                            for j in c.read(c.RUN / 'jobs/confirmation18.json'))
        else:
            assert decision['branch'] == 'B' and decision['selected'] is None
            expected.update((arm, 2026093001, 'precision', j['id']) for arm in ('Base', 'D512', 'DX512', 'D6', 'DX6')
                            for j in c.read(c.RUN / 'jobs/main12.json'))
    keys = [(r['arm'], r['training_seed'], r['kind'], r['id']) for r in rows]
    assert set(keys) == expected, ('Different phase or incomplete score coverage', phase)
    assert len(set((k, r['cap']) for k, r in zip(keys, rows))) == len(rows), 'Duplicate same-cap score'
    if current:
        assert len(keys) == len(set(keys))
    assert len({r['file'] for r in rows}) == len(rows)


def apply(phase):
    assert phase in ('initial', 'branch')
    claims, provenance = correction()
    native = c.RUN / f'scores/native-{phase}'
    prior_path = c.RUN / f'retention-extraction-correction-{phase}.json'
    prior = c.read(prior_path) if prior_path.exists() else None
    native_bytes = {}
    for filename in ('all-stages.json', 'current.json', 'summary.json'):
        source = c.RUN / 'scores' / filename
        snapshot = native / filename
        native_bytes[filename] = snapshot.read_bytes() if snapshot.exists() else source.read_bytes()
        if prior:
            assert prior['native_sha256'][filename] == hashlib.sha256(native_bytes[filename]).hexdigest()
            assert prior['provenance'] == provenance
    native_rows = {n: json.loads(native_bytes[n]) for n in ('all-stages.json', 'current.json')}
    for n, rows in native_rows.items():
        validate_scope(rows, phase, n == 'current.json')
        retention_files = [r['file'] for r in rows if r['kind'] == 'retention']
        assert len(retention_files) == 28 and set(retention_files) == set(claims), 'Retention coverage changed'
        assert all(r['parse_method'] != 'condition_hidden_retention_commitment' for r in rows if r['kind'] == 'retention'), 'Native snapshot is already corrected'
    maxcaps = {}
    for row in native_rows['all-stages.json']:
        key = (row['kind'], row['id'])
        maxcaps[key] = max(row['cap'], maxcaps.get(key, 0))
    selected = [r for r in native_rows['all-stages.json'] if r['cap'] == maxcaps[(r['kind'], r['id'])]]
    assert selected == native_rows['current.json'], 'Current/all-stages selection differs'
    differences = []
    repaired = {}
    for filename in ('all-stages.json', 'current.json'):
        rows = native_rows[filename]
        changed = []
        for original in rows:
            row = dict(original)
            if row['kind'] == 'retention':
                claim = claims[row['file']]
                assert row['file_sha256'] == c.sha(row['file'])
                value = float(parse_numeric(claim['expression'])) if claim['status'] == 'committed' else None
                wanted = float(parse_numeric(row['expected']))
                error = abs(value - wanted) if value is not None else None
                correct = value is not None and math.isfinite(value) and error <= max(1e-4, 1e-5 * abs(wanted))
                row.update(value=value, absolute_error=error,
                           relative_error=error / max(abs(wanted), 1e-30) if error is not None else None,
                           numeric_correct=correct, observed_success=correct and row['finish_reason'] == 'stop',
                           parse_method='condition_hidden_retention_commitment', answer_excerpt=claim['excerpt'][-500:])
                if filename == 'current.json':
                    differences.append(dict(file=row['file'], native_value=original['value'], corrected_value=value,
                                            native_success=original['observed_success'], corrected_success=row['observed_success'],
                                            review_id=claim['review_id']))
            else:
                assert row == original
            changed.append(row)
        repaired[filename] = changed
    summary = json.loads(native_bytes['summary.json'])
    retention = collections.defaultdict(list)
    for row in repaired['current.json']:
        if row['kind'] == 'retention':
            retention[f"{row['arm']}:{row['training_seed']}:retention"].append(row)
    for group, rows in retention.items():
        assert len(rows) == 4
        summary[group].update(numeric_success=sum(r['observed_success'] for r in rows),
                              unparsed=sum(r['value'] is None for r in rows),
                              median_relative_error=statistics.median([r['relative_error'] for r in rows if r['relative_error'] is not None])
                              if any(r['relative_error'] is not None for r in rows) else None)
    repaired['summary.json'] = summary
    repaired_bytes = {n: (json.dumps(v, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode() for n, v in repaired.items()}
    # Preflight every input and every replacement before publishing any score.
    for filename in native_bytes:
        allowed = {hashlib.sha256(native_bytes[filename]).hexdigest()}
        if (native / filename).exists():
            allowed.add(hashlib.sha256(repaired_bytes[filename]).hexdigest())
        assert c.sha(c.RUN / 'scores' / filename) in allowed, ('Changed score input', filename)
    native.mkdir(parents=True, exist_ok=True)
    for filename, data in native_bytes.items():
        path = native / filename
        if path.exists():
            assert path.read_bytes() == data
        else:
            path.write_bytes(data)
    c.write(native / 'repair-transaction.json', dict(state='prepared', provenance=provenance,
            replacements_sha256={n: hashlib.sha256(v).hexdigest() for n, v in repaired_bytes.items()}))
    for filename, value in repaired.items():
        c.write(c.RUN / 'scores' / filename, value)
    record = dict(time=c.stamp(), status='complete', phase=phase, scope='retention_only',
                  main_and_short_unchanged=True, thresholds_unchanged=True,
                  provenance=provenance, changes=differences,
                  native_sha256={n: hashlib.sha256(v).hexdigest() for n, v in native_bytes.items()},
                  corrected_sha256={n: c.sha(c.RUN / 'scores' / n) for n in ('current.json', 'all-stages.json', 'summary.json')})
    c.write(c.RUN / f'retention-extraction-correction-{phase}.json', record)
    print(json.dumps(dict(status='complete', phase=phase, retention_rows=len(differences), main_and_short_unchanged=True)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=['initial', 'branch'], required=True)
    apply(parser.parse_args().phase)
