"""Stage newly final main answers while independent cap groups keep running.

Operational review scheduling only. The frozen extension rules and numeric
parser are reused; no GPU work, condition unmasking, or branch decision occurs.
"""
import argparse
import math

import campaign as c
import extend
import score


def final_group(group):
    """Return every final record only after the entire cap group is resolved."""
    arms = extend.ARMS if group == 'common' else extend.ARMS[:3]
    jobs = c.read(c.RUN / ('jobs/main12.json' if group == 'common' else 'jobs/main24.json'))
    if group == 'rep2':
        jobs = jobs[12:]
    job_ids = {j['id'] for j in jobs}
    artifact_keys = {}
    observed_caps = {}
    # Include incomplete artifacts in ambiguity/supersession checks. The
    # canonical scorer sees receipt-bearing failed directories as well.
    for arm in arms:
        prefix = f'{arm}-2026093001-main-'
        for directory in sorted((c.RUN / 'outputs').glob(prefix + '*')):
            artifact_cap = int(directory.name[len(prefix):].split('-')[0])
            relevant_ids = {p.name[:-7] for p in directory.glob('*-0.json')} & job_ids
            if directory.name == f'{prefix}{artifact_cap}-{group}':
                stage_jobs = c.RUN / f'extensions/jobs-main-{group}-{artifact_cap}.json'
                if stage_jobs.exists():
                    relevant_ids |= {j['id'] for j in c.read(stage_jobs)} & job_ids
            for ident in relevant_ids:
                key = (arm, ident, artifact_cap)
                assert key not in artifact_keys, ('ambiguous artifact regardless of receipt status', key)
                artifact_keys[key] = directory
                observed_caps[ident] = max(artifact_cap, observed_caps.get(ident, 0))
    active = jobs
    final = {}
    checked = []
    censored = []
    for index, (cap, context) in enumerate(extend.BOUNDS):
        hits = set()
        for arm in arms:
            source_jobs_path = (
                c.RUN / ('jobs/main24.json' if arm in extend.ARMS[:3] else 'jobs/main12.json')
                if index == 0 else c.RUN / f'extensions/jobs-main-{group}-{cap}.json'
            )
            if not source_jobs_path.exists():
                return None, dict(state='pending', group=group, arm=arm, cap=cap, reason='jobs not yet materialized')
            source_jobs = c.read(source_jobs_path)
            if index:
                assert source_jobs == active, ('ordered cap subset changed', group, cap)
            expected_by_id = {j['id']: (i, j) for i, j in enumerate(source_jobs)}
            records = {}
            for directory in sorted((c.RUN / 'outputs').glob(f'{arm}-2026093001-main-{cap}*')):
                receipt_path = directory / 'receipt.json'
                if not receipt_path.exists():
                    continue
                receipt = c.read(receipt_path)
                if receipt['status'] != 'complete':
                    continue
                files = list(directory.glob('*-0.json'))
                assert len(files) == receipt['completed_jobs']
                for path in files:
                    record = c.read(path)
                    if record['id'] not in {j['id'] for j in active}:
                        continue
                    assert record['id'] not in records, ('ambiguous same-cap output', arm, cap, record['id'])
                    assert receipt['jobs_sha256'] == c.sha(source_jobs_path)
                    assert (receipt['cap'], receipt['context'], receipt['batch_size']) == (cap, context, 4)
                    assert receipt['samples'] == 1 and receipt['enable_thinking'] is False
                    assert (receipt['temperature'], receipt['top_p'], receipt['top_k'], receipt['presence_penalty']) == (0.7, 0.95, 20, 0.2)
                    assert receipt['driver_sha256'] == c.sha(c.GEN / 'generate_batch.py')
                    assert receipt['model_revision'] == 'c202236235762e1c871ad0ccb60c8ee5ba337b9a'
                    expected_adapter = c.adapter(arm)
                    assert receipt['adapter'] == (str(expected_adapter) if expected_adapter else None)
                    if expected_adapter:
                        assert receipt['adapter_sha256'] == c.sha(expected_adapter / 'adapter_model.safetensors')
                    position, job = expected_by_id[record['id']]
                    assert record['messages'] == job['messages'] and record['seed'] == job['seed']
                    assert record['batch_start'] == position // 4 * 4
                    assert record['finish_reason'] in ('stop', 'length')
                    assert len(record['completion_ids']) <= cap
                    records[record['id']] = (path, record, receipt)
            for job in active:
                ident = job['id']
                if ident not in records:
                    return None, dict(state='pending', group=group, arm=arm, cap=cap, id=ident, reason='complete paired output absent')
                path, record, receipt = records[ident]
                final[arm, ident] = (path, record, receipt)
                checked.append(dict(arm=arm, id=ident, cap=cap, file=str(path), sha256=c.sha(path)))
                if record['finish_reason'] == 'length':
                    hits.add(ident)
        # Every member of this comparison must share inputs and batching.
        for job in active:
            paired = [final[arm, job['id']][1] for arm in arms]
            for record in paired[1:]:
                assert all(record[k] == paired[0][k] for k in ('messages', 'seed', 'prompt_ids', 'batch_start'))
        if not hits:
            break
        if index == len(extend.BOUNDS) - 1:
            censored = sorted(hits)
            break
        active = [j for j in jobs if j['id'] in hits]
    for (arm, ident), (_, _, receipt) in final.items():
        assert receipt['cap'] == observed_caps[ident], ('unexpected superseding artifact', arm, ident, receipt['cap'], observed_caps[ident])
    return final, dict(state='final', group=group, checked=checked, censored=censored)


