"""Prepare unseen exact-content precision packets without opening arm mappings.

Operational review staging only; the frozen scorer, rubric and generation are
unchanged. Run only after branch generation and canonical scoring are complete.
"""
from campaign import RUN, HERE, read, write, sha, stamp
from bind_reviews import packets_at, validate_grade


def main():
    complete = RUN / 'branch/generation-complete.json'
    assert complete.exists(), 'Branch generation must be complete'
    target = RUN / 'review-precision'
    packets = packets_at(target)
    known = set()
    provenance = []
    for name in ('review-stable', 'review-common-final', 'review-rep2-final'):
        source = RUN / name
        source_packets = {p['review_id']: p for p in packets_at(source)}
        grades = read(source / 'grades.json')
        receipt = read(source / 'grading-receipt.json')
        assert receipt['mapping_opened'] is False
        assert receipt['state'] in ('stable_grading_complete', 'final_group_grading_complete')
        assert receipt['grades_sha256'] == sha(source / 'grades.json')
        assert receipt.get('packet_sha256', receipt.get('inputs_sha256', {}).get('blind-packets.json')) == sha(source / 'blind-packets.json')
        assert len(grades) == len(source_packets)
        assert {g['review_id'] for g in grades} == set(source_packets)
        for grade in grades:
            packet = source_packets[grade['review_id']]
            validate_grade(packet, grade)
            known.add(packet['content_sha256'])
        provenance.append(dict(directory=str(source), packet_sha256=sha(source / 'blind-packets.json'),
                               grades_sha256=sha(source / 'grades.json'),
                               grading_receipt_sha256=sha(source / 'grading-receipt.json')))
    new = [p for p in packets if p['content_sha256'] not in known]
    out = RUN / 'review-precision-new'
    out.mkdir(exist_ok=True)
    path = out / 'blind-packets.json'
    if path.exists():
        assert read(path) == new, 'Refusing to change staged packets'
    else:
        write(path, new)
    receipt = dict(created_utc=stamp(), packet_sha256=sha(path),
                   rubric_sha256=sha(HERE / 'REVIEW.md'), protocol_sha256=sha(HERE / 'PROTOCOL.md'),
                   scorer_sha256=sha(HERE / 'score.py'), staging_driver_sha256=sha(__file__),
                   kind='precision', packets=len(new), characters=sum(len(p['final_text']) for p in new),
                   canonical_packet_sha256=sha(target / 'blind-packets.json'),
                   generation_completion_sha256=sha(complete), source_commitments=provenance,
                   filter='Exact messages/final-text SHA absent from committed source packets; no verdict-based filtering',
                   mapping_opened=False)
    receipt_path = out / 'receipt.json'
    if receipt_path.exists():
        previous = read(receipt_path)
        assert all(previous.get(k) == v for k, v in receipt.items() if k != 'created_utc')
    else:
        write(receipt_path, receipt)
    for packet in new:
        case = out / (packet['review_id'] + '.md')
        text = ('# ' + packet['review_id'] + ' / ' + packet['source_id'] + '\n\n'
                + packet['messages'][0]['content'] + '\n\nExpected numeric answer: '
                + packet['answer_expected'] + '\n\n## Model output\n\n'
                + packet['final_text'] + '\n')
        if case.exists():
            assert case.read_text() == text
        else:
            case.write_text(text)
    print({'canonical_packets': len(packets), 'new_packets': len(new),
           'new_characters': receipt['characters'], 'mapping_opened': False})


if __name__ == '__main__':
    main()
