"""Post-grading descriptive summaries; no hypothesis tests or new selection gate.

Requires complete committed grades before opening a condition mapping. Censored
records keep primary/lenient=None and are reported separately from natural stops.
"""
import argparse
import collections
import json

import bind_reviews as binding
from campaign import RUN, read, sha, write, stamp


def join_review(rows, directory, kind):
    packets = {p['review_id']: p for p in binding.packets_at(directory)}
    grades = read(directory / 'grades.json')
    assert len(grades) == len(packets)
    assert {g['review_id'] for g in grades} == set(packets)
    for g in grades:
        binding.validate_grade(packets[g['review_id']], g)
    receipt_path = directory / 'binding-receipt.json'
    if not receipt_path.exists():
        receipt_path = directory / 'grading-receipt.json'
    receipt = read(receipt_path)
    assert receipt['mapping_opened'] is False
    if receipt_path.name == 'binding-receipt.json':
        assert receipt['state'] == 'complete'
        assert receipt['packets'] == receipt['bound'] == len(packets) and receipt['missing'] == []
        assert receipt['rubric_sha256'] == sha(binding.HERE / 'REVIEW.md')
    else:
        assert receipt['state'] in ('stable_grading_complete', 'final_group_grading_complete')
        assert receipt['packets'] == len(packets)
    assert receipt['grades_sha256'] == sha(directory / 'grades.json')
    committed_packet = receipt.get('canonical_packet_sha256', receipt.get('packet_sha256',
        receipt.get('inputs_sha256', {}).get('blind-packets.json')))
    assert committed_packet == sha(directory / 'blind-packets.json')
    # All complete grades and their commitments have been verified above.
    mapping_path = directory / 'mapping.researcher-only.json'
    assert sha(mapping_path) == read(directory / 'receipt.json')['mapping_sha256']
    mapping = read(mapping_path)
    assert {m['review_id'] for m in mapping} == set(packets)
    by_grade = {g['review_id']: g for g in grades}
    mapped = {}
    for m in mapping:
        assert m['kind'] == kind and m['observed_success'] and m['finish_reason'] == 'stop'
        assert m['file_sha256'] == sha(m['file'])
        output = read(m['file'])
        assert binding.digest(output) == packets[m['review_id']]['content_sha256']
        key = (m['arm'], m['training_seed'], m['kind'], m['id'])
        assert key not in mapped
        mapped[key] = (m, by_grade[m['review_id']])
    selected = [dict(r) for r in rows if r['kind'] == kind]
    assert len({(r['arm'], r['training_seed'], r['kind'], r['id']) for r in selected}) == len(selected)
    assert all(r['finish_reason'] in ('stop','length') and isinstance(r['observed_success'], bool)
               and r['observed_success'] == (r['numeric_correct'] and r['finish_reason'] == 'stop')
               for r in selected), 'Inconsistent completion/success metadata'
    success_keys = {(r['arm'], r['training_seed'], kind, r['id']) for r in selected if r['observed_success']}
    assert success_keys == set(mapped), 'Mapping does not cover exactly the current numeric successes'
    for r in selected:
        key = (r['arm'], r['training_seed'], kind, r['id'])
        r['primary_success'] = None if r['finish_reason'] != 'stop' else False
        r['lenient_success'] = None if r['finish_reason'] != 'stop' else False
        if r['observed_success']:
            m, g = mapped[key]
            assert all(m.get(k) == r.get(k) for k in (
                'arm','training_seed','kind','id','source_id','replicate','file','file_sha256',
                'cap','finish_reason','observed_success','numeric_correct','tokens','value',
                'expected','absolute_error','relative_error','parse_method'))
            r.update(primary_success=g['verdict'] == 'valid', lenient_success=g['lenient_valid'],
                     review_id=g['review_id'], verdict=g['verdict'], rationale=g['rationale'],
                     solution_type=g.get('solution_type','unspecified'))
    return selected