def stage(group):
    c.verify_manifest()
    prior_review = c.read(c.RUN / 'review-stable/receipt.json')
    assert c.sha(c.HERE / 'REVIEW.md') == prior_review['rubric_sha256']
    assert c.sha(score.__file__) == prior_review['scorer_sha256']
    final, evidence = final_group(group)
    if final is None:
        return evidence
    excluded = set(c.read(c.RUN / 'parallel-review-policy.json')['stable_first_stage']['exclude_job_ids'])
    keys = {r['id']: r for p in (c.RUN / 'keys').glob('*.json') for r in c.read(p)}
    rows = []
    for (arm, ident), (path, output, receipt) in sorted(final.items()):
        if ident not in excluded:
            continue
        parsed, method, excerpt = score.module.parse(output['raw_text'])
        wanted = float(score.module.parse_numeric(keys[ident]['answer_exact']))
        value = None
        error = None
        correct = False
        if parsed is not None:
            try:
                value = float(score.module.parse_numeric(parsed))
                if math.isfinite(value):
                    error = abs(value - wanted)
                    correct = error <= max(1e-4, 1e-5 * abs(wanted))
                else:
                    value = None
            except (ValueError, TypeError, OverflowError, ZeroDivisionError):
                pass
        rows.append(dict(arm=arm, training_seed=2026093001, kind='main', id=ident,
                         source_id=output['source_id'], replicate=output.get('replicate', 1),
                         file=str(path), file_sha256=c.sha(path), cap=receipt['cap'],
                         finish_reason=output['finish_reason'], tokens=len(output['completion_ids']),
                         value=value, expected=keys[ident]['answer_exact'], numeric_correct=correct,
                         observed_success=correct and output['finish_reason'] == 'stop',
                         absolute_error=error, parse_method=method, answer_excerpt=excerpt[-500:]))
    name = f'review-{group}-final'
    score.blind(rows, review_name=name, kind='main')
    evidence.update(review_directory=name, staged_outputs=len(rows), created_utc=c.stamp(),
                    mapping_opened=False, branch_decision_allowed=False,
                    frozen_rubric_sha256=c.sha(c.HERE / 'REVIEW.md'))
    c.write(c.RUN / name / 'finality-receipt.json', evidence)
    return {k: evidence[k] for k in ('state', 'group', 'review_directory', 'staged_outputs', 'censored')}


if __name__ == '__main__':
    import json
    parser = argparse.ArgumentParser()
    parser.add_argument('group', choices=['common', 'rep2'])
    print(json.dumps(stage(parser.parse_args().group), ensure_ascii=False))
