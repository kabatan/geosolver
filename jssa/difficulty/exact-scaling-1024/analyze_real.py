"""Descriptive analysis of saved degrees and historic timing; no solving."""
from collections import Counter, defaultdict
import csv
import json
import math
import os
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
os.environ['MPLCONFIGDIR'] = '/tmp/exact-scaling-1024-matplotlib'
os.environ['OPENBLAS_NUM_THREADS'] = '1'
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def read_rows():
    rows = list(csv.DictReader((HERE / 'real-problems.csv').open()))
    # Keep missing saved runs separate from recorded non-correct runs.
    root = HERE.parents[2]
    source_cache = {}
    for r in rows:
        source = r['solver_source']
        if source not in source_cache:
            grouped = defaultdict(list)
            for sample in csv.DictReader((root/source).open()):
                grouped[sample['case_id']].append(sample)
            source_cache[source] = grouped
        saved = source_cache[source][r['problem_id']]
        missing = [s for s in saved if s.get('record_missing', s.get('missing_record', 'False')) == 'True']
        r['solver_missing_count'] = len(missing)
        r['solver_recorded_count'] = len(saved)-len(missing)
        r['solver_confirmed_noncorrect_count'] = sum(s['matched'] != 'True' for s in saved)-len(missing)
        r['solver_missing_seeds'] = ';'.join(s['seed'] for s in missing)
    csv_write(HERE/'real-problems.csv', rows)
    for r in rows:
        for k in ['depth', 'point_depth', 'target_dependency_depth', 'n_constructions',
                  'dsl_variables', 'solver_runs', 'solver_correct']:
            r[k] = int(r[k])
        for k in ['solver_correct_seconds_median', 'solver_all_seconds_median', 'msolve_seconds',
                  'base_degree', 'base_dimension', 'strong_degree', 'strong_dimension']:
            r[k] = float(r[k]) if r[k] != '' else None
    return rows


def med(xs):
    return statistics.median(xs) if xs else None


def fmt(x, digits=3):
    if x is None or x == '':
        return '—'
    if isinstance(x, str):
        return x.replace('|', '/')
    return str(int(x)) if float(x).is_integer() else f'{x:.{digits}g}'


def span(xs):
    return f'{fmt(med(xs))} [{fmt(min(xs))}, {fmt(max(xs))}]' if xs else '—'


def finite(r, mode):
    return r[mode+'_dimension'] == 0 and r[mode+'_degree'] is not None and r[mode+'_degree'] > 0


def csv_write(path, rows):
    if not rows:
        Path(path).write_text('no_rows\n')
        return
    with Path(path).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def fit(rows, xkey, ykey, log2=False):
    pairs = [(float(r[xkey]), float(r[ykey])) for r in rows if r[ykey] is not None
             and (not log2 or r[ykey] > 0)]
    if len(pairs) < 2 or len(set(x for x, _ in pairs)) < 2:
        return dict(n=len(pairs), slope=None, intercept=None, r2=None)
    x, y = np.array(pairs).T
    if log2:
        y = np.log2(y)
    slope, intercept = np.polyfit(x, y, 1)
    residual = ((y - (slope*x + intercept))**2).sum()
    total = ((y-y.mean())**2).sum()
    return dict(n=len(pairs), slope=float(slope), intercept=float(intercept),
                r2=float(1-residual/total) if total else None)


def table(header, rows):
    return ['|'+'|'.join(header)+'|', '|'+'|'.join(['---']*len(header))+'|'] + [
        '|'+'|'.join(fmt(x) for x in r)+'|' for r in rows]


