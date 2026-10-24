"""Post-measurement integrity and accounting verification; never executes solver jobs."""
import csv
import json
import math
from collections import Counter
from pathlib import Path

from common import HERE, IMPL, REPO, S6, SOURCE, THREADS, load, progress, save, sha, source_manifest, utc


def main():
    freeze = load(HERE / 'freeze.json')
    for f,h in freeze['measurement_files_sha256'].items():
        assert sha(HERE / f) == h, f
    assert sha(S6 / 'preparation-hashes.json') == freeze['preparation_sha256']
    assert sha(S6 / 'run-plan.json') == freeze['run_plan_sha256']
    assert sha(S6 / 'same-group-split.json') == freeze['same_group_split_sha256']
    source, files = source_manifest()
    assert source == SOURCE and files == load(S6 / 'source-hashes.json')['files_sha256']
    preparation = load(S6 / 'preparation-hashes.json')
    differences = []
    for category in ['files_sha256','input_occurrences_sha256','protected_source_files_sha256','reference_provenance_sha256']:
        for relative, expected in preparation[category].items():
            p = Path(relative) if relative.startswith('/') else REPO / relative
            actual = sha(p)
            if actual != expected:
                differences.append(dict(category=category,path=str(p),expected_sha256=expected,current_sha256=actual,
                    current_mtime_utc=__import__('datetime').datetime.fromtimestamp(p.stat().st_mtime, __import__('datetime').timezone.utc).isoformat()))
    # The independently added prose appendix was not used to change this experiment.
    assert all(d['path'] == str(S6 / 'switch-scope.md') and d['category'] == 'files_sha256' for d in differences), differences
    jobs = load(S6 / 'run-plan.json')['jobs']
    ends = [load(HERE/'receipts'/f"{j['queue_index']:03d}.end.json") for j in jobs]
    starts = [load(HERE/'receipts'/f"{j['queue_index']:03d}.start.json") for j in jobs]
    assert len(starts) == len(ends) == 264
    assert len({(j['identity'],j['seed'],j['configuration']) for j in starts}) == 264
    assert [r['queue_index'] for r in sorted(ends,key=lambda r:r['start_monotonic'])] == list(range(264))
    intervals = []
    raw_checked = 0
    for j,s,e in zip(jobs,starts,ends):
        for k,v in j.items():
            assert s[k] == e[k] == v, (j['queue_index'],k)
        assert 0 < e['wall_seconds'] <= 180
        assert e['cleanup_seconds'] <= 2
        assert e['state'] == 'completed' and e['exit_code'] == 0
        assert not e['resource_violations']
        assert e['observed_processes']
        for p in e['observed_processes']:
            assert p['affinity_sets'] == p['thread_affinity_sets'] == [[e['cpu']]]
            env = p['actual_environment']
            assert all(env.get(k) == v for k,v in THREADS.items())
            assert env.get('GEOSOLVER_S3_TANGENCY_MODE') == ('T1' if j['configuration']=='T1' else None)
            assert env['PYTHONPATH'] == '/tmp/s3-impl/src'
            assert env['PYTHONDONTWRITEBYTECODE'] == '1'
            assert not any(k.startswith('GEOSOLVER_ABLATE_') for k in env)
        for file in e['files'].values():
            p = Path(file['path'])
            assert p.stat().st_size == file['size_bytes'] and sha(p) == file['sha256'], str(p)
            raw_checked += 1
        intervals.append((e['start_monotonic'],e['start_monotonic']+e['wall_seconds']+e['cleanup_seconds'],e['cpu']))
    by_cpu = {}
    for a,b,c in intervals:
        if c in by_cpu:
            assert a >= by_cpu[c]
        by_cpu[c] = b
    events = sorted([(a,1) for a,b,c in intervals]+[(b,-1) for a,b,c in intervals])
    concurrent = peak = 0
    for _, delta in events:
        concurrent += delta
        peak = max(peak,concurrent)
    assert peak <= 12
    audit = load(HERE/'audit.json')
    lf = audit['load_file']
    assert sha(lf['path']) == lf['sha256']
    references = load(HERE/'references.json')['cases']
    with (HERE/'per-run.csv').open() as f:
        runs = list(csv.DictReader(f))
    with (HERE/'per-problem.csv').open() as f:
        problems = list(csv.DictReader(f))
    assert len(runs)==264 and len(problems)==44
    missing = [r for r in runs if not references[r['case_id']]['available']]
    assert len(missing)==12 and all(r['ok']==r['C_seed']=='' for r in missing)
    for r in runs:
        if r['ok']=='True':
            assert float(r['C_seed']) == float(r['wall_seconds']) < 180
        elif r['ok']=='False':
            assert float(r['C_seed']) == 180
    for p in problems:
        for mode in ['T2','T1']:
            rs = [r for r in runs if r['case_id']==p['case_id'] and r['configuration']==mode]
            if p['reference_available']=='False':
                assert p['solved_'+mode]==p['C_'+mode]==''
            else:
                n = sum(r['ok']=='True' for r in rs)
                assert p['solved_'+mode] == str(n>=2)
                assert math.isclose(float(p['C_'+mode]),sum(float(r['C_seed']) for r in rs)/3,rel_tol=1e-14)
    reverse = [p['case_id'] for p in problems if p['solved_T1']=='True' and p['solved_T2']=='False']
    positive = [p['case_id'] for p in problems if p['solved_T2']=='True' and p['solved_T1']=='False']
    matches = load(HERE/'graded-answers.json')
    mismatches = [m for m in matches if m['reason']=='answer_set_mismatch']
    assert len(mismatches)==6
    assert {jobs[m['queue_index']]['case_id'] for m in mismatches}=={'HMMT-2010-FEB-GEO-09'}
    full=references['HMMT-2010-FEB-GEO-09']['canonical_set']
    for m in mismatches:
        assert m['answer_set'] != full
    summary = dict(verified_utc=utc(), frozen_measurement_files_match=True,
        source_and_all_source_files_match=True, inputs_references_targets_groups_and_queue_match=True,
        start_receipts=264,end_receipts=264,unique_keys=264,duplicate_or_retried_keys=0,
        fixed_fifo_verified=True,slot_overlap_absent=True,maximum_active_including_cleanup=peak,
        all_sampled_descendant_and_thread_affinities_match=True,all_sampled_thread_envs_match=True,
        cleanup_under_two_seconds=True,raw_files_rehashed=raw_checked,load_file_rehashed=True,
        costs_and_majority_accounting_verified=True,reference_missing_runs=12,
        measured_wall_sum_seconds=sum(e['wall_seconds'] for e in ends),
        sampled_peak_tree_rss_bytes=max(e['peak_tree_rss_bytes'] for e in ends),
        T2_only_observed=positive,T1_only_observed=reverse,
        answer_set_mismatch_queue_indices=[m['queue_index'] for m in mismatches],
        preparation_document_drift_after_start=differences,
        document_drift_note='Only switch-scope.md received an external static-audit prose appendix after launch. Initial preparation hashes matched at prepare and run entry; the original source/targets/groups/references/queue and frozen measurement/grading files still match. The appendix was not used to alter conditions, predictions, grading, or results. Left intact.',
        measurement_and_grading_code_modified_after_freeze=False)
    save(HERE/'verification.json',summary)
    audit['post_measurement_verification']=summary
    save(HERE/'audit.json',audit)
    answer = (HERE/'answer.md').read_text()
    answer = answer.replace('生の負荷時系列は外部rawのload.jsonl。',f"生の負荷時系列は `{lf['path']}`。")
    # Report-only clarification. Do not change frozen code, canonical references or judgments.
    answer += ('\n採点内訳は正解230 seed、不正解22 seed（no_answer_found 16、答え集合不一致6）、参照欠測12 seed。'
        '集合不一致6件はHMMT-2010-FEB-GEO-09であり、solverが返した集合を既存の独立集合{70,160}と全体照合して不一致とした。'
        f"T2のみ成功は{', '.join(positive)}、逆方向のT1のみ成功は{', '.join(reverse)}。逆方向の結果も保持した。\n")
    same = load(HERE/'judgments.json')['groups']['same_formula_18']
    obsratio = same['observed_mean_C_T1']/same['observed_mean_C_T2']
    answer += (f"\n式一致18問のうち採点可能17問では成功数16対16、観測部分の費用平均比は{obsratio:.6e}。"
        'この参考値で欠測を埋めたり、V2を支持へ変更したりしない。\n')
    answer += (f"\n追加整合性検査: 264開始/終了receipt、264一意キー、FIFO、同slot重複なし、"
        f"原本{raw_checked}ファイルと負荷時系列のSHA-256再照合、費用/多数決計算の一致を確認。"
        f"計測wall合計={summary['measured_wall_sum_seconds']:.6e}秒、最大観測process-tree RSS={summary['sampled_peak_tree_rss_bytes']:.6e} bytes。"
        '個別検査結果はverification.json。\n')
    if differences:
        answer += ('\n文書の追補: 実行開始後に別作業でswitch-scope.mdへ精密化ヤコビの静的監査追補が加わった。'
            '実行前には準備hashの全一致を確認済みで、終了後も入力・群・参照・キュー・ソース全ファイル・固定driver/採点コードは一致した。'
            'この文書差分は条件・予測・採点を変更せず、初期hashと現在hashをaudit.json/verification.jsonへ記録して追補を保持した。\n')
    (HERE/'answer.md').write_text(answer)
    progress('最終検証完了: 原本hash・固定コード/ソース/入力/群/参照/キュー・264一意キー・FIFO・slot非重複・資源/費用計算を確認。switch-scope.mdの外部文書追補のみを差分記録。commit/pushなし。')
    paths = [p for p in S6.rglob('*') if p.is_file()]
    assert all(p.stat().st_size < 3_000_000 for p in paths)
    hashes = {str(p.relative_to(HERE)):sha(p) for p in sorted(HERE.rglob('*')) if p.is_file() and p.name not in {'artifact-hashes.json','campaign.lock'} and '__pycache__' not in p.parts}
    save(HERE/'artifact-hashes.json',dict(created_utc=utc(),files_sha256=hashes,
        hash_manifest_policy='This manifest excludes itself and the empty runtime lock; all scientific artifacts and final verification code are included.',
        all_S6_files_under_3000000_bytes=True,largest_S6_file_bytes=max(p.stat().st_size for p in paths)))
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
