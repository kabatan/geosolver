import csv,json,pathlib
P=pathlib.Path(__file__).resolve().parent
s=json.loads((P/'summary.json').read_text());pre=json.loads((P/'preflight.json').read_text());ex=json.loads((P/'execution.json').read_text());rows=list(csv.DictReader((P/'per-problem.csv').open()))
def verdict(v):return '的中' if v else '外れ'
def sec(x):return f'{x:.3f}'
counts=s['category_counts'];e1,e2,e3=[s[k] for k in ('E1','E2','E3')]
singleton=[r for r in rows if r['singular_status'].startswith('univariate:') and json.loads(r['singular_candidates'])==json.loads((P/'records'/(r['case_id']+'.elim.json')).read_text()).get('reference')]
singleton_e2=[r for r in singleton if int(r['geosolver_correct_out_of_5'])>=3]
sensitivity='消去候補集合だけで参照集合と一致する例は'+str(len(singleton))+'問。これらを正解に含める感度集計ではE1は'+str(e1['observed']+len(singleton))+'/34問、E2は'+str(e2['observed']-len(singleton_e2))+'問（変換不能も除くと'+str(e2['excluding_conversion_failures']-len(singleton_e2))+'問）。主判定の定義は変更しない。' if singleton else ''
table=f'''| 予測（変更なし） | 観測 | 判定 |
|---|---|---|
| E1：正しい答え集合は26/34問以下 | {e1['observed']}/34問 | {verdict(e1['met'])} |
| E2：厳密側が答えを出せず、geosolverが3/5回以上正解する問題が6問以上 | {e2['observed']}問 | {verdict(e2['met'])} |
| E3：両方が解ける問題の求解時間中央値はmsolveが短い | {e3['intersection_problems']}問で {sec(e3['msolve_solve_median_seconds'])}秒 対 {sec(e3['geosolver_per_problem_correct_median_seconds'])}秒 | {verdict(e3['met'])} |
'''
only_ms=[r['case_id'] for r in rows if r['msolve_category']=='正しい答え集合' and int(r['geosolver_correct_out_of_5'])==0]
only_ms_text=('、'.join(only_ms)+'はmsolveが正しい集合を出し、geosolverは0/5回だった。') if only_ms else ''
wrong=[r for r in rows if r['msolve_category']=='不正解'];timeouts=[r for r in rows if r['msolve_category']=='時間切れ']
if not wrong:wrongtext='有限な答え集合の不正解は0問で、不正解例は得られなかった。'
else:
 abnormal=[r for r in wrong if r['msolve_status'].startswith('error:')]
 numerical=[r for r in wrong if r not in abnormal]
 wrongtext='不正解区分'+str(len(wrong))+'問。'
 for r in abnormal:
  wrongtext+=r['case_id']+'は'+f"{float(r['msolve_solve_seconds']):.1f}"+'秒でSIGSEGV（原因未確定、最大RSS '+f"{int(r['peak_tree_rss_bytes'])/(1<<30):.2f}"+' GiB）。10度・15度の角度条件を含む15変数・13等式の系で、答えは出なかった。'
 wrongtext+='この異常終了問はQ30で2/5回正解のため、E2の件数には影響しない。' if abnormal else ''
 wrongtext+='有限な答え集合の誤りは'+str(len(numerical))+'問。'
if timeouts:
 features=[]
 for r in timeouts:
  cid=r['case_id']
  if cid=='HMMT-2024-FEB-GUTS-04':description=f"固定図形・DSL未知数0でも、三角関数の定数を多項式化すると{r['polynomial_vars']}変数"
  elif cid=='HMMT-2010-FEB-TEAM1-07':description=f"10度・15度の角度条件と距離補助変数を持つ{r['polynomial_vars']}変数の系"
  else:description=f"{r['polynomial_vars']}変数・{r['polynomial_equations']}等式の系"
  features.append(f'{cid}（{description}）')
 timeouttext='時間切れは'+ '、'.join(features)+'。負荷の影響もあり、難しさの原因は確定できない。'
