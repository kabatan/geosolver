#!/usr/bin/env python3
"""Aggregate saved attempts only. Refuses to report an unfinished campaign."""
import csv
from collections import Counter
import hashlib
import json
from pathlib import Path
from statistics import median
import subprocess
import sys

E=Path(__file__).resolve().parent
sys.path.insert(0,str(E))
import judge_c3_c5 as judge

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,obj): Path(p).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')

def category(r):
    s=r['status']; p=r.get('power',{}); q=r.get('rabinowitsch',{})
    if s=='no_answer': return '対象外：答えなし'
    if s=='unsupported': return '変換不能'
    if s=='timeout': return '時間上限'
    if s=='resource_limit': return '資源上限'
    if s=='nonmember': return '非所属'
    success=(s=='member' and r.get('proof_verified') is True and r.get('unit_ideal') is False
             and q.get('status')=='member' and not r.get('singular_errors')
             and r.get('last_algebra_event')=='finished end'
             and any(obj.get('independent_verification')=='verified' for obj in (p,q)))
    if success: return '認証'
    if s in ('member','algebraically_empty'): return '検算不能'
    return '実装エラー'

def make_csv():
    m=json.loads((E/'pre-run-hashes.json').read_text())
    assert (E/'completion.json').exists(),'CAMPAIGN_NOT_COMPLETE'
    records=[json.loads((E/'runs'/(cid+'.json')).read_text()) for cid in m['order']]
    assert len(records)==29 and all(r['status']!='running' for r in records)
    fields=['id','group','source_group','polynomial_source','polynomial_source_sha256','seed','answer_count',
            'category_ja','status','polynomial','degree','translated','proof_verified','independent_verification',
            'nonmembership_counterexample_verified','wall_seconds','worker_wall_seconds','translation_seconds','singular_wall_seconds','saturation_seconds',
            'power_status','power_first_zero','power_basis_seconds','power_nf_seconds','power_basis_size',
            'power_certificate_seconds','power_verification_seconds','power_independent_verification',
            'rabinowitsch_status','rabinowitsch_basis_seconds','rabinowitsch_nf_seconds','rabinowitsch_basis_size',
            'rabinowitsch_certificate_seconds','rabinowitsch_verification_seconds','rabinowitsch_independent_verification',
            'nvars','nequations','saturation_factors','unit_ideal','peak_tree_rss_bytes','load_average_1m',
            'start_unix','cpu','attempts','reason_code','reason','polynomial_missing_reason']
    rows=[]
    for r in records:
        cid=r['id'];candidate=m['records'][cid];p=r.get('power',{});q=r.get('rabinowitsch',{})
        verified=[name for name,obj in [('power',p),('rabinowitsch',q)] if obj.get('independent_verification')=='verified']
        row={k:r.get(k,'') for k in fields if k in r}
        row.update(group='unseen29',source_group='a' if cid.startswith('AIME') else 'b',
                   polynomial_source=candidate.get('source',''),polynomial_source_sha256=candidate.get('source_sha256',''),
                   seed=candidate.get('seed',''),answer_count=candidate['answer_count'],category_ja=category(r),
                   polynomial=candidate.get('polynomial') or '',degree=candidate.get('degree') or '',
                   translated=(E/'runs'/(cid+'.work')/'translation.json').exists(),
                   independent_verification=','.join(verified) if verified else 'not_available' if r['status']=='nonmember' else 'not_verified',
                   power_status=p.get('status','not_run'),rabinowitsch_status=q.get('status','not_run'),
                   power_first_zero=p.get('first_zero_power',''),polynomial_missing_reason=candidate.get('polynomial_missing_reason') or '')
        example=E/'nonmembership-example.json'
        counterexample=(example.exists() and json.loads(example.read_text()).get('id')==cid and json.loads(example.read_text()).get('verified') is True)
        row['nonmembership_counterexample_verified']=counterexample
        if counterexample:
            row['independent_verification']='nonmembership_counterexample_verified'
        if not candidate['answer_count']:
            row.update(polynomial_source=';'.join(s['path'] for s in candidate['searched_solver_records']),
                       polynomial_source_sha256=';'.join(s['sha256'] for s in candidate['searched_solver_records']))
        for prefix,obj in [('power',p),('rabinowitsch',q)]:
            for key in ('basis_seconds','basis_size','certificate_seconds','verification_seconds','independent_verification'):
                row[prefix+'_'+key]=obj.get(key,'')
            row[prefix+'_nf_seconds']=obj.get('normal_form_seconds','')
        for key in ('load_average_1m','start_unix','cpu'):
            row[key]=r.get('start_receipt',{}).get(key,'')
        rows.append(row)
    with (E/'per-problem.csv').open('w') as f:
        w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)
    return m,records,rows

