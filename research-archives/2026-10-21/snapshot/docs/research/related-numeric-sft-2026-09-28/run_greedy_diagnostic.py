"""Serial post-hoc numeric-only fit diagnostic, after the primary study and loss probe."""
import json, math, statistics, subprocess, time
import analyze as an
import run_pipeline as op

P, R, O = op.P, op.R, op.O

def main():
    while not (O/'automatic-diagnostics-complete.json').exists():
        time.sleep(5)
    for name, digest in op.read(O/'greedy-freeze.json')['sha256'].items():
        assert op.sha(op.Path(name)) == digest
    jobs = op.read(O/'greedy-jobs.json')
    key = op.read(O/'greedy-answer-key.json')
    rows, summary = [], {}
    for arm in ['base','sft-a']:
        label = f'{arm}-greedy-fit'
        args = [op.PY, P/'generate_greedy.py', '--jobs', O/'greedy-jobs.json', '--out', O/label]
        if arm != 'base':
            args += ['--adapter', O/'sft-a-train128/final/adapter-vllm']
        op.run(args, label, True, [O/'greedy-jobs.json', P/'GREEDY_FIT_DIAGNOSTIC.md', P/'generate_greedy.py'])
        for job in jobs:
            path = O/label/(job['id']+'-0.json')
            raw = op.read(path)
            assert raw['messages'] == job['messages']
            parsed, method, excerpt = an.parse(raw['raw_text'])
            target = float(an.parse_numeric(key[job['id']]['answer_exact']))
            value, error, correct = None, None, None
            if parsed is not None:
                try:
                    value = float(an.parse_numeric(parsed))
                    error = abs(value-target)/abs(target)
                    correct = math.isfinite(value) and (abs(value-target)<=1e-4 or error<=1e-5)
                except (ValueError, TypeError, OverflowError):
                    pass
            rows.append(dict(arm=arm, job_id=job['id'], source_id=job['source_id'], split=job['split'],
                             target=target, value=value, relative_error=error, numeric_correct=correct,
                             finish_reason=raw['finish_reason'], tokens=len(raw['completion_ids']),
                             file=str(path), file_sha256=op.sha(path), parse_method=method))
        summary[arm] = {}
        for split in ['trained_all','new_shape']:
            part = [r for r in rows if r['arm']==arm and r['split']==split]
            errors = [r['relative_error'] for r in part if r['relative_error'] is not None]
            summary[arm][split] = dict(n=len(part), correct=sum(r['numeric_correct'] is True and r['finish_reason']=='stop' for r in part),
                                      length=sum(r['finish_reason']=='length' for r in part), unparsed=sum(r['numeric_correct'] is None for r in part),
                                      median_relative_error=statistics.median(errors) if errors else None,
                                      mean_relative_error=statistics.mean(errors) if errors else None,
                                      within_1pct=sum(e<=.01 for e in errors),within_5pct=sum(e<=.05 for e in errors),within_10pct=sum(e<=.1 for e in errors))
    op.write(O/'greedy-fit-scores.json', {'status':'complete','scope':'posthoc exploratory greedy direct-number fit; not primary transfer endpoint','summary':summary,'rows':rows})
    subprocess.run([str(R/'.venv/bin/python'), str(P/'report_metrics.py')], check=True, cwd=R)
    op.write(O/'automatic-greedy-complete.json', {'status':'complete','unix':time.time()})
    print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__ == '__main__': main()