else:timeouttext='時間切れは0問で、時間切れ例は得られなかった。'
answer=table+f'''
4基準：①直感に反するか＝弱い（表現の差を含む）。②深い理論が必要か＝未確認。③広く再現するか＝限定的（固定34問、厳密側は各1回）。④solverならでは＝弱い（固定変換器の制約を含む）。**Aの中心を、この比較だけで担うことはできない。** 実用上の補足証拠とする。

{wrongtext}{timeouttext}{only_ms_text}

E2は変換不能{counts.get('変換不能',0)}問を含む。これを除いても{e2['excluding_conversion_failures']}問で、同じ6問の基準を{'満たす' if e2['excluding_conversion_failures']>=6 else '満たさない'}。有限でない系のSingular消去候補は、最終検証済みの答え集合に数えていない。{sensitivity}

時間は共有機・4並列での参考値。1分loadは{pre['load_before'][0]:.1f}（実行前）、{s['load_1min']['min']:.1f}〜{s['load_1min']['max']:.1f}（実行中）で、Q30とは負荷が異なる。E3は求解だけの比較で、変換・検証込みの中央値は{sec(e3['msolve_total_median_seconds'])}秒。GMBは値の集合を問う書式を表せないため、この34問では比較しない。
'''
(P/'answer.md').write_text(answer)
counttable='| 区分 | 問数 |\n|---|---:|\n'+''.join(f'| {k} | {counts.get(k,0)} |\n' for k in ['正しい答え集合','不正解','時間切れ','メモリ不足','有限でない','変換不能'])
elimtable='| 問題 | Singular消去 | 参照値が候補に含まれる |\n|---|---|---|\n'+''.join(f"| {r['case_id']} | {r['singular_status']} {r['singular_reason']} | {r['singular_reference_among_candidates'] or '未判定'} |\n" for r in rows if r['singular_status'])
summary=f'''# 実験1：固定34問とmsolveの比較

事前登録 `70443d65` の実験1のみ実行。開始 {ex['started_utc']}、終了 {ex['finished_utc']}。予測・閾値・対象は変更していない。判定は [answer.md](answer.md)、全件は [per-problem.csv](per-problem.csv)。

{counttable}
geosolverはQ30の既存170枠（欠測も分母に残す）を使用し、正解{s['geosolver_correct_runs']}/170回、3/5回以上正解は{s['geosolver_at_least_3_of_5']}/34問。欠測は厳密側{s['msolve_missing_records']}件、geosolver側{s['geosolver_missing_runs']}件。再実行はしていない。aは `per-run.csv`、bは同等の実行表 `results.csv`（bに `per-run.csv` は存在しない）を使用した。

実行元はクリーンcheckout `/tmp/q6e1-clean`、凍結版 `60db4b6`。src全251ファイルをgitと照合し、source_hash `{pre['source_hash']}` を実行前に確認した。固定コード11ファイルは変更なし。34問のDSLとcasesのhashはQ30の固定記録に一致した。共有worktreeのsrc・benchmarksは実行に使っていない。独立した `/tmp/q6e1-run/benchmarks/` に変換コード・34問・凍結research_runnerを配置し、作業ディレクトリとsrcのimport先をクリーンcheckoutに固定した。

msolve 0.9.4、1スレッド、各600秒、最大4並列。各プロセスの仮想アドレス空間に8 GiB（8,589,934,592 bytes）上限を設定し、ラッパーで実際のlimitsを保存した。システム導入なし。固定コードの最終検証上限は別途600秒。各実行は1 CPUに固定したが、割当先が重なる時間帯がある。時間は共有負荷下の値で、専有4コアでの測定ではない。Q30も同じ共有機で最大4並列だが、実行時期・CPU割当・負荷は一致しない。

「正しい答え集合」は、固定コードの最終検証を通過した実数解の答え集合が参照集合と一致した場合（既存の相対許容誤差1e-7）。不等式・枝は多項式へ入れず、最後の検証で絞った。形式的な完全性の証明ではない。「変換不能」{counts.get('変換不能',0)}問には、未対応のpi式・min各1問と、未知数0の入力でmsolveがerror:-11になった2問を含む。後者はmsolveの数学的な不正解として数えていない。「不正解」区分には、変換はできたが異常終了して答えを出せなかった例も含め、原因は別記する。メモリ不足は明示的な割当失敗の証拠がある場合だけにした。

有限でない5問には、固定コードのSingular消去を各600秒・同じ8 GiB上限で試みた。消去候補の参照値包含だけでは正解扱いにしない。厳密パイプライン34件、消去経路{ex['singular_elimination_attempts']}件（Singular実行4件、消去前の変換不能1件）、再試行0回。

{elimtable}
{sensitivity} 単一候補を得た例も、固定コードでは座標の復元と元のDSLによる最終検証をしていないため、主表では「有限でない」に残した。

E1〜E3は [answer.md](answer.md) の通り。E3の対象は、厳密側が正しい答え集合を出し、Q30で1回以上正解した共通{e3['intersection_problems']}問。各問題のQ30正解回だけで時間中央値を取り、その問題別中央値の中央値と、msolve求解時間の中央値を比較した。変換・検証込みは{sec(e3['msolve_total_median_seconds'])}秒、Python起動等も含むプロセス時間は{sec(e3['msolve_process_wall_median_seconds'])}秒。失敗回や時間切れを速度中央値に混ぜていない。

CSVの `solve_seconds` はmsolve＋Singular消去の合計（消去なしはmsolveのみ）。`msolve_solve_seconds` はmsolveのみ、`msolve_total_seconds` は変換＋msolve＋最終検証。変換不能で求解未実施の時間は空欄。geosolverの時間は既存表の `wall_seconds`（正解までのsolver時間）で、欠測・不正解を除いた中央値。

生入力・出力・ログ・資源記録はリポジトリ外 `{pre['raw_directory']}` に保存。5 MB超の生ログもそこに置く。`raw-manifest.json` に全ファイルのパス・サイズ・SHA-256、`preflight.json` に実行前の条件と入力hash、`records/` に小さい結果JSON、`load.jsonl` に30秒ごとの負荷を残した。外部保存先は一時領域なので、長期保存には別途退避が必要。

GMBは値の集合を問う書式を表せないため比較しない。
'''
(P/'summary.md').write_text(summary)
