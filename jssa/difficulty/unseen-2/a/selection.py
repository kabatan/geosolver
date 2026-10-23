"""Offline census and exclusions. Decisions do not inspect solver results."""
from collections import Counter
from datetime import datetime,timezone
import csv
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]


def sha(data): return hashlib.sha256(data).hexdigest()
def rows(path): return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
def key(s): return '-'.join(str(int(t)) if t.isdigit() else {'I':'1','II':'2'}.get(t,t) for t in s.upper().split('-'))
def sortkey(s):
    _,y,p,n=s.split('-'); return (int(y),len(p),int(n))


def decisions():
    reasons={}
    def add(code,reason,ids):
        for cid in ids.split():
            assert cid not in reasons,cid
            reasons[cid]=(code,reason)
    add('not_planar_solid','立体・空間配置が原文の本質。平面への解法的還元で対象に入れない。','''
    AIME-2000-I-08 AIME-2000-II-12 AIME-2001-I-10 AIME-2001-I-12 AIME-2001-I-15
    AIME-2001-II-12 AIME-2001-II-15 AIME-2002-I-11 AIME-2002-I-15 AIME-2002-II-02
    AIME-2003-I-05 AIME-2003-I-06 AIME-2003-II-04 AIME-2003-II-05
    AIME-2004-I-03 AIME-2004-I-11 AIME-2004-I-14 AIME-2004-II-03 AIME-2004-II-11
    AIME-2005-I-09 AIME-2005-II-10 AIME-2010-I-11 AIME-2011-I-08 AIME-2011-I-13
    AIME-2012-I-08 AIME-2012-II-05 AIME-2013-I-07 AIME-2015-I-15 AIME-2015-II-09 AIME-2016-I-03
    AIME-2016-I-04 AIME-2016-II-14 AIME-2017-I-04 AIME-2017-II-15 AIME-2018-I-07''')
    add('intrinsic_integer','整数性・既約性が配置の尺度・形状の条件であり、出力形式だけではない。連続幾何量へ変えると原問題を変える。','''
    AIME-2000-I-04 AIME-2011-II-03''')
    add('configuration_or_lattice_count','図形・格子・経路・彩色の個数。1配置上の単一幾何量の求値ではない。','''
    AIME-2000-II-02 AIME-2001-II-05 AIME-2002-I-05 AIME-2004-I-08 AIME-2005-I-13
    AIME-2011-I-05 AIME-2013-II-09 AIME-2014-I-05 AIME-2016-I-14 AIME-2016-II-12
    AIME-2017-I-01 AIME-2017-II-13 AIME-2018-II-07 AIME-2018-II-08''')
    add('probability_or_expectation','確率・期待値の問題。図形を舞台としても有限配置の幾何量DSLではない。','''
    AIME-2001-II-09 AIME-2003-I-11 AIME-2003-II-13 AIME-2004-I-10 AIME-2010-II-02
    AIME-2010-II-04 AIME-2011-I-10 AIME-2013-I-04 AIME-2014-I-11 AIME-2015-II-05
    AIME-2016-I-13 AIME-2016-II-13 AIME-2017-I-06 AIME-2017-I-08 AIME-2017-II-03
    AIME-2019-I-05''')
    add('configuration_optimization','配置全体にわたる最大・最小の選別が必要。停留条件や最適な接触配置を解法からDSLへ注入しない。','''
    AIME-2004-I-09 AIME-2005-I-10 AIME-2005-I-11 AIME-2005-II-15
    AIME-2012-I-13 AIME-2012-II-06 AIME-2013-II-10 AIME-2014-I-07 AIME-2014-II-12
    AIME-2016-I-09 AIME-2017-I-15 AIME-2018-I-08 AIME-2018-I-13''')
    add('intrinsic_integer_optimization','整数条件を伴う最大・最小、整数配置全体の選別。整数変数を除去しても同じ問題にならない。','''
    AIME-2010-I-08 AIME-2010-II-12 AIME-2011-I-06 AIME-2015-I-11 AIME-2016-II-07 AIME-2019-I-11''')
    add('locus_or_infinite_regions','軌跡・到達可能領域・無限個の領域の面積。境界や有限和を解法から決め打ちしない。','''
    AIME-2000-I-13 AIME-2004-I-04 AIME-2004-I-12 AIME-2015-I-14''')
    add('infinite_construction','無限回の幾何構成または無限和が本質。極限の式を解法としてDSLへ入れない。','''
    AIME-2013-I-13 AIME-2016-II-05 AIME-2017-II-12''')
    add('missing_figure','本文はn=5の図の配置に依存。保存HTMLには外部GIFの参照とファイル名だけで画像本体・配置情報がない。記憶で補完しない。','AIME-2002-II-04')
    add('unsupported_exact_answer_type','目標の面積比はpiを含む分母を持つ。既存の代数的実数/一次pi型では表現できず、既存厳密集合採点を変更せず使えない。','AIME-2004-II-01')
    add('unsupported_exact_answer_type','目標の周長は対数の和。既存の代数的実数/一次pi型では表現できない。logの指数をtargetにして出力形式へすり替えない。','AIME-2015-II-04')
    add('multi_quantity_ratio','求める比は長辺:短辺:Dから角への距離の3成分。単一スカラーの生の幾何量という今回の規則では扱わない。p+q+rをtargetにせず、1つの比から残りを解法で復元する採点も導入しない。','AIME-2012-II-04')
    add('not_geometry_rate_problem','一直線上の速さ・出会い・所要時間の算数が主題。平面図形の計量や配置の問題としては採用しない。','AIME-2014-I-04 AIME-2018-II-01')
    add('graph_combinatorics','円はグラフの節点・経路の図示。ネットワーク上の流量や歩道数が主題で、平面の幾何量ではない。','AIME-2012-I-07 AIME-2018-I-10')
    add('fold_order_combinatorics','繰り返し折った紙の積層順位が主題。1配置の長さ・面積等の幾何量ではない。','AIME-2004-II-15')
    return reasons


