"""Posthoc scale-normalized analysis of existing short numerical outputs.

No model calls or target-selected features. Reuses the previously fixed first
length and training-only median coefficient for every source. Correlation is
within-source centered, so merely recognizing a source's average ratio cannot
raise it. This is a behavioral diagnostic, not a causal mechanism attribution.
"""
from pathlib import Path
from collections import defaultdict
import hashlib
import itertools
import json
import math
import re
import statistics as st

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RUNTIME = ROOT / 'qwen/.runtime/numeric_sft_dose_control_20260928'
BASELINE = HERE.parent / 'numeric-sft-dose-control-2026-09-28/scale-baseline.json'


def read(p):
    return json.loads(p.read_text())


def correlation(xs, ys):
    mx, my = st.mean(xs), st.mean(ys)
    sx = sum((x-mx)**2 for x in xs)
    sy = sum((y-my)**2 for y in ys)
    return sum((x-mx)*(y-my) for x, y in zip(xs, ys))/math.sqrt(sx*sy) if sx*sy else None


def summarize(rows):
    groups = defaultdict(list)
    for r in rows:
        groups[r['source_id']].append(r)
    x, y = [], []
    order_correct = order_total = ties = 0
    for rs in groups.values():
        mx = st.mean(r['gold_log_ratio'] for r in rs)
        my = st.mean(r['pred_log_ratio'] for r in rs)
        x.extend(r['gold_log_ratio']-mx for r in rs)
        y.extend(r['pred_log_ratio']-my for r in rs)
        for a, b in itertools.combinations(rs, 2):
            dx = a['gold_log_ratio']-b['gold_log_ratio']
            dy = a['pred_log_ratio']-b['pred_log_ratio']
            if abs(dx) < 1e-12:
                continue
            order_total += 1
            order_correct += dx*dy > 0
            ties += abs(dy) < 1e-12
    model_ss = sum(r['log_error']**2 for r in rows)
    baseline_ss = sum(r['baseline_log_error']**2 for r in rows)
    return dict(n=len(rows), sources=len(groups), within_source_centered_log_ratio_correlation=correlation(x,y),
                within_source_pair_order_correct=order_correct, within_source_pairs=order_total,
                predicted_pair_ties=ties, log_squared_error_vs_scale_baseline=1-model_ss/baseline_ss,
                model_mean_squared_log_error=model_ss/len(rows), baseline_mean_squared_log_error=baseline_ss/len(rows),
                mean_absolute_log_error=st.mean(abs(r['log_error']) for r in rows),
                scale_mean_absolute_log_error=st.mean(abs(r['baseline_log_error']) for r in rows))


def main():
    inputs = [RUNTIME/'fit-scores.json', RUNTIME/'fit-jobs.json', BASELINE]
    scores, jobs_list, baseline = map(read, inputs)
    jobs = {j['id']: j for j in jobs_list}
    features = baseline['feature_selection']['by_source']
    rows, excluded = [], []
    for r in scores['rows']:
        if r['value'] is None or r['value'] <= 0:
            excluded.append({k:r[k] for k in ('arm','job_id','split','value')})
            continue
        f = features[r['source_id']]
        text = jobs[r['job_id']]['messages'][0]['content']
        matches = re.findall(r'(?<![A-Za-z0-9_:])'+re.escape(f['field'])+r'\s*=\s*([+\-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+\-]?\d+)?)', text)
        assert len(matches) == 1, (r['job_id'], matches)
        length = float(matches[0])
        assert length > 0 and r['target'] > 0
        c = f['c_median_y_over_L']
        rows.append({k:r[k] for k in ('arm','job_id','source_id','split','target','value')} | dict(
            L=length, scale_coefficient=c, gold_log_ratio=math.log(r['target']/length),
            pred_log_ratio=math.log(r['value']/length), log_error=math.log(r['value']/r['target']),
            baseline_log_error=math.log(c*length/r['target'])))
    summary, by_source = {}, {}
    for arm in ['base','correct128','correct512','shuffled512']:
        summary[arm], by_source[arm] = {}, {}
        for split in ['trained_all','reserved_shape']:
            selected = [r for r in rows if r['arm']==arm and r['split']==split]
            summary[arm][split] = summarize(selected)
            by_source[arm][split] = {s:summarize([r for r in selected if r['source_id']==s]) for s in features}
    result = dict(analysis_type='posthoc, existing outputs, no training/inference',
                  definitions=dict(L='previously fixed first stated positive length per source',
                      c='median(training y/L), computed previously without heldout labels',
                      normalized='log(y/L), log(prediction/L)',
                      correlation='center each log-ratio within source separately, then pool',
                      skill='1 - sum(log(pred/y)^2)/sum(log(cL/y)^2); may be negative',
                      pair_order='sign agreement for every within-source normalized-answer pair; pairs are dependent'),
                  summary=summary, by_source=by_source, excluded_nonpositive=excluded, rows=rows,
                  inputs_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs})
    (HERE/'shape-residual.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    lines=['# Scale-normalized behavior (posthoc)', '',
           'The length field and median coefficient come unchanged from the previous scale baseline. No new model was run. These diagnostics describe saved outputs; they do not identify an internal algorithm or establish a causal reason for transfer.', '',
           '| Arm | Split | n | Within-source correlation of log(y/L) | Normalized pair-order matches | Squared-log improvement over cL |',
           '|---|---|---:|---:|---:|---:|']
    for arm, splits in summary.items():
        for split, s in splits.items():
            lines.append(f"| {arm} | {split} | {s['n']} | {s['within_source_centered_log_ratio_correlation']:.4f} | {s['within_source_pair_order_correct']}/{s['within_source_pairs']} | {s['log_squared_error_vs_scale_baseline']:.4f} |")
    lines += ['', 'Base has 8 nonpositive trained outputs and 2 nonpositive heldout outputs, omitted from log analysis. Thus base columns are incomplete and not directly comparable. All positive-label SFT arms include all 80/30 outputs.', '',
              'The 30 heldout rows are only 3 shapes in each of 10 sources; their 30 within-source pairs are dependent. This is not 30 independent tests. A high correlation with poor precision can coexist: following the direction of geometric variation is weaker than learning an exact reusable relation.', '',
              'Reproduce with `python3 shape_residual.py`. Per-source figures, every normalized row, and input hashes are in `shape-residual.json`.']
    (HERE/'shape-residual.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