def report():
    m,records,rows=make_csv()
    official=judge.DEFAULT_STAGE
    provenance={'official_stageb_csv':str(official),'official_csv_exists':official.exists()}
    # The stageB manifest documents the external raw directory. Capture only
    # this cohort's existing output; never execute or modify the other campaign.
    if official.exists():
        stage,source=judge.load_stage(official)
    else:
        stage_manifest=official.parent/'pre-run-hashes.json'
        saved=json.loads(stage_manifest.read_text())
        directory=Path(saved['external_raw_directory'])/'unseen29'
        snapshot=E/'stageB-unseen29-snapshot.csv'
        judge.snapshot(directory,snapshot)
        stage,source=judge.load_stage(snapshot)
        provenance.update(fallback='stageB既存元JSONからの読み取り専用抽出',stageb_manifest_sha256=sha(stage_manifest))
    result=judge.judge(rows,stage)
    result.update(stageb_source=source,stageb_provenance=provenance,
                  certify_csv_sha256=sha(E/'per-problem.csv'),judge_script_sha256=sha(judge.__file__))
    write(E/'c3-c5.json',result)
    counts=Counter(r['category_ja'] for r in rows)
    cert=[r for r in rows if r['category_ja']=='認証']
    full=sum(r['category_ja']!='対象外：答えなし' for r in rows)
    converted=sum(r['translated'] for r in rows)
    times=[r['wall_seconds'] for r in cert]
    mid=median(times) if times else None
    c1='未判定' if not converted else '的中' if len(cert)/converted>=.5 else '外れ'
    c2='未判定' if mid is None else '的中' if mid<=2 else '外れ'
    loads=[r['load_average_1m'] for r in rows if r['load_average_1m']!='']
    audit={p:{'expected':h,'actual':sha(p),'matches':sha(p)==h} for p,h in m['hashes'].items()}
    assert all(x['matches'] for x in audit.values()),'FROZEN_CODE_OR_INPUT_CHANGED'
    ledgers=list((E/'runs').glob('*.work'))
    starts=sorted([json.loads((w/'start.json').read_text()) for w in ledgers],key=lambda r:r['start_unix'])
    expected=[cid for cid in m['order'] if m['records'][cid]['answer_count']]
    assert [s['id'] for s in starts]==expected,'ORDER_CHANGED'
    assert len(ledgers)==full==28 and sum(r.get('attempts',0) for r in records)==28
    assert len(set(s['cpu'] for s in starts))<=4
    for r in records:
        if r['status']!='no_answer':
            assert r['limits']['parallelism']==4 and r['limits']['threads']==1
    oversized=[str(p) for p in E.rglob('*') if p.is_file() and p.stat().st_size>2_900_000]
    assert not oversized,'ARTIFACT_SIZE_LIMIT'
    write(E/'post-run-audit.json',{'hashes':audit,'start_order_matches':True,'attempts':28,'retries':0,
                                 'ledger_count':len(ledgers),'no_answer_count':29-full,'oversized_files':oversized,
                                 'load_average_1m_range':[min(loads),max(loads)],
                                 'parallelism':4,'cpu_per_problem':1,'report_script_sha256':sha(__file__),
                                 'judge_script_sha256':sha(judge.__file__)})
    summary={'scope':'unseen29 only; development excluded','counts':dict(counts),'certified':len(cert),
             'listed':29,'eligible_including_conversion_failures':full,'recorded_minpoly_count':sum(bool(r['polynomial']) for r in rows),
             'translated':converted,'rate_all':len(cert)/full,'rate_translated':len(cert)/converted,
             'rate_listed29':len(cert)/29,'certified_median_seconds':mid,'C1':c1,'C2':c2,
             'C3':result['C3'],'C4':result['C4'],'C5':result['C5']}
    write(E/'summary-unseen29.json',summary)
    eq=result['C3']['strata']['equal'];extra=result['C3']['strata']['extra_irreducible_factors']
    def pct(x):return f'{x*100:.1f}%'
    def rate(s): return f'{s["certified"]}/{s["n"]} = {pct(s["rate"])}' if s['n'] else '該当なし、未判定'
    def sec(x): return f'{x:.3f}' if x is not None else '欠測'
    lines=['**開発外29問だけの判定。開発群323問とdev5は含まない。事前登録9全体の最終判定ではない。**','',
           '| 予測 | 今回の判定 | 観測 |','|---|---|---|',
           f'| C1：変換できた問題の認証率50%以上 | {c1} | {len(cert)}/{converted} = {pct(len(cert)/converted)} |',
           f'| C2：認証問題の全体時間中央値2秒以下 | {c2} | {sec(mid)}秒 |',
           f'| C3：同一式80%以上、余分な既約因子あり30%以下 | {result["C3"]["judgment"]} | 同一式 {rate(eq)}、余分な因子あり {rate(extra)} |',
           f'| C4：強化版で解けない認証問題5問以上 | {result["C4"]["judgment"]} | {result["C4"]["certified_not_solved"]}問 |',
           f'| C5：同じ認証問題でcertifyの時間中央値が短い | {result["C5"]["judgment"]} | {result["C5"]["paired_n"]}問、certify {sec(result["C5"]["certify_median_seconds"])}秒、強化版 {sec(result["C5"]["strong_median_seconds"])}秒 |','',
           f'指定29問を確認し、答えなし1問を別枠として、28問を各1回実行した。認証は{len(cert)}問。再試行・対象交換・p(T)の代用は0。','',
           '| 区分 | 件数 |','|---|---:|']
    for cat in ['認証','非所属','変換不能','時間上限','資源上限','実装エラー','検算不能','対象外：答えなし']:
        lines.append(f'| {cat} | {counts[cat]} |')
    lines += ['',f'認証率は、答えなしを除いた全対象で **{len(cert)}/{full} = {pct(len(cert)/full)}**、変換できた問題で **{len(cert)}/{converted} = {pct(len(cert)/converted)}**。指定リスト29問をそのまま母数にした参考値は {len(cert)}/29 = {pct(len(cert)/29)}。時間上限は変換済みの母数に残した。', '',
              'AIME-2014-II-10はseed 301〜305の全てで答えなし。HMMT-2015-FEB-GUTS-24は301に答えがなく302を採用した。他は301。答えあり28問は全て答え1個で、複数答えの積を使う実例はなかった。πを含む4問は答え自体に最小多項式がなく、係数の多項式で代用しなかった。これらも除外せず、元入力の変換不能として数えた。p(T)を取得できたのは24問。','',
              '非所属の例：HMMT-2013-FEB-GUTS-01の保存された答えは93、p(T)=T−93。一方、変換後にはT²−93²=0が残り、T=−93の枝も許す。元の距離は非負だが、二乗した等式だけではその枝を除けない。[元等式への反例の代入検算](nonmembership-example.json)でも、元等式と非零条件を満たしながらp≠0を確認した。したがって、この非所属をsolverの誤答とは扱わない。他の非所属も誤答とは断定しない。','',
              '認証は、元の等式・非零条件からp(T)=0が従うことだけを示す。Jが非単位、Rab法で所属、べき法と無矛盾、少なくとも一方の証明書の独立検算を全て要求した。実図の存在・一意性、答え集合の完全性の証明ではない。非所属一般の独立証明書検算は未実装で、上の例だけは別途具体的な反例を代入確認した。','',
              f'条件は600秒・8 GiB・1 CPU/問・4並列。IDのSHA-256昇順に開始した。各開始時の1分load averageは{min(loads):.2f}〜{max(loads):.2f}。全体時間は起動・変換・飽和・基底・正規形・証明書・独立検算を含む壁時間で、他作業の負荷付きの参考値。Singular内の区間時間は1ms単位で、0.000は処理なしを意味しない。C2/C5の数値判定はそのまま示すが、速度の一般的な優位とは解釈しない。','']
    if counts['時間上限']:
        for r in records:
            if r['status']=='timeout':
                lines.append(f'{r["id"]}は{r["wall_seconds"]:.3f}秒で時間上限。直近段階は `{r.get("stage")}` / `{r.get("last_algebra_event")}`。部分的なマーカーを認証や非所属に数えていない。')
        lines.append('')
    if official.exists():
        lines.append('C3〜C5はstageB/per-problem.csvをIDで結合し、同CSVの元JSON参照から既存の消去式を取得した。')
    else:
        lines.append('stageB/per-problem.csvは集計時に未作成だったため、stageBの事前manifestが示す既存開発外29問の元JSONを読み取り専用で抽出し、[比較用CSV](stageB-unseen29-snapshot.csv)をIDで結合した。元JSONのSHA-256は同名provenance.jsonに保存。新たな求解・消去や他タスクの変更はしていない。C3は式のない問題を同一式・余分因子群に入れず、C4/C5は該当する既存区分・時間で判定した。')
    lines += [f'C3の式比較は同一式{eq["n"]}問と余分な既約因子あり{extra["n"]}問。消去式またはp(T)がない残り{len(result["C3"]["missing_or_unclassified"])}問の式比較は未判定であり、これらをどちらの条件付き認証率にも混ぜていない。', '', '`verified_complete` と `direct_verified` だけを強化版の「解けた」とし、`verified_subset`は含めない。C3は定数倍を除いて比較し、pで割り切れて新しい既約因子がある場合を「余分な因子あり」とした。[判定詳細](c3-c5.json)と[判定スクリプト](judge_c3_c5.py)。境界値・欠測・部分解・時間同値の合成チェックは通過した。','',
              '前回停止記録は[stopped-first-attempt/answer.md](stopped-first-attempt/answer.md)ほか2点に保存し、元のanswer.mdとsource-search.jsonは保持した。今回のHMMT-2011と合成入力の確認は[pre-eval-check.md](pre-eval-check.md)に別掲し、評価に混ぜていない。certify.py・verify_certificate.py・翻訳器は変更なし。追加した外部実行器を実行前に固定し、終了後も全ハッシュ一致を確認した。','',
              '[問題別CSV](per-problem.csv)、[実行前ハッシュと候補出典](pre-run-hashes.json)、[終了時監査](post-run-audit.json)、[進捗](progress.md)。各成果物は2,900,000 byte以下。システム導入・昇格・commit/pushなし。開発群は元JSONが揃った後の別タスクに残す。','']
    (E/'answer-unseen29.md').write_text('\n'.join(lines))
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__': report()
