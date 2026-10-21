"""Bind previously saved condition-hidden grades by exact messages/full-text hash.

Never opens a condition mapping. Default invocation validates only; --save writes
only when every canonical packet has a consistent complete source grade.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path

from campaign import RUN, HERE, read, write, sha, stamp


def digest(packet):
    return hashlib.sha256(json.dumps(
        [packet['messages'], packet['final_text']], ensure_ascii=False
    ).encode()).hexdigest()


def validate_packet(packet):
    assert packet['content_sha256'] == digest(packet), ('packet hash', packet['review_id'])


def validate_grade(packet, grade):
    validate_packet(packet)
    assert grade['review_id'] == packet['review_id']
    assert grade['content_sha256'] == packet['content_sha256']
    assert grade['verdict'] in ('valid', 'invalid', 'unclear')
    assert isinstance(grade['lenient_valid'], bool)
    assert isinstance(grade['rationale'], str) and grade['rationale'].strip()
    assert isinstance(grade['decisive_excerpts'], list) and grade['decisive_excerpts']
    assert grade['full_text_read'] is True
    assert grade['read_characters'] == len(packet['final_text'])
    assert all(isinstance(s, str) and s and s in packet['final_text']
               for s in grade['decisive_excerpts'])
    assert grade['verdict'] != 'valid' or grade['lenient_valid']
    assert grade['verdict'] != 'invalid' or not grade['lenient_valid']


def packets_at(directory):
    receipt = read(directory / 'receipt.json')
    assert receipt['packet_sha256'] == sha(directory / 'blind-packets.json')
    assert receipt['rubric_sha256'] == sha(HERE / 'REVIEW.md')
    assert receipt['scorer_sha256'] == sha(HERE / 'score.py')
    packets = read(directory / 'blind-packets.json')
    assert len({p['review_id'] for p in packets}) == len(packets)
    assert len({p['content_sha256'] for p in packets}) == len(packets)
    for p in packets:
        validate_packet(p)
    return packets


def bind(target, sources, save=False):
    packets = packets_at(target)
    known, evidence = {}, []
    for source in sources:
        source_packets = {p['review_id']: p for p in packets_at(source)}
        grades = read(source / 'grades.json')
        assert len(grades) == len(source_packets)
        assert {g['review_id'] for g in grades} == set(source_packets)
        grading_receipt = read(source / 'grading-receipt.json')
        assert grading_receipt['state'] in ('stable_grading_complete', 'final_group_grading_complete')
        assert grading_receipt['mapping_opened'] is False
        assert grading_receipt['grades_sha256'] == sha(source / 'grades.json')
        packet_commitment = grading_receipt.get('packet_sha256',
            grading_receipt.get('inputs_sha256', {}).get('blind-packets.json'))
        assert packet_commitment == sha(source / 'blind-packets.json')
        evidence.append(dict(directory=str(source), packet_sha256=sha(source / 'blind-packets.json'),
                             grades_sha256=sha(source / 'grades.json'),
                             grading_receipt_sha256=sha(source / 'grading-receipt.json')))
        for g in grades:
            p = source_packets[g['review_id']]
            validate_grade(p, g)
            h = p['content_sha256']
            if h in known:
                previous = known[h][0]
                assert (previous['verdict'], previous['lenient_valid']) == (g['verdict'], g['lenient_valid']), ('conflicting grade', h)
            else:
                known[h] = (g, source)
    bound, missing = [], []
    for p in packets:
        h = p['content_sha256']
        if h not in known:
            missing.append(p['review_id'])
            continue
        old, source = known[h]
        g = dict(old)
        g['review_id'] = p['review_id']
        g['binding_provenance'] = dict(directory=str(source), review_id=old['review_id'],
                                       source_grades_sha256=sha(source / 'grades.json'),
                                       exact_content_sha256=h)
        validate_grade(p, g)
        bound.append(g)
    result = dict(time=stamp(), state='complete' if not missing else 'incomplete',
                  packets=len(packets), bound=len(bound), missing=missing, sources=evidence,
                  canonical_packet_sha256=sha(target / 'blind-packets.json'),
                  rubric_sha256=sha(HERE / 'REVIEW.md'), mapping_opened=False,
                  counts=dict(collections.Counter(g['verdict'] for g in bound)))
    if save:
        assert not missing, ('unreviewed canonical packets', missing)
        path = target / 'grades.json'
        receiptpath = target / 'binding-receipt.json'
        expected_grade_hash = hashlib.sha256((json.dumps(bound, indent=2,
            ensure_ascii=False, allow_nan=False) + '\n').encode()).hexdigest()
        result['grades_sha256'] = expected_grade_hash
        if receiptpath.exists():
            old_receipt = read(receiptpath)
            assert path.exists(), 'Binding receipt without committed grades'
            assert all(old_receipt.get(k) == v for k, v in result.items() if k != 'time'), 'Stale binding receipt'
            assert old_receipt['grades_sha256'] == sha(path)
        if path.exists():
            assert read(path) == bound, 'Refusing to overwrite different canonical grades'
        else:
            write(path, bound)
        assert sha(path) == expected_grade_hash
        if not receiptpath.exists():
            write(receiptpath, result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', default='review')
    parser.add_argument('--sources', nargs='+', default=['review-stable', 'review-common-final', 'review-rep2-final'])
    parser.add_argument('--save', action='store_true')
    args = parser.parse_args()
    assert all(Path(n).name == n and n not in ('.', '..') for n in [args.target, *args.sources])
    print(json.dumps(bind(RUN / args.target, [RUN / s for s in args.sources], args.save), ensure_ascii=False, indent=2))