def main():
    assert not (HERE/'prediction.lock.json').exists()
    sources=rows(HERE/'source-evidence/statements.jsonl')
    source_by_id={r['id']:r for r in sources}
    expected=[f'AIME-{y}-{p}-{n:02}' for y in list(range(2000,2006))+list(range(2010,2020)) for p in ['I','II'] for n in range(1,16)]
    assert len(expected)==480 and set(expected)==set(source_by_id)
    cases=rows(HERE/'cases.jsonl'); adopted={r['id'] for r in cases}
    audit=json.loads((HERE/'audit/validation.json').read_text()); assert audit['passed'] and audit['cases']==len(cases)
    old={}
    for label,path in [('development323','benchmarks/cases.jsonl'),('new2026','jssa/difficulty/new2026/cases.jsonl'),('unseen1983','jssa/difficulty/unseen-1983/cases.jsonl')]:
        for r in rows(ROOT/path): old.setdefault(key(r['id']),[]).append(dict(group=label,id=r['id']))
    reasons=decisions(); assert set(reasons)<=set(expected)
    assert not adopted & set(reasons)
    decisions_rows=[]
    for cid in expected:
        s=source_by_id[cid]
        if key(cid) in old:
            status='duplicate'; code='normalized_source_id'; reason='既存の'+', '.join(r['group']+':'+r['id'] for r in old[key(cid)])+'と同じ原問題。'
        elif cid in adopted:
            status='adopted'; code='audited_direct_planar_value'; reason='原文・Answer Key・DSL・正解図代入・出力変換の監査合格。'
        elif cid in reasons:
            status='excluded'; code,reason=reasons[cid]
        else:
            status='excluded'; code='not_geometry'; reason='主題は整数・代数・数列・確率・組合せ等で、有限平面配置上の単一幾何量の求値ではない。'
        decisions_rows.append(dict(id=cid,status=status,reason_code=code,reason=reason,
                                   source_file=s['source_file'],source_sha256=s['source_sha256'],
                                   source_line=s['line'],statement_sha256=sha(s['text'].encode())))
    # Independent keyword triage is an audit aid, never the selection decision.
    manifest=dict(schema_version=1,created_at_utc=datetime.now(timezone.utc).isoformat(),
                  universe='AIME I/II 2000–2005 and 2010–2019, all 480 slots',
                  selection_order='year, I before II, problem number',requested_count=[15,20],
                  selected_count=len(cases),selected_ids=sorted(adopted,key=sortkey),
                  count_stop='全480スロットを確認。既存重複・主題・表現/採点制約による除外後の監査合格17問を全件採用。20に埋めるための規則緩和なし。',
                  status_counts=dict(Counter(r['status'] for r in decisions_rows)),
                  reason_counts=dict(Counter(r['reason_code'] for r in decisions_rows)),
                  source_html_count=64,complete_problem_sections=480,
                  selection_used_solver_results=False,solver_run=False,rows=decisions_rows)
    (HERE/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    with (HERE/'audit/selection.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(decisions_rows[0])); writer.writeheader();writer.writerows(decisions_rows)
    report=['# Q30a 採否台帳','',manifest['count_stop'],'','全480問の理由は `selection.csv` と `../manifest.json`。キーワード検索だけで採否を決めず、境界事例は原文を読んで下表の理由を記録。',
            '', '## 幾何に関係するが採用しなかった未使用問題','', '| 問題 | 理由 |','|---|---|']
    for r in decisions_rows:
        if r['status']=='excluded' and r['reason_code']!='not_geometry': report.append(f'| {r["id"]} | {r["reason"]} |')
    report+=['','## 境界事例','',
             '- AIME-2003-I-02は100個の指定円の有限面積和。未知変数がないことを理由に除外しない。',
             '- AIME-2014-I-01は固定された6斜線と1横線の長さに、原文が指定する両端の最低余長200ずつを足す。配置の最適化を解いて接触条件を注入する問題とは区別した。',
             '- AIME-2014-I-10は指定された最初の1回転での有限配置。滑りなしの転がりの定義から弧長の等式を記述した。',
             '- 複素数の問題は原文が実際に三角形・多角形を指定する2012-I-14, 2014-II-10, 2019-I-12を採用。複素代数だけの問題は採用しない。',
             '- 最大最小・個数・確率・本質的整数条件・無限過程はユーザーの規則を満たす求値問題へ解法で置き換えない。',
             '- 上記は未実行時点の手動の主題/表現判定であり、全AIMEの唯一の分類体系という主張ではない。','']
    (HERE/'audit/selection.md').write_text('\n'.join(report))
    print(json.dumps({k:manifest[k] for k in ['selected_count','status_counts','reason_counts']},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
