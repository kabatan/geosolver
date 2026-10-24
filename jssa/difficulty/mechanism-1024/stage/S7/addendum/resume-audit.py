"""Supplemental provenance and saved-matrix audit; immutable protocol unchanged.

Run after report.py and verify-v2.py, then rerun verify-v2.py for final hashes.
"""
from common import *
from collections import Counter
from mpmath import mp
from measure import spectrum, kind
import importlib.util

spec = importlib.util.spec_from_file_location('addendum_report', OUT / 'report.py')
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)
fmt, table = report.fmt, report.table


def matrix(rows, n):
    return mp.matrix([[mp.mpf(x) for x in row] for row in rows]) if rows else mp.matrix(0, n)


def main():
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    manifest = check_manifest()
    amendment = load(OUT / 'implementation-amendment.json')
    assert sha(OUT / 'pre-run-hashes.json') == amendment['original_manifest_sha256']
    for path, digest in amendment['files'].items():
        assert sha(path) == digest, path
    resume = load(OUT / 'resume-state.json')
    for key, digest in resume['valid_existing_results'].items():
        assert sha(OUT / 'results' / (key + '.json')) == digest
    records = [load(OUT / 'results' / (key + '.json')) for key in manifest['case_ids']]
    assert len(records) == 49 and all(r['status'] == 'ok' for r in records)
    users, digests = {}, {}
    matrices_checked = 0
    max_svd_error = mp.mpf(0)
    with mp.workdps(200):
        def check(a, saved):
            nonlocal matrices_checked, max_svd_error
            values, active, zeros, error = spectrum(a)
            assert saved['classification'] == kind(values[0])
            assert saved['nonzero_rows'] == active and saved['dimension_zero_count'] == zeros
            assert len(values) == len(saved['singular_values'])
            for actual, recorded in zip(values, saved['singular_values'], strict=True):
                assert abs(actual - mp.mpf(recorded)) < mp.mpf('1e-190') * max(1, abs(actual))
            assert abs(values[0] - mp.mpf(saved['sigma'])) < mp.mpf('1e-190')
            assert error < mp.mpf(manifest['protocol']['svd_error_below'])
            matrices_checked += 1
            max_svd_error = max(max_svd_error, error)

        for r in records:
            for path, digest in r['accessed_files'].items():
                assert path not in digests or digests[path] == digest
                assert sha(path) == digest, path
                digests[path] = digest
                users.setdefault(path, []).append(r['case_id'])
            for sample in r['samples']:
                assert mp.mpf(sample['stage1_central_relative_error']) < mp.mpf('1e-120')
                for side in ('plus', 'minus', 'central'):
                    check(matrix(sample['jacobian_' + side], r['n']), sample[side])
                if r['case_id'] in manifest['protocol']['w3']:
                    base = matrix(sample['base_jacobian'], r['n'])
                    raw = matrix(sample['jacobian_central'], r['n'])
                    check(base, sample['base'])
                    for rev in sample['single_condition_reversions']:
                        ch = rev['change']
                        rows = [[base[i, j] for j in range(r['n'])] for i in range(base.rows)
                                if i not in ch['base_rows']]
                        if ch['bundle_index'] is not None:
                            rows.append([raw[ch['bundle_index'], j] for j in range(r['n'])])
                        assert len(rows) == rev['rows']
                        check(matrix(rows, r['n']), rev)

    # Includes files hashed during immutable-input verification, even if not
    # directly imported/evaluated by an individual worker. Keep roles separate.
    paths = set(READS) | set(digests) | {str(S7 / 'report.py')}
    inventory = []
    for path in sorted(paths):
        p = Path(path)
        if not p.is_file():
            continue
        if p.is_relative_to(OUT):
            role = 'addendum'
        elif p.is_relative_to(FROZEN):
            assert path in manifest['files'] and p.suffix in {'.py', '.json'}
            role = 'frozen_source'
        else:
            assert p.is_relative_to(S7)
            rel = p.relative_to(S7)
            allowed = (len(rel.parts) == 1 and (p.suffix == '.py' or p.name in {'README.md', 'classification.csv'}))
            allowed |= len(rel.parts) == 2 and rel.parts[0] == 'inputs' and p.suffix == '.json'
            allowed |= len(rel.parts) == 3 and rel.parts[0] == 'results' and p.name in {'reference.json', 'sigma-details.json'}
            assert allowed, path
            role = 'stage1'
        inventory.append(dict(path=path, role=role, sha256=sha(p), worker_case_ids=users.get(path, []),
                              in_pre_run_manifest=path in manifest['files']))
    counts = Counter(r['role'] for r in inventory)
    save(OUT / 'used-files-audit.json', dict(
        status='ok', scope='research inputs, frozen sources, and addendum files; OS/Python dependency reads are outside this inventory',
        individual_worker_accessed_files=len(digests), file_role_counts=dict(counts),
        files=inventory, all_research_inputs_allowlisted=True, preserved_complete_results=len(resume['valid_existing_results']),
        recovered_empty_outputs=resume['empty_files_quarantined'], matrices_svd_recomputed=matrices_checked,
        maximum_recomputed_svd_error=fmt(max_svd_error),
        amendment_hashes_checked=True, immutable_manifest_hashes_checked=True,
        stage_2_executed=False, rule_changes=False,
        operator_reviewed_preregistration='stage/S3/preregistration-14.md (explicitly requested protocol document)',
        blocked_read_attempts=[dict(path=str(S7 / 'pre-run-hashes.json'), content_read=False,
            reason='Initial supplemental-audit import resolved stage1/report.py; its non-allowlisted metadata read was blocked by common.guard. Corrected to explicit addendum/report.py import.')],
        note='Worker receipts record research/source reads. Immutable-manifest reads are included separately; this is not a retrospective OS syscall trace.'))

    marker = '\n## 再開時の確認と固定閾値での不定例\n'
    doc = (OUT / 'addendum.md').read_text().split(marker)[0]
    lines = [marker, '',
             '再開前は42ファイル中40問が完了済みで、2ファイルが0バイトだった。空ファイルはinterrupted-empty-files/に保持し、不足7問と合わせて9問を再計算した。既存40問のSHA-256は不変。run-v2.py / report.py / verify-v2.pyはいずれも終了コード0を直接確認した。', '',
             '不定3問はいずれもk=70で特異、k=60で片側σが固定境界1e-60を上回る中間域に入り不定となった。判定は変更しない。', '']
    lines += table(['問題', 'σ(+), k=70', 'σ(+), k=60', 'k=70', 'k=60', '最終'], [
        (r['case_id'], fmt(r['samples'][0]['plus']['sigma']), fmt(r['samples'][1]['plus']['sigma']),
         r['samples'][0]['classification'], r['samples'][1]['classification'], r['classification'])
        for r in records if r['classification'] == '不定'])
    lines += ['',
              'W3指定5問はすべて距離0の座標差だけが適用された例で、rawはすべて片側差分で微分不能となった。したがって、この5問を「滑らかなraw系の特異性を避けた」証拠として数えない。座標差による局所的な行列の改善は確認できるが、元のW3の一般化はこの診断からは支持しない。精密化に関する予測は本補遺では評価していない。', '',
              '[使用ファイル監査](used-files-audit.json)には問題ごとの読込記録、許可範囲、ハッシュを保存した。再開状態はresume-state.json。追加監査では保存行列からSVDとW3の単条件復帰を再計算した。判定規則・protocol.json・pre-run-hashes.json・登録済み実装は変更していない。', '']
    (OUT / 'addendum.md').write_text(doc + '\n'.join(lines))
    marker = '\n## 5問を合わせた解釈\n'
    doc = (OUT / 'w3-analysis.md').read_text().split(marker)[0]
    (OUT / 'w3-analysis.md').write_text(doc + marker + '\n'
        '5問すべてで効いている種類は距離0の座標差だけで、raw診断は微分不能である。AIME-2013-II-04、HMMT-2006-FEB-GEO-01、HMMT-2009-FEB-GEO-01、JMO-2021-PRE-07は該当する1条件を戻すと両幅で特異になる。AIME-2020-II-04は3条件のどれを1つだけ戻しても両幅で非特異を保つため、単独で必要な1条件は特定できない。3条件すべてがrawのときに中央行列が特異となる結果は、各条件が単独で必要という主張を支持しない。\n\n'
        '片側行列がm<nでσ=0.0e+0となる例も、行列片側差gが1e-20を超えるので微分不能に分類する。この5問を滑らかなraw系の特異性回避として数えることはできない。精密化の到達桁数に関する判定はしていない。\n')
    files = [p for p in OUT.rglob('*') if p.is_file()]
    assert all(p.stat().st_size <= 3_000_000 for p in files)
    print(json.dumps(dict(status='ok', cases=len(records), preserved_results=40,
                          worker_accessed_files=len(digests), matrices_svd_recomputed=matrices_checked,
                          maximum_file_bytes=max(p.stat().st_size for p in files)), ensure_ascii=False))


if __name__ == '__main__':
    main()
