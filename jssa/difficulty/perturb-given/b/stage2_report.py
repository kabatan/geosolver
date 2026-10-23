"""Concise Japanese report from completed fixed Q40b analyses."""
import json
from collections import Counter
from pathlib import Path

from stage2_common import HERE, OUT, RAW, read, sha, utc, write


def main():
    analysis = OUT / 'analysis'
    metrics = read(analysis / 'metrics.json')
    audit = read(analysis / 'audit.json')
    summaries = read(analysis / 'success-and-cost-distributions.json')
    problems = read(analysis / 'problem-results.json')
    diagnostics = {p['canonical_id']: read(OUT / 'diagnostics' / (p['canonical_id'] + '.json')) for p in problems}
    assert all(diagnostics.values()), 'all 40 diagnostic records are required'
    mechanism = [p for p in problems if p['classification'] == 'improved' and diagnostics[p['canonical_id']]['M']]
    M = sum(d['M'] for d in diagnostics.values())
    eligible = sum(d.get('m', -1) >= d.get('n_vars', 1) for d in diagnostics.values())
    changed = [p['canonical_id'] for p in problems if diagnostics[p['canonical_id']].get('box_changes')]
    improved_changed = [p['canonical_id'] for p in problems if p['classification'] == 'improved'
                        and p['canonical_id'] in changed]
    P4 = len(mechanism) >= 8
    joint = metrics['P1'] and metrics['P2']
    diagnostics_summary = {'M_problems': M, 'M_and_stable_improvement': len(mechanism),
        'matching_problems': [p['canonical_id'] for p in mechanism], 'P4': P4,
        'm_ge_n_problems': eligible, 'box_changed_problems': changed,
        'improved_and_box_changed': improved_changed,
        'majority_of_improved_have_changed_boxes': len(improved_changed) > metrics['improved'] / 2,
        'diagnostic_missing_cases': {k: d['missing_reason'] for k, d in diagnostics.items() if d.get('missing_reason')},
        'diagnostic_seed_status': dict(Counter(
            s.get('missing_reason', 'complete') for d in diagnostics.values() for s in d.get('seeds', {}).values()))}
    write(analysis / 'mechanism-summary.json', diagnostics_summary)
    decision = {**metrics, 'P4': P4, 'mechanism': diagnostics_summary,
        'primary_joint_prediction_passed': joint,
        'valid_cost_comparison': audit['valid_cost_comparison'],
        'valid_singularity_causal_experiment': audit['valid_cost_comparison'] and metrics['feasibility_causal_audit_passed'],
        'human_difficulty_tested': False, 'other_methods_tested': False, 'A_center_adopted': False}
    write(analysis / 'decision.json', decision)
    raw_manifest = [{'path': str(p), 'bytes': p.stat().st_size, 'sha256': sha(p)}
                    for p in sorted(RAW.glob('*.log'))]
    write(OUT / 'raw-log-manifest.json', raw_manifest)
    dev, unseen = metrics['cohorts']['development'], metrics['cohorts']['unseen']
    stable3 = sum(p['improving_seeds'] == 3 for p in problems)
    seed_text = '、'.join(f"{s}: {counts['improved']}/40" for s, counts in metrics['seed_counts'].items())
    first = ('費用比較として不可（計測契約の不備）。' if not audit['valid_cost_comparison'] else
             '事前の改善仮説をこの条件で支持。人間の直感との比較は未実施。' if joint else
             'この条件では改善仮説を支持しない。')
    judge = lambda x: ('成立' if x else '不成立') if audit['valid_cost_comparison'] else '判定不可'
    ci = metrics['CPU_95pct_interval']
    original, perturbed = summaries['by_variant']['original'], summaries['perturbed']
    lines = [
        '# Q40b：与えられた数値を崩す実験', '',
        f"① **直感に反するか**：{first}", '',
        f"② **深い理論が必要か**：必要とは示せない。退化の軽減と安定改善の同時成立は{len(mechanism)}/40問。", '',
        f"③ **広く再現するか**：安定改善{metrics['improved']}/40、悪化{metrics['worsened']}/40。開発{dev['improved']}/20（323問中の確認済み{dev['improved']}）、未使用{unseen['improved']}/20（候補54問から選択）。3 seedすべてで改善したのは{stable3}/40問。", '',
        '④ **solverならではか**：未確認。他手法との比較はしていない。', '',
        '**人間が導けるか**は未検証。**他手法でも得られるか**も未検証。**Aの中心としては未採用**。', '',
        '| 予言 | 固定した成立線 | 実測 | 判定 |',
        '|---|---|---|---|',
        f"| P1：安定改善が多い | 改善≥16、悪化≤6、片側p≤0.05 | 改善{metrics['improved']}、悪化{metrics['worsened']}、p={metrics['sign_test_p']:.4g} | {judge(metrics['P1'])} |",
        f"| P2：全体の費用低下 | CPU倍率≥1.25、壁時間≥1.15、CPU区間下端>1 | CPU {metrics['G_CPU']:.3f}倍［95%区間 {ci[0]:.3f}–{ci[1]:.3f}］、壁 {metrics['G_wall']:.3f}倍 | {judge(metrics['P2'])} |",
        f"| P3：両群で再現 | 各群改善≥5、改善>悪化 | 開発 {dev['improved']}対{dev['worsened']}、未使用 {unseen['improved']}対{unseen['worsened']} | {judge(metrics['P3'])} |",
        f"| P4：退化の軽減 | 機構条件M＋安定改善≥8問 | {len(mechanism)}/40 | {judge(P4)} |", '',
        f"主検証はP1・P2の同時成立が条件で、今回は**{judge(joint)}**。seed別の改善数（各40問）は {seed_text}。", '',
        f"最初に全条件の検証を通った図は、元版 **{original['successes']}/120**、摂動版 **{perturbed['successes']}/600**。失敗・timeout・欠測は費用180秒として分母に残した。" + ('答えの同定は全実行で0回。' if audit['valid_cost_comparison'] and audit['all_identify_calls_zero'] else '同定と計測の不備は監査に記録した。'), '',
    ]
    if not audit['valid_cost_comparison']:
        lines += [f"計測監査の不備は{len(audit['errors'])}件。上の数値は固定分母の参考集計で、有効な費用比較としては採用しない。", '']
    failed = metrics['all_three_failed_perturbed_variants']
    if failed >= 41:
        lines += [f"摂動200版中{failed}版が3 seed全失敗で、事前の上限40版を超えた。**特異性を除く因果実験として不可**。失敗だけから解がないとは断定しない。", '']
    else:
        lines += [f"摂動200版中{failed}版が3 seed全失敗。失敗だけから解がないとは断定しない。", '']
    box_text = (f"安定改善のうち箱幅の変化を伴うものは{len(improved_changed)}/{metrics['improved']}問。"
                if metrics['improved'] else '安定改善は0問。')
    lines += [f"機構条件Mは{M}/40問（等式数≥変数数は{eligible}/40）。{box_text}枝の合流や深い理論の必要性を証明した実験ではない。", '']
    load = metrics['load_average_start_1min']
    if load:
        lines += [f"共有機の試行開始時load average（1分）は{load['min']:.1f}–{load['max']:.1f}、中央値{load['median']:.1f}。CPU時間を主指標にしたが、180秒の壁時間上限を通じて負荷の影響は残る。壁時間の結果はこの負荷条件つき。", '']
    lines += [
        '条件・閾値・seed・選択40問は変更せず、追加・交換・再試行なし。凍結版`60db4b6`、専用checkout、並列2。', '',
        '根拠：[実行許可receipt](execution/authorization-receipt.json)、[実装lock](implementation.lock.json)、[監査](execution/analysis/audit.json)、[720試行](execution/analysis/all-720-runs.csv)、[版別・群別集計](execution/analysis/success-and-cost-distributions.json)、[水準別集計](execution/analysis/metrics.json)、[機構診断](execution/analysis/mechanism-summary.json)。生ログは`/tmp/q40b-raw/`に保存し、[hash一覧](execution/raw-log-manifest.json)を残した。', '',
    ]
    (HERE / 'answer.md').write_text('\n'.join(lines), encoding='utf-8')
    paths = [p for p in OUT.rglob('*') if p.is_file() and p.name != 'completion-manifest.json']
    write(OUT / 'completion-manifest.json', {'utc': utc(), 'answer_sha256': sha(HERE / 'answer.md'),
            'files': {str(p.relative_to(HERE)): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in sorted(paths)}})
    print(json.dumps({'answer': str(HERE / 'answer.md'), 'P4': P4, 'M_and_improved': len(mechanism),
                      'primary_joint': joint, 'cost_comparison_valid': audit['valid_cost_comparison']}))


if __name__ == '__main__':
    main()