def main():
    rows = read_rows()
    assert len(rows) == 357
    assert not any(r['base_status'] == 'PENDING' or r['strong_status'] == 'PENDING' for r in rows)
    summaries, regressions, failures, missing, mismatch = [], [], [], [], []
    for group in ['all', 'dev323', 'unseen34']:
        rr = rows if group == 'all' else [r for r in rows if r['group'] == group]
        for mode in ['base', 'strong']:
            for depth in sorted({r['depth'] for r in rr}):
                dd = [r for r in rr if r['depth'] == depth]
                zs = [r[mode+'_degree'] for r in dd if finite(r, mode)]
                ps = [r[mode+'_degree'] for r in dd if (r[mode+'_dimension'] or 0) > 0]
                summaries.append(dict(group=group, mode=mode, depth=depth, n=len(dd),
                                      zero_dimensional=len(zs), degree_median=med(zs),
                                      degree_min=min(zs) if zs else None, degree_max=max(zs) if zs else None,
                                      positive_dimensional=len(ps), positive_degree_median=med(ps),
                                      positive_degree_min=min(ps) if ps else None,
                                      positive_degree_max=max(ps) if ps else None,
                                      unknown=sum(r[mode+'_degree'] is None for r in dd),
                                      empty=sum(r[mode+'_dimension'] == -1 for r in dd)))
            for xkey in ['depth', 'point_depth', 'target_dependency_depth']:
                fitrows = [r for r in rr if finite(r, mode)]
                regressions.append(dict(group=group, quantity=mode+'_log2_degree', x=xkey,
                                        **fit(fitrows, xkey, mode+'_degree', True)))
        for transform in [False, True]:
            regressions.append(dict(group=group, quantity='solver_'+('log2_seconds' if transform else 'seconds'),
                                    x='depth', **fit(rr, 'depth', 'solver_correct_seconds_median', transform)))
        for cat in sorted({r['msolve_category'] for r in rr}):
            cc = [r for r in rr if r['msolve_category'] == cat]
            zz = [r['base_degree'] for r in cc if finite(r, 'base')]
            pp = [r['base_degree'] for r in cc if (r['base_dimension'] or 0) > 0]
            failures.append(dict(group=group, msolve_category=cat, n=len(cc),
                                 depth_median=med([r['depth'] for r in cc]),
                                 depth_min=min(r['depth'] for r in cc), depth_max=max(r['depth'] for r in cc),
                                 zero_dimensional=len(zz), zero_degree_median=med(zz),
                                 zero_degree_min=min(zz) if zz else None, zero_degree_max=max(zz) if zz else None,
                                 positive_dimensional=len(pp), positive_degree_median=med(pp),
                                 unknown=sum(r['base_degree'] is None for r in cc),
                                 solver_any_correct=sum(r['solver_correct'] > 0 for r in cc)))
    for r in rows:
        for mode in ['base', 'strong']:
            if r[mode+'_degree'] is None:
                missing.append(dict(problem_id=r['problem_id'], group=r['group'], mode=mode,
                                    status=r[mode+'_status'], reason=r[mode+'_reason'], detail=r[mode+'_detail']))
        if r['msolve_seconds'] is None:
            missing.append(dict(problem_id=r['problem_id'], group=r['group'], mode='historic_msolve_time',
                                status=r['msolve_category'], reason=r['msolve_reason'], detail='No numeric solve time in source'))
        if r['solver_correct_seconds_median'] is None:
            missing.append(dict(problem_id=r['problem_id'], group=r['group'], mode='historic_solver_correct_time',
                                status=r['solver_result'], reason='No successful seed', detail='Failures excluded from success-time median'))
        if r['solver_missing_count']:
            missing.append(dict(problem_id=r['problem_id'], group=r['group'], mode='historic_solver_run',
                                status='RECORD_MISSING', reason='process_crash',
                                detail='missing seeds: '+r['solver_missing_seeds']))
        for key, old in [('nvars', 'msolve_historic_nvars'), ('neqs', 'msolve_historic_neqs')]:
            if r['base_'+key] and r[old] and int(r['base_'+key]) != int(r[old]):
                mismatch.append(dict(problem_id=r['problem_id'], field=key, now=r['base_'+key], historic=r[old]))
    csv_write(HERE/'depth-distribution.csv', summaries)
    csv_write(HERE/'regressions.csv', regressions)
    csv_write(HERE/'msolve-profile.csv', failures)
    csv_write(HERE/'missing.csv', missing)
    csv_write(HERE/'historic-system-size-check.csv', mismatch)
    fast = sorted([r for r in rows if finite(r, 'base') and r['solver_correct_seconds_median'] is not None
                   and r['solver_correct_seconds_median'] <= 10],
                  key=lambda r: (-r['base_degree'], r['solver_correct_seconds_median'], r['problem_id']))[:10]
    reverse = sorted([r for r in rows if finite(r, 'base') and r['solver_confirmed_noncorrect_count'] > 0],
                     key=lambda r: (r['base_degree'], r['solver_correct']/r['solver_runs'], r['problem_id']))
    example_keys = ['problem_id', 'group', 'depth', 'base_dimension', 'base_degree', 'strong_degree',
                    'solver_correct', 'solver_runs', 'solver_correct_seconds_median',
                    'solver_all_seconds_median', 'msolve_category', 'msolve_seconds']
    csv_write(HERE/'high-degree-fast.csv', [{k:r[k] for k in example_keys} for r in fast])
    csv_write(HERE/'low-degree-failures.csv', [{k:r[k] for k in example_keys} for r in reverse])

    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2), constrained_layout=True)
    colors = {'dev323': '#24649a', 'unseen34': '#df7041'}
    for i, mode in enumerate(['base', 'strong']):
        ax = axes[i]
        for group in colors:
            zz = [r for r in rows if r['group'] == group and finite(r, mode)]
            # Deterministic small jitter separates overlaid observations; regression uses integer depth.
            jitter = np.linspace(-.10, .10, len(zz)) if zz else []
            ax.scatter([r['depth']+j for r,j in zip(zz,jitter)], [math.log2(r[mode+'_degree']) for r in zz],
                       s=24, alpha=.6, color=colors[group], label=f'{group} (n={len(zz)})',
                       marker='o' if group == 'dev323' else '^')
        reg = next(r for r in regressions if r['group']=='all' and r['x']=='depth'
                   and r['quantity']==mode+'_log2_degree')
        xx = np.array([0, max(r['depth'] for r in rows)])
        ax.plot(xx, reg['slope']*xx+reg['intercept'], color='#222222', lw=1.5,
                label=f'OLS slope={reg["slope"]:.3f}; R2={reg["r2"]:.3f}')
        ax.plot(xx, xx, '--', color='#8b8b8b', lw=1, label='D = 2^depth (reference)')
        ax.set_title(('Original encoding' if mode=='base' else 'Strong, saturated + target')+'\nZero-dimensional ideals only')
        ax.set(xlabel='Named-construction depth', ylabel='log2(ideal degree), with multiplicity')
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(alpha=.17)
    ax = axes[2]
    for group in colors:
        rr = [r for r in rows if r['group']==group and r['solver_correct_seconds_median'] is not None]
        jitter = np.linspace(-.10, .10, len(rr))
        ax.scatter([r['depth']+j for r,j in zip(rr,jitter)], [r['solver_correct_seconds_median'] for r in rr],
                   s=24, alpha=.55, color=colors[group], label=f'{group} (n={len(rr)})',
                   marker='o' if group=='dev323' else '^')
    dd = sorted({r['depth'] for r in rows})
    mm = [med([r['solver_correct_seconds_median'] for r in rows if r['depth']==d
               and r['solver_correct_seconds_median'] is not None]) for d in dd]
    ax.plot(dd, mm, 'D-', color='#222222', lw=1, markersize=4, label='Median across problems')
    ax.set_yscale('log')
    ax.set(xlabel='Named-construction depth', ylabel='Historical solver seconds (log scale)')
    ax.set_title('Median of successful seeds per problem\nFailures omitted; historical run conditions differ')
    ax.legend(fontsize=8)
    ax.grid(alpha=.17)
    fig.suptitle('357 real problems: descriptive associations, not causal scaling estimates', fontsize=14)
    fig.savefig(HERE/'degree-vs-depth.png', dpi=150)
    plt.close(fig)

    both = [r for r in rows if finite(r,'base') and finite(r,'strong')]
    comparison = Counter('lower' if r['strong_degree'] < r['base_degree'] else
                         'higher' if r['strong_degree'] > r['base_degree'] else 'equal' for r in both)
    summary = dict(n=len(rows), groups=dict(Counter(r['group'] for r in rows)),
                   base_status=dict(Counter(r['base_status'] for r in rows)),
                   strong_status=dict(Counter(r['strong_status'] for r in rows)),
                   paired_zero_dimensional=len(both), strong_degree_comparison=dict(comparison),
                   historic_system_size_mismatches=mismatch,
                   omitted_variables=[r['problem_id'] for r in rows if r['base_omitted_dsl_variables']],
                   regressions=regressions)
    (HERE/'real-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    reg = lambda group, quantity, x='depth': next(r for r in regressions if r['group']==group
                                                 and r['quantity']==quantity and r['x']==x)
    b, s, timing = reg('all','base_log2_degree'), reg('all','strong_log2_degree'), reg('all','solver_seconds')
    lines = ['# 実問題の次数と作図の深さ', '',
             f'全357問（開発323、開発外34）を収録した。既存系の零次元次数が分かったのは{b["n"]}問、'
             f'強化系は{s["n"]}問。正次元で次元と次数を得たのは既存61問、強化31問で、次数不明はそれぞれ56問・101問。'
             '次数は重複度込みで、相異なる複素解の個数とは限らない。'
             '主な観測は、既存系の `log2(次数) = a + b×深さ` の傾き '
             f'**{fmt(b["slope"])}**（R²={fmt(b["r2"])}）、強化系は **{fmt(s["slope"])}**（R²={fmt(s["r2"])}）だった。'
             '深さだけから次数≈2^kを一般に説明できるとは言えない。以下は観測の記述であり、予測の固定・修正は行っていない。', '',
             '深さ別の次数は次の通り。中央値 [最小, 最大]。零次元だけを集計し、正次元の次数を混ぜない。', '']
    distrows = []
    for d in sorted({r['depth'] for r in rows}):
        rr = [r for r in rows if r['depth']==d]
        distrows.append([d,len(rr),sum(finite(r,'base') for r in rr),span([r['base_degree'] for r in rr if finite(r,'base')]),
                         sum((r['base_dimension'] or 0)>0 for r in rr),sum(r['base_degree'] is None for r in rr),
                         sum(finite(r,'strong') for r in rr),span([r['strong_degree'] for r in rr if finite(r,'strong')])])
    lines += table(['深さ','全問','既存・零次元n','既存次数','既存・正次元n','既存・不明n','強化・零次元n','強化次数'],distrows)
    lines += ['', '群別・正次元の次数分布も [depth-distribution.csv](depth-distribution.csv) に収録。', '',
              '![次数・深さ・solver時間](degree-vs-depth.png)', '',
              '回帰の傾きは**問題の種類・自由変数数・条件数・DSLの書き方による交絡がある参考値**。'
              '次数未判明の難しい系を除いた選択もある。深さ12は1問だけで、深さ7〜11の観測はない。'
              '傾き1や傾き0の検定、因果関係の推定はしていない。', '']
    regtab=[]
    for g in ['dev323','unseen34','all']:
        for q in ['base_log2_degree','strong_log2_degree','solver_seconds','solver_log2_seconds']:
            z=reg(g,q); regtab.append([g,q,z['n'],z['slope'],z['intercept'],z['r2']])
    lines += table(['群','縦軸','n','傾き','切片','R²'], regtab)
    lines += ['', f'solverの秒数を直接回帰すると1段当たり {fmt(timing["slope"])} 秒、R²={fmt(timing["r2"])}。'
              '正解seedの時間中央値だけの関係なので、時間切れ・不正解は0秒とせず除外した。'
              'これだけで「1本の枝をたどり、時間が深さに比例する」とは結論できない。'
              '既存BASE相当solverには代数的前処理、多点出発、第2探索、rescueが含まれる。', '',
              '深さを点の生成だけで数える補助定義では、既存次数の傾きは '
              f'{fmt(reg("all","base_log2_degree","point_depth")["slope"])}、'
              'targetが直接参照する作図の最大深さでは '
              f'{fmt(reg("all","base_log2_degree","target_dependency_depth")["slope"])}。'
              '[全回帰値](regressions.csv)。定義による差も、深さが入力表現に依存することを示す。', '',
              '## 既存msolveの失敗・時間切れ', '',
              '過去の結果区分をそのまま集計した。`error`を全てメモリ超過と決めつけない。'
              '`no_unknowns`は求解器失敗と同義ではなく、既存変換が未知数を残さなかった区分。'
              '次表の次数は今回計算できた既存系の零次元分だけ。', '']
    fr=[]
    for f in failures:
        if f['group']=='all':
            fr.append([f['msolve_category'],f['n'],f'{fmt(f["depth_median"])} [{f["depth_min"]}, {f["depth_max"]}]',
                       f['zero_dimensional'],f'{fmt(f["zero_degree_median"])} [{fmt(f["zero_degree_min"])}, {fmt(f["zero_degree_max"])}]' if f['zero_dimensional'] else '—',
                       f['positive_dimensional'],f['unknown']])
    lines += table(['msolve結果','n','深さ 中央値 [範囲]','零次元n','次数 中央値 [範囲]','正次元n','次数不明n'],fr)
    lines += ['', '開発群の時間切れ9問のうち、次数が判明した3問は2384〜46656（中央値18432）、深さ0〜3。'
              '開発外の時間切れ1問は次数1024・深さ1だった。高次数でも浅いDSLが含まれる。'
              '開発群の`error`15問は今回も全て次数不明なので、大次数だとは判定できない。'
              '旧READMEの「有限でない68問」は、元CSVでは`positive_dimensional`65問と`free_parameter`3問に分かれる。']
    lines += ['', '時間切れ群の次数不明を大次数と置換しない。有限でない群は有限解の列挙とは課題が違う。'
              '正次元でもTが有限個に決まることがあり、全配置の次数とTの最小多項式次数は別物である。'
              '[群別の詳細](msolve-profile.csv)。', '',
              '## 大きい次数を速く解いた例と逆の例', '',
              '「速い」は既存の正解seed中央値10秒以下とした表示上の基準。次数降順、同次数は時間昇順の上位10問。'
              'この例示基準は予測や仮説検定には使わない。', '']
    lines += table(['問題ID','群','深さ','既存次数','強化次数','正解/seed','正解秒中央値'],[
        [r['problem_id'],r['group'],r['depth'],r['base_degree'],r['strong_degree'],
         f'{r["solver_correct"]}/{r["solver_runs"]}',r['solver_correct_seconds_median']] for r in fast])
    lines += ['', '最大の例HMMT-2010-FEB-GEO-01（次数46656、深さ0）はDSL自由変数0で、'
              '七角形の頂点をsin/cos定数で直接置く問題。既存変換は6組の三角定数をそれぞれ代数化し、'
              '共役・符号の選択を独立に残すため6^6=46656になる。'
              'solverは固定配置の直接評価を使える。これは表現による候補増加の例であり、'
              '46656個の本来の図を1本の探索で処理した証拠ではない。'
              '七角形の三角定数のような、平方根だけでない代数拡大もこの実問題群には含まれる。']
    lines += ['', '次は既存次数16以下で、少なくとも1seedで正解しなかった記録がある例。'
              '部分失敗と全seed失敗を区別する。正解時間「—」は全seed失敗であり0秒ではない。', '']
    lines += table(['問題ID','深さ','既存次数','正解/seed','正解秒中央値','全seed秒中央値'],[
        [r['problem_id'],r['depth'],r['base_degree'],f'{r["solver_correct"]}/{r["solver_runs"]}',
         r['solver_correct_seconds_median'],r['solver_all_seconds_median']] for r in reverse if r['base_degree']<=16])
    lines += ['', '次数の大小に関係なく、次数が判明した記録済み失敗の全一覧は '
              '[low-degree-failures.csv](low-degree-failures.csv) に残した。']
    lines += ['', '## 強化版について', '',
              f'両方が零次元で次数判明の{len(both)}問では、強化系の次数は低下{comparison["lower"]}問、'
              f'同じ{comparison["equal"]}問、増加{comparison["higher"]}問。'
              '「R1〜R4でも次数そのものは減らせない」という一般論は、この表とは合わない。'
              'ただし既存系はTなし・Rabinowitsch変数付き、強化系はT付き・飽和済みであり、表現と対象が完全には同一でない。', '',
              '具体例AIME-2001-I-05は深さ0、既存次数8、強化次数4。'
              'DSLの厳密不等式 x>0、y<1 が与える x≠0、y−1≠0 による飽和で退化成分が除かれる。'
              'この例のTは既存の距離補助変数と線形に同定されるので、T追加だけでは倍増しない。'
              '逆に新しい距離・根号をtargetに追加すると符号分岐が増える。'
              '高次の系でもTへの射影の次数は小さい場合があるため、全系の次数と出力の次数を同一視しない。', '',
              '## 方法・出典・欠測', '',
              '1. `benchmarks/cases.jsonl` の323問と `unseen-2/{a,b}/cases.jsonl` の17+17問を全数使用。'
              '各ケースの内包DSLと `dsl_path` のJSONが一致することを確認。群の入替え・難易度による除外なし。',
              '2. 既存系は `/tmp/q6-tools/exact_comparison/benchmarks/exact_comparison/algebraize.py` の '
              '`translate(mode="fresh",with_target=False)` と既存 `run_exact.build(rabinowitsch=True)` を無変更で使用。'
              '`origin/claude/project-thread-fos2rk` の変換器とSHA-256が一致する。等式で使う変数を残し、既存の分母因子の積に補助変数zzを付ける。',
              '3. 強化系は無変更の `strong_translate.translate` と `run_strong.prepare`。Tを追加し、R2の各非零因子で順に `sat`。'
              '今回はそのイデアルの次数を測った。R1のTへの射影・実根列挙・復元・検証を実問題では実行していない。'
              'R3の代数定数も変換器どおり。R4の「DSL未知数0なら直接評価」は求解手順であってイデアルの定義ではないので、'
              '直接評価器を呼ばず変換された系の次数を記録した。強化パイプライン全体の成功率・時間とは異なる。',
              '4. 有理数体・次数逆辞書式順序で `G=std(J)`、`dim(G)`、`mult(G)` を計算。'
              '零次元では `vdim(G)` と一致する重複度込みの次数。異なる複素点の個数は非被約ならこれより少ない。'
              '正次元は有限個の解数ではなく、最高次元成分の重複度込みの次数。空イデアルは次元−1・次数0で別扱い。'
              '正次元で補助変数やTを加えると、同じ幾何を表す場合も埋込みの次数は変わり得る。',
              '5. 深さkは**名前付き作図命令の依存DAGの最大段数**。定数・自由パラメータは0。'
              '他の作図名を参照しない `Point` と自由パラメータの単なる別名は0。その他の名前付き出力は、'
              '式中で参照する先行作図名の最大深さ+1（参照なしは1）。点・直線・円・スカラーを含む。'
              '匿名の入れ子は独立ノードにせず、条件・targetを加算しない。作図が条件だけに書かれたDSLは深さ0でも高次数になり得る。'
              '依存抽出はPython AST、`expand_k.py` とDSLパーサの式形式を参照。各ノードの証跡は `depths/`。',
              '6. 補助列 `point_depth` は点を返す名前付き命令だけを+1し、線・円・スカラーは依存深さを伝播する。'
              '`target_dependency_depth` はtargetが参照する作図名の最大の主深さ。主定義の結果をこの定義に差し替えていない。',
              '7. Singular 4.4.1をPATH先頭 `/tmp/q6-tools/bin` で使用。1系30秒、1問の2系合計最大60秒、最大4並列。'
              '変換は1系20秒、各子プロセスの仮想メモリ2 GiB、1ファイル2,900,000 byteを上限とした。'
              'ログの次数計算時間は予算管理用で、時間比較には使用しない。再試行・新規msolve時間測定・solver実行なし。', '',
              '既存時間の参照は次の通り（CSV各行にもパス・列名を収録）。', '',
              '- 開発外msolve: `capability-1024/exp1-msolve/per-problem.csv` の `msolve_solve_seconds`, `msolve_category`。'
              '`solve_seconds`と同じ求解部分であり、変換・検証を含む全体時間ではない。',
              '- 開発msolve: `jssa/strategy/astra-consult-18/Q24/source-msolve-cases.csv` の `msolve_s`, `msolve_class`。'
              '10/22、コードbranch `claude/project-thread-fos2rk` b0575a0。結果の元保存先は別branch '
              '`claude/project-thread-nycxfb` のc0bd76d、`jssa/results/exact-comparison-pc-20261022/aggregate/cases.csv`。'
              '現ローカルでは元commit/結果ツリーを参照できなかったが、保存コピーのGit blob SHA '
              '`2270f6bb7b6596e23c7ad0e9bfa37c0c5026d7b8` は既存来歴と一致した。'
              '探索した `git log --all` / `git ls-tree` / `git show` / `rg` の範囲は [provenance.json](provenance.json)。',
              '- 開発外solver: `unseen-2/a/per-run.csv` と `b/results.csv` の `matched` と `wall_seconds`。'
              'Q30、seed301〜305の正解数と、正解した実行だけの壁時間中央値。',
              '- 開発solver: `jssa/results/mechanism-attribution/attribution.csv` の `matched` と `wall_s`。'
              '凍結版本計測 `jssa-main-j6-20261022`、seed0〜2、BASE相当。全323×3行を使用。', '',
              '開発外HMMT-2015-FEB-GUTS-24のseed301は記録欠測（process_crash）。'
              '予定5seedの分母には含め、正解時間から除いた。`solver_missing_count` / `solver_missing_seeds` と '
              '`solver_confirmed_noncorrect_count` で欠測と記録済み不正解を分離した。', '',
              '開発群の旧msolveは1800秒・4並列・5 GiBで、別の難しさ実験も同時に動いていた。'
              'solver本計測は6並列。開発外msolveは600秒の記録。機械・同時負荷・上限・seed数が揃わないため、'
              'この表の秒数から厳密法とsolverの公平な速度倍率は出さない。', '',
              f'既存記録と今回変換の変数数・等式数の照合で差があるのは{len(mismatch)}項目。'
              '[照合表](historic-system-size-check.csv)。'
              f'今回確認できた範囲で、既存変換が等式から落としたDSL自由変数を持つのは{len(summary["omitted_variables"])}問。'
              '該当ID: '+(', '.join(summary['omitted_variables']) or 'なし')+'。'
              'その行の零次元次数は使用変数だけの系の値であり、元DSLの配置が有限である証拠ではない。', '',
              '次数不明は推測で補完していない。理由別件数は次の通り。全ID・詳細・既存時間の欠測も '
              '[missing.csv](missing.csv) に列挙した。正次元で次数が計算できたものは欠測ではない。', '']
    lines += table(['系','理由コード','件数'],[[m,c,n] for m in ['base','strong']
                 for c,n in sorted(Counter(r[m+'_status'] for r in rows if r[m+'_degree'] is None).items())])
    lines += ['', '`TRANSLATION_UNSUPPORTED`=命令/定数/target等が未対応、`TRANSLATION_TIMEOUT`=変換20秒超過、'
              '`DEGREE_TIMEOUT`=Singular30秒超過、`MEMORY_LIMIT`=2 GiB上限、'
              '`TRANSLATION_ERROR`=既存変換器の例外、`WORKER_LIMIT`=外側監視の終了、'
              '`ARTIFACT_SIZE_LIMIT`=2.9 MB上限、`TOTAL_BUDGET_LIMIT`=全体枠。'
              '出現していないコードの欠測が発生したと主張するものではない。', '',
              '次数・変数数・等式数は総次数の上界（Bézout積）ではなく、実際に計算したイデアルの量。'
              '不等式の符号、平方根の主値、実在、枝選択はこの複素系では完全には表さない。'
              '今回の観測は「全ての問題で2^k」「強化しても次数を下げられない」「solverは必ず線形時間」を裏付けない。'
              '一方、有限の平方根拡大が毎段独立に必要な特定の族では指数増加が起こり得る。この範囲を人工族で別に確かめる。', '',
              '<!-- FAMILIES -->',
              '## 人工族（補強）', '', '実問題表の保存と「実問題表完了」ログ後に補強を追記する。', '',
              '## 段階2（時間比較）の案', '',
              '各族の実測可能なk範囲と実行順は補強後に追記する。今回は時間比較を実行していない。', '']
    (HERE/'answer.md').write_text('\n'.join(lines))
    print(json.dumps({k:v for k,v in summary.items() if k!='regressions'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
