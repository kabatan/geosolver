#!/usr/bin/env python3
"""Report completed saved attempts; no certification execution."""
import csv
from collections import Counter
import json
from pathlib import Path
from statistics import median
import sys
import sympy as sp

E = Path(__file__).resolve().parent
D = E/'unseen'
sys.path.insert(0, str(E.parent))
import certify as c


def category(r):
    s = r['status']
    if s == 'timeout':
        return '時間上限'
    if s == 'resource_limit':
        return '資源上限'
    if s == 'nonmember':
        return '非所属'
    good = (s == 'member' and r.get('proof_verified') is True and r.get('unit_ideal') is False
            and r.get('rabinowitsch',{}).get('status') == 'member'
            and r.get('power',{}).get('status') in ('member','inconclusive_m_le_4')
            and not r.get('singular_errors') and r.get('last_algebra_event') == 'finished end'
            and r.get('singular_returncode') == 0
            and any(r.get(k,{}).get('independent_verification') == 'verified' for k in ('power','rabinowitsch')))
    if good:
        return '認証'
    if s in ('member','algebraically_empty'):
        return '検算不能'
    return '実装エラー'


def report():
    m = json.loads((E/'pre-run-hashes.json').read_text())
    completion = json.loads((D/'completion.json').read_text())
    assert set(completion['completed']) == set(m['order']) and completion['attempts'] == 16
    analysis = json.loads((D/'nonmembership-analysis.json').read_text())
    records = [json.loads((D/'runs'/(cid+'.json')).read_text()) for cid in m['order']]
    fields = ['id','original_category_ja','q_degree','category_ja','sign_category_ja',
              'independent_verification','certificate_independent_verification','nonmembership_counterexample_verified',
              'status','original_polynomial','q_polynomial','target','polynomial_source','polynomial_source_sha256','dsl_sha256',
              'wall_seconds','worker_wall_seconds','translation_seconds','singular_wall_seconds','saturation_seconds',
              'power_status','power_first_zero','power_basis_seconds','power_nf_seconds','power_certificate_seconds',
              'power_verification_seconds','power_independent_verification','rabinowitsch_status',
              'rabinowitsch_basis_seconds','rabinowitsch_nf_seconds','rabinowitsch_certificate_seconds',
              'rabinowitsch_verification_seconds','rabinowitsch_independent_verification','unit_ideal',
              'load_average_1m','start_unix','cpu','parallelism','attempts','peak_tree_rss_bytes','reason_code','reason']
    rows = []
    for r in records:
        cid = r['id']; cand = m['records'][cid]
        assert r.get('attempts') == 1 and r.get('limits',{}).get('parallelism') == 2
        assert r['limits']['threads'] == 1 and r['limits']['memory_bytes'] == 8<<30
        verified = [k for k in ('power','rabinowitsch') if r.get(k,{}).get('independent_verification') == 'verified']
        witness = analysis['witnesses'].get(cid,{}).get('verified',False)
        row = {k:r.get(k,'') for k in fields if k in r}
        row.update(original_category_ja='非所属', q_degree=cand['degree'], category_ja=category(r),
                   sign_category_ja=cand['sign']['category_ja'], original_polynomial=cand['original_polynomial'],
                   q_polynomial=cand['polynomial'], target=cand['sign']['target'], polynomial_source=cand['source'],
                   polynomial_source_sha256=cand['source_sha256'], dsl_sha256=cand['dsl_sha256'],
                   certificate_independent_verification='可：'+','.join(verified) if verified else 'なし',
                   nonmembership_counterexample_verified=witness,
                   independent_verification='証明書検算可' if verified else '元等式への反例代入検算可' if witness else '非所属一般の独立検算は未実装',
                   power_first_zero=r.get('power',{}).get('first_zero_power',''))
        for k in ('power','rabinowitsch'):
            obj = r.get(k,{})
            row[k+'_status'] = obj.get('status','not_run')
            for key in ('basis_seconds','certificate_seconds','verification_seconds','independent_verification'):
                row[k+'_'+key] = obj.get(key,'')
            row[k+'_nf_seconds'] = obj.get('normal_form_seconds','')
        for key in ('load_average_1m','start_unix','cpu','parallelism'):
            row[key] = r['start_receipt'][key]
        rows.append(row)
    with (D/'per-problem.csv').open('w') as f:
        writer = csv.DictWriter(f,fields)
        writer.writeheader(); writer.writerows(rows)
    counts = Counter(r['category_ja'] for r in rows)
    cert = [r for r in rows if r['category_ja']=='認証']
    nn = sum(r['sign_category_ja']=='非負形で正の根' for r in cert)
    oldrows = list(csv.DictReader((E.parent/'eval/per-problem.csv').open()))
    oldcert = sum(r['category_ja']=='認証' for r in oldrows)
    converted = sum(r['translated']=='True' for r in oldrows)
    assert oldcert == 4 and converted == 21
    stats = dict(scope='開発外のみ。開発群は未実施。事前登録9の主判定は変更しない。',
                 counts={k:counts[k] for k in ['認証','非所属','時間上限','資源上限','実装エラー','検算不能']},
                 C6=dict(numerator=len(cert),denominator=16,threshold='>=60%',judgment='的中' if 100*len(cert)>=60*16 else '外れ'),
                 C7=dict(numerator=nn,denominator=len(cert),threshold='>=70%',
                         judgment=('的中' if 100*nn>=70*len(cert) else '外れ') if cert else '未判定'),
                 C8=dict(numerator=oldcert+len(cert),denominator=converted,threshold='>=50%',
                         judgment='的中' if 2*(oldcert+len(cert))>=converted else '外れ'),
                 all_sign_counts=dict(Counter(r['sign_category_ja'] for r in rows)),
                 certified_sign_counts=dict(Counter(r['sign_category_ja'] for r in cert)),
                 positive_real_root_counts={}, attempts=16,retries=0)
    T = sp.Symbol('T')
    for row in cert:
        roots = sp.Poly(row['q_polynomial'],T).real_roots()
        stats['positive_real_root_counts'][row['id']] = len({r for r in roots if r.is_positive is True})
    stats['certified_median_wall_seconds'] = median([r['wall_seconds'] for r in cert]) if cert else None
    c.write_json(D/'summary.json',stats)
    audit = {p:dict(expected=h,actual=c.sha(p),matches=c.sha(p)==h) for p,h in m['hashes'].items()}
    assert all(v['matches'] for v in audit.values())
    starts = sorted([r['start_receipt'] for r in records],key=lambda s:s['start_unix'])
    assert [s['id'] for s in starts] == m['order']
    ledgers = list((D/'runs').glob('*.work'))
    assert len(ledgers) == 16
    events = []
    for r in records:
        start = r['start_receipt']['start_unix']
        events.extend([(start,1),(start+r['wall_seconds'],-1)])
    active = peak = 0
    for _,change in sorted(events):
        active += change; peak = max(peak,active)
    assert peak <= 2
    files = [p for p in E.rglob('*') if p.is_file()]
    oversized = [str(p) for p in files if p.stat().st_size>c.MAX_FILE]
    assert not oversized
    loads = [r['load_average_1m'] for r in rows]
    c.write_json(D/'post-run-audit.json', dict(hashes=audit,attempts=16,retries=0,ledger_count=16,
                 start_order_matches=True,maximum_simultaneous_attempts=peak,parallelism=2,cpu_per_problem=1,
                 oversized_files=oversized,largest_file_bytes=max(p.stat().st_size for p in files),
                 load_average_1m_range=[min(loads),max(loads)],report_sha256=c.sha(__file__),
                 analysis_sha256=c.sha(E/'analyze_nonmembers.py'),
                 original_preregistration9_unchanged=True,development_evaluation_accessed=False))
    def pct(a,b):
        return f'{a}/{b} = {100*a/b:.1f}%' if b else '分母0、未判定'
    lines = ['| 予測（開発外のみ） | 観測 | 判定 |','|---|---|---|',
             f'| C6：元の非所属の60%以上をqで認証 | {pct(len(cert),16)} | {stats["C6"]["judgment"]} |',
             f'| C7：q認証の70%以上が非負形の±判定 | {pct(nn,len(cert))} | {stats["C7"]["judgment"]} |',
             f'| C8：9と9bの合計が変換済みの50%以上 | (4＋{len(cert)})/21 = {100*(4+len(cert))/21:.1f}% | {stats["C8"]["judgment"]} |','',
             '**開発群は未実施。これは事前登録9の結果を見て固定した事後の拡張で、事前登録9の主判定は変えない。** C8の分母21問には、事前登録9の時間上限1問も含む。','',
             '開発外の元「非所属」16問だけを各1回実行した。再試行・対象交換なし。','',
             '| 区分 | 件数 |','|---|---:|']
    for key in ['認証','非所属','時間上限','資源上限','実装エラー','検算不能']:
        lines.append(f'| {key} | {counts[key]} |')
    lines += ['',f'認証{len(cert)}問の±判定は、非負形で正の根が{nn}問、solver数値で選択が{len(cert)-nn}問。16問全体では非負形が{stats["all_sign_counts"].get("非負形で正の根",0)}問、solver数値が{stats["all_sign_counts"].get("solver数値で選択",0)}問（targetが `r` と `W/H`）。構文木だけによる[固定規則](../sign-rule.md)で判定した。','',
              'qでも非所属だった9問の主な内訳は次のとおり。区分・予測の判定を変えるための追加実行はしていない。','',
              '- **2問：pが既に偶多項式。** AIME-2005-II-08、HMMT-2015-FEB-GUTS-24。q=p²なので根集合が増えず、目標の±だけでは改善しない。前者では補助距離の負の枝が残り、元等式を満たす複素目標の反例も確認した。',
              '- **7問：目標の±以外の枝。** 残る非所属7問すべてで、元の等式と非零条件を満たしてq≠0となる代入を有理数・代数数の厳密計算で確認した。例：AIME-2004-II-07は求める290/3以外に10/3、HMMT-2020-FEB-GUTS-13は112/65以外に112/33、HMMT-2012-FEB-GUTS-06は72以外に32の枝がある。内部の符号・角定数の共役・配置の分岐は、目標だけの符号対称化では除けない。','',
              '全9問でRab法は正常終了して非所属、q〜q⁴の正規形も非零だった。8問には上記の元等式への反例代入検算があり、HMMT-2015-FEB-GUTS-24の非所属一般の独立検算は未実装。「q=0の枝が飽和で消えた」かの切り分けは今回行っておらず、その原因の件数は断定しない。反例は代数化後の条件に対するもので、元DSLの不等式や主値まで満たす実図とは限らない。[問題別の根拠と代入値](nonmembership-analysis.json)。','',
              '「±を除いた認証」は、元の等式・非零条件からq(T)=0が従うことの認証である。Jが非単位、Rab法で所属、べき法と無矛盾、少なくとも一方の証明書の独立検算を要求した。−T側の負の値を除く理由は求める量の非負形だけであり、実図の存在・一意性や答え集合の完全性は示さない。非所属もsolverの誤答とは扱わない。','']
    ambiguous = [cid for cid,n in stats['positive_real_root_counts'].items() if n>1]
    if ambiguous:
        lines += ['さらに、'+ '、'.join(ambiguous)+'ではqに正の実根が2個ある。非負形だけでは答え1個に絞れず、p(−T)の根すべてを排除できるわけでもない。C7は固定規則による構文上の判定率で、完全な根選択の証明率ではない。','']
    lines += [f'条件は600秒・8 GiB・1 CPU/問・並列2。IDのSHA-256昇順で開始した。各問開始時の1分load averageは{min(loads):.2f}〜{max(loads):.2f}。時間は起動・変換・飽和・基底・正規形・証明書・独立検算を含む壁時間で、負荷付きの参考値。各区間は[問題別CSV](per-problem.csv)に記録した。','']
    for r in records:
        if r['status'] in ('timeout','resource_limit'):
            lines += [f'{r["id"]}：{category(r)}、{r["wall_seconds"]:.3f}秒。直近段階は `{r.get("stage")}`。途中の所属マーカーだけで認証には数えない。','']
    lines += ['certify.py・verify_certificate.py・翻訳器は変更なし。[実行前ハッシュ](../pre-run-hashes.json)と[終了時監査](post-run-audit.json)は全件一致。各ファイルは2,900,000 byte以下。開発群のeval/dev/は読み書きせず、システム導入・昇格・他タスクの操作・commit/pushは行っていない。', '',
              '[進捗](../progress.md)・[集計JSON](summary.json)・[実行記録](runs/)。']
    (D/'answer.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(stats,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    report()
