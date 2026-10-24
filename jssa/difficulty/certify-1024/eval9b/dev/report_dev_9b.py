#!/usr/bin/env python3
"""Report completed saved attempts; no certification execution."""
import csv
from collections import Counter
import json
from pathlib import Path
from statistics import median
import sys
import sympy as sp

sys.dont_write_bytecode = True
E = Path(__file__).resolve().parent
D = E
BASE = E.parent.parent
sys.path.insert(0, str(BASE))
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
    m=json.loads((E/'pre-run-hashes.json').read_text())
    completion=json.loads((D/'completion.json').read_text())
    assert set(completion['completed'])==set(m['order']) and completion['attempts']==163
    records=[json.loads((D/'runs'/(cid+'.json')).read_text()) for cid in m['order']]
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
        assert r.get('attempts') == 1 and r.get('limits',{}).get('parallelism') == 4
        assert r.get('supervisor_finalized') is True
        assert r['limits']['threads'] == 1 and r['limits']['memory_bytes'] == 8<<30
        verified = [k for k in ('power','rabinowitsch') if r.get(k,{}).get('independent_verification') == 'verified']
        witness = False
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
    with (E.parent/'unseen/per-problem.csv').open() as f:
        assert fields==csv.DictReader(f).fieldnames, 'UNSEEN_COLUMN_MISMATCH'
    counts=Counter(r['category_ja'] for r in rows)
    cert=[r for r in rows if r['category_ja']=='認証']
    nn=sum(r['sign_category_ja']=='非負形で正の根' for r in cert)
    old=json.loads((BASE/'eval/dev/summary.json').read_text())
    assert old['certified']==65 and old['translated']==254
    unseen=json.loads((E.parent/'unseen/summary.json').read_text())
    # Values reported in the frozen unseen answer; check the saved summary agrees.
    unseen_answer=(E.parent/'unseen/answer.md').read_text()
    assert '7/16 = 43.8%' in unseen_answer and '7/7 = 100.0%' in unseen_answer and '(4＋7)/21 = 52.4%' in unseen_answer
    assert [(unseen[k]['numerator'],unseen[k]['denominator']) for k in ('C6','C7','C8')]==[(7,16),(7,7),(11,21)]
    def judge(a,b,threshold):
        return dict(numerator=a,denominator=b,threshold=f'>={threshold}%',rate=a/b if b else None,
            judgment=('的中' if 100*a>=threshold*b else '外れ') if b else '未判定')
    stats=dict(scope='事前登録9b・開発群の元非所属163問のみ',counts={k:counts[k] for k in ['認証','非所属','変換不能','時間上限','資源上限','実装エラー','検算不能']},
        C6=judge(len(cert),163,60),C7=judge(nn,len(cert),70),C8=judge(65+len(cert),254,50),
        unseen={k:unseen[k] for k in ('C6','C7','C8')},
        combined=dict(C6=judge(len(cert)+7,179,60),C7=judge(nn+7,len(cert)+7,70),C8=judge(65+len(cert)+11,275,50)),
        all_sign_counts=dict(Counter(r['sign_category_ja'] for r in rows)),
        certified_sign_counts=dict(Counter(r['sign_category_ja'] for r in cert)),positive_real_root_counts={},
        attempts=163,retries=0,interruptions_not_results=completion['interruptions_not_results'],restarted_once=completion['restarted_once'])
    T=sp.Symbol('T')
    for row in cert:
        # Count distinct strictly positive roots exactly, without selecting a branch.
        poly=sp.Poly(row['q_polynomial'],T).sqf_part()
        stats['positive_real_root_counts'][row['id']]=int(poly.count_roots(0,sp.oo))-(1 if poly.eval(0)==0 else 0)
    stats['certified_median_wall_seconds']=median(r['wall_seconds'] for r in cert) if cert else None
    ambiguous=[cid for cid,n in stats['positive_real_root_counts'].items() if n>1]
    stats['certified_multiple_positive_roots']=ambiguous
    details={};cause_counts=Counter()
    for row,result in zip(rows,records):
        if row['category_ja']=='認証':continue
        cid=row['id'];cat=row['category_ja'];work=D/'runs'/(cid+'.work')
        detail=dict(category_ja=cat,status=result['status'],reason_code=result.get('reason_code'),
            stage=result.get('stage'),last_algebra_event=result.get('last_algebra_event'),
            original_equation_counterexample=False)
        if cat=='非所属':
            p=sp.Poly(row['original_polynomial'],T)
            q=sp.Poly(row['q_polynomial'],T)
            even=sp.expand(p.as_expr()-p.as_expr().subs(T,-T))==0
            same_roots=p.sqf_part().monic()==q.sqf_part().monic()
            label='非所属：pが既に偶多項式、q=p²で根集合不変' if even else '非所属：±で根集合不変（偶多項式以外）' if same_roots else '非所属：目標の±を加えても所属せず、個別原因未検証'
            blocks=json.loads((work/'algebra-output.json').read_text())
            detail.update(even_p_so_q_equals_p_squared=even,q_has_same_root_set_as_p=same_roots,
                q_normal_form=blocks.get('NF1'),power_normal_forms_zero=result.get('power',{}).get('normal_forms_zero'),
                rabinowitsch_status=result.get('rabinowitsch',{}).get('status'),
                general_nonmembership_independent_verification='未実装')
        else:
            label=cat+'：'+str(result.get('reason_code') or result.get('last_algebra_event') or result.get('stage') or result['status'])
        detail['cause_bucket']=label;cause_counts[label]+=1;details[cid]=detail
    stats['uncertified_cause_counts']=dict(cause_counts)
    c.write_json(D/'nonmembership-analysis.json',dict(scope='保存結果と多項式の検査のみ。追加認証実行なし。',
        cause_counts=dict(cause_counts),details=details,witnesses={},script_sha256=c.sha(__file__),
        caveat='個別の幾何学的原因・元等式への反例代入・飽和で消えた枝の有無は未検証。非所属の一般の独立検算は未実装。'))
    c.write_json(D/'summary.json',stats)
    audit={p:dict(expected=h,actual=c.sha(p),matches=c.sha(p)==h) for p,h in m['hashes'].items()}
    assert all(x['matches'] for x in audit.values()), 'FROZEN_HASH_MISMATCH'
    starts=sorted((r['start_receipt'] for r in records),key=lambda x:x['start_unix'])
    if not completion['interruptions_not_results']:
        assert [s['id'] for s in starts]==m['order']
    else:
        # Every physical start is ordered within each controller run.
        allstarts=starts+[json.loads((D/'interrupted'/(cid+'.work')/'start.json').read_text()) for cid in completion['interruptions_not_results']]
        for pid in {s['controller_pid'] for s in allstarts}:
            batch=sorted((s for s in allstarts if s['controller_pid']==pid),key=lambda x:x['start_unix'])
            assert [s['id'] for s in batch]==sorted((s['id'] for s in batch),key=lambda x:m['order'].index(x))
    assert len(list((D/'runs').glob('*.work')))==163
    events=[]
    for r in records:
        start=r['start_receipt']['start_unix'];events.extend([(start,1),(start+r['wall_seconds'],-1)])
        runtime=json.loads((D/'runs'/(r['id']+'.work')/'runtime-limits.json').read_text())
        assert runtime['affinity']==[r['start_receipt']['cpu']] and r['start_receipt']['parallelism']==4
        assert runtime['rlimit_as']==[8<<30,8<<30] and runtime['rlimit_fsize']==[c.MAX_FILE,c.MAX_FILE]
        assert set(runtime['threads'].values())=={'1'}
        assert r['limits']['wall_seconds']==600
    active=peak=0
    for _,change in sorted(events):active+=change;peak=max(peak,active)
    assert peak<=4
    files=[p for p in D.rglob('*') if p.is_file()]
    oversized=[str(p) for p in files if p.stat().st_size>c.MAX_FILE];assert not oversized
    loads=[r['load_average_1m'] for r in rows]
    c.write_json(D/'post-run-audit.json',dict(hashes=audit,attempts=163,retries=0,ledger_count=163,
        interruptions_not_results=completion['interruptions_not_results'],restarted_once=completion['restarted_once'],
        start_order_matches=True,maximum_simultaneous_completed_attempts=peak,parallelism=4,cpu_per_problem=1,
        oversized_files=oversized,largest_file_bytes=max(p.stat().st_size for p in files),load_average_1m_range=[min(loads),max(loads)],
        report_sha256=c.sha(__file__),original_preregistration9_unchanged=True,eval_and_unseen_read_only=True))
    def pct(a,b):return f'{a}/{b} = {100*a/b:.1f}%' if b else '分母0、未判定'
    def table(label,values):
        lines=[f'| 予測（{label}） | 観測 | 判定 |','|---|---|---|']
        labels={'C6':'元の非所属の60%以上をqで認証','C7':'q認証の70%以上が非負形の±判定','C8':'9と9bの合計が変換済みの50%以上'}
        for k in ('C6','C7','C8'):
            v=values[k];lines.append(f'| {k}：{labels[k]} | {pct(v["numerator"],v["denominator"])} | {v["judgment"]} |')
        return lines+['']
    lines=table('開発群のみ',stats)
    lines += [f'C8は事前登録9の65問＋今回の{len(cert)}問を、変換できた254問で割った。元の時間・資源上限も分母に残す。', '',
        '事前登録9bは、事前登録9の開発外結果を見た後に固定した事後の拡張である。予測・閾値・規則と事前登録9の主判定は変更していない。','']
    lines+=table('開発外のみ・既存報告',stats['unseen'])
    lines+=['開発外の値は[既存の報告](../unseen/answer.md)から別掲した。開発外を再実行していない。','']
    lines+=table('開発群＋開発外の合算',stats['combined'])
    lines+=['合算の分母はC6が163＋16＝179、C8が254＋21＝275。C7は両群のq認証例だけを分母にした。','',
        '| 開発群の区分 | 件数 |','|---|---:|']
    for k,n in stats['counts'].items():lines.append(f'| {k} | {n} |')
    lines+=['',f'開発群の元「非所属」163問だけを各1回実行した。pはeval/dev/candidates.jsonとdev-answers-seed0.jsonの元sha256に照合し、全答えの最小多項式の積を使った。q=p(T)p(−T)に因子選択や正規化は加えていない。', '',
        f'q認証{len(cert)}問の±判定は、非負形で正の根が{nn}問、solver数値で選択が{len(cert)-nn}問。全163問の判定は'+ '、'.join(f'{k} {n}問' for k,n in stats['all_sign_counts'].items())+'。[固定規則](../sign-rule.md)の構文木判定だけを使った。','',
        'qでも認証できなかった問題の内訳は次のとおり。','', '| 保存結果・多項式から分かる範囲 | 件数 |','|---|---:|']
    for label,n in sorted(cause_counts.items(),key=lambda x:(-x[1],x[0])):lines.append(f'| {label} | {n} |')
    lines+=['','偶多項式ではq=p²なので根集合が増えず、目標の符号対称化だけでは改善しない。それ以外の非所属は、±を加えてもRab法で所属しなかったという範囲までの説明である。補助変数の符号・共役・配置など、個別の幾何学的原因は未検証。開発外で行ったような元等式への反例代入は今回行っていない。非所属一般の独立検算も未実装で、CSVにはその限界を明記した。時間・資源上限は停止条件であり、非所属とは数えない。[問題別の根拠](nonmembership-analysis.json)。','',
        '「±を除いた認証」は、代数化した元の等式・非零条件からq(T)=0が従うことを示す。Jが非単位、Rabinowitsch法で所属、べき法と無矛盾、少なくとも一方の証明書の独立検算を要求した。実図の存在・一意性や答え集合の完全性は示さない。非所属をsolverの誤答とは扱わない。','',
        f'q認証{len(cert)}問のうち、異なる正の実根が複数あるのは{len(ambiguous)}問（重複を除いた実根を厳密計数）。非負形でも負の根を除けるだけで、複数の非負根から目標を1つに決める証明にはならない。C7は固定規則による構文上の判定率である。問題IDと根数は[集計JSON](summary.json)に保存した。','',
        f'条件は各問600秒・8 GiB・1 CPU・並列4固定。IDのSHA-256昇順に開始し、開始時の1分load averageは{min(loads):.2f}〜{max(loads):.2f}。時間は起動・変換・飽和・基底・正規形・証明書・検算を含む壁時間で、負荷付き参考値。監視間隔0.1秒とOSの実行待ちによる停止検出の遅れはあり得る。','']
    interrupted=completion['interruptions_not_results']
    if interrupted:
        lines += ['中断は'+ '、'.join(interrupted)+f'の{len(interrupted)}問。中断を結果に数えず、内容とhashをinterrupted/に保存し、各問を最初から1回だけ再実行した。完了済みの結果の再試行と対象交換はない。','']
    else:lines+=['中断0問、再試行0回、対象交換なし。','']
    lines+=['制御プロセスはsetsid・nohup、標準入力/dev/null、標準出力・標準エラーをログへ向けて切り離した。排他的なcontroller lockと<ID>.workのmkdirを用いた。アプリや実行基盤からの強制停止まで存続を保証するものではないが、中断時の保存・再開処理を備えた。','',
        'certify.py・verify_certificate.py・sign-rule.mdと元のrun_9b.pyは変更していない。eval/以下とeval9b/unseen/への書き込みなし。[実行前hash](pre-run-hashes.json)と[終了時監査](post-run-audit.json)は全件一致。各成果物は2,900,000 byte以下。昇格・システム導入・他タスクへの介入・commit/pushなし。','',
        '[問題別CSV](per-problem.csv)・[進捗](progress.md)・[集計JSON](summary.json)・[実行記録](runs/)。']
    (D/'answer.md').write_text('\n'.join(lines)+'\n')
    assert all(p.stat().st_size<=c.MAX_FILE for p in D.rglob('*') if p.is_file())
    print(json.dumps({k:stats[k] for k in ('counts','C6','C7','C8','combined')},ensure_ascii=False,indent=2))


if __name__=='__main__':report()