def totals(rows):
    natural = [r for r in rows if r['finish_reason'] == 'stop']
    primary_known = all('primary_success' in r for r in rows)
    return dict(n=len(rows), natural=len(natural), censored=len(rows)-len(natural),
                numeric=sum(r['observed_success'] for r in natural),
                primary=sum(r['primary_success'] is True for r in natural) if primary_known else None,
                lenient=sum(r['lenient_success'] is True for r in natural) if primary_known else None,
                tokens=sum(r['tokens'] for r in rows), max_tokens=max((r['tokens'] for r in rows), default=0),
                cap_counts=dict(collections.Counter(str(r['cap']) for r in rows)))


def paired(rows, arm, control):
    a = {r['id']: r for r in rows if r['arm'] == arm}
    b = {r['id']: r for r in rows if r['arm'] == control}
    assert len(a) == sum(r['arm'] == arm for r in rows)
    assert len(b) == sum(r['arm'] == control for r in rows)
    assert a.keys() == b.keys(), ('unpaired IDs', arm, control)
    result = dict(arm=arm, control=control, n=len(a), censored=0,
                  wins=[], losses=[], both_valid=[], neither_valid=[])
    for ident in sorted(a):
        x, y = a[ident], b[ident]
        assert x['cap'] == y['cap'] and x['source_id'] == y['source_id']
        if x['primary_success'] is None or y['primary_success'] is None:
            result['censored'] += 1
        else:
            label = ('both_valid' if y['primary_success'] else 'wins') if x['primary_success'] else ('losses' if y['primary_success'] else 'neither_valid')
            result[label].append(dict(id=ident, family=x['source_id']))
    return result


def summarize(rows, kind):
    assert all(r['kind'] == kind for r in rows)
    assert len({(r['arm'], r['training_seed'], r['kind'], r['id']) for r in rows}) == len(rows)
    grouped = collections.defaultdict(list)
    old_ids = {r['id'] for r in read(RUN / 'jobs/confirm-old.json')}
    fresh_ids = {r['id'] for r in read(RUN / 'jobs/fresh6.json')}
    for r in rows:
        if kind == 'confirmation':
            assert r['id'] in old_ids | fresh_ids
            part = 'old12' if r['id'] in old_ids else 'fresh6'
        elif kind == 'main':
            part = 'sample' + str(r['replicate'])
        else:
            part = r.get('split') or 'all'
        grouped[(r['training_seed'], part)].append(r)
    result = {}
    for (seed, part), selected in grouped.items():
        arms = sorted({r['arm'] for r in selected})
        comparisons = []
        if all('primary_success' in r for r in selected):
            for arm in arms:
                if arm != 'Base' and 'Base' in arms:
                    comparisons.append(paired(selected, arm, 'Base'))
            for arm, control in [('S128','X128'),('S512','X512'),('D512','DX512'),('D6','DX6'),('D6','D512')]:
                if arm in arms and control in arms:
                    comparisons.append(paired(selected, arm, control))
        result[f'{seed}:{part}'] = dict(
            arms={arm:totals([r for r in selected if r['arm']==arm]) for arm in arms},
            paired=comparisons,
            per_family={arm:{family:totals([r for r in selected if r['arm']==arm and r['source_id']==family])
                for family in sorted({r['source_id'] for r in selected if r['arm']==arm})} for arm in arms})
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--kind', required=True, choices=['main','confirmation','precision'])
    parser.add_argument('--review', required=True)
    parser.add_argument('--scores', default='scores/current.json')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    assert '/' not in args.review and args.review not in ('.','..')
    rows = read(RUN / args.scores)
    joined = join_review(rows, RUN / args.review, args.kind)
    result = dict(time=stamp(), kind=args.kind, source_scores_sha256=sha(RUN/args.scores),
                  grades_sha256=sha(RUN/args.review/'grades.json'), review=args.review,
                  groups=summarize(joined,args.kind), rows=joined,
                  note='Descriptive paired counts. Repeated samples and related shapes are correlated; no significance claim. Censored outputs are not failures.')
    if args.kind == 'main':
        result['numeric_diagnostics'] = {kind:summarize([r for r in rows if r['kind']==kind],kind)
                                         for kind in ('short','retention')}
    write(RUN/args.output,result)
    print(json.dumps(dict(output=args.output, kind=args.kind, records=len(joined))))
