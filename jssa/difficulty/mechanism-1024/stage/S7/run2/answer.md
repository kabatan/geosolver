HMMT-2023-FEB-GEO-07 の環境欠測補完を完了。D_base=484.53438515817004、D_raw=160.89844175205795。

W判定の旧→新: W1: 当たり→当たり、W2: 外れ→外れ、W3: 当たり→当たり、W4: 当たり→当たり。変更した判定: なし。

元のErrno 122は interrupted_env_quota として interrupted-env-quota/ に元ログ・receipt・0バイトinitial.pkl・SHA-256を保存。旧answer.mdは answer-before-quota-rerun.md に保存。ユーザーの明示指示によりこの1問のみ、seed 0の主探索1回→候補保存→固定scales→BASE精密化90秒→RAW精密化90秒→保存refined.pklから両measureを実行した。1枠、taskset -c 31、内部OMP/BLAS等1スレッド、全工程foregroundでwait。各runtime開始終了receiptはThreads=1・affinity=[31]。ただし実行中のsearchとrefine.BASEではOS Threads=2を観測した。新規補完の実行条件監査もviolationsとし、内部1スレッド条件の完全充足は主張しない。追加threadの役割は観測receiptのみでは不明。再探索・再精密化は追加しない。他265問の生ファイル・集計行、solverソース、driver.py、worker.py、analyze.py、入力・参照値・分類・分母・閾値・構成は不変。元events.jsonlは変更せず、新工程は対象run内の専用receiptに記録した。旧resume-started.jsonは保存し、completed_files内の当該5原本の参照先だけをscratchの事故退避先に移し、hash値と他フィールドは不変。analyze.pyを無変更で実行し、旧報告と同じannotate_failures.pyで既存例外詳細を追記して再集計した。下記の「測定修正」「再実行なし」「no_retries」および元イベント由来の工程数は先行campaign/measure修正時点の履歴を述べる。今回の1問の例外は本補完記録とquota-rerun-audit.jsonが示す。元の2件のthread逸脱は保持。

---

実行条件監査: violations。OS Threads=2の終了receiptが2件あるため、内部1スレッド条件の完全充足は確認できない。CPU affinity各1コアと最大10並列は維持。

| 予測 | 判定 | 固定分母での結果 | 欠測 |
|---|---|---|---|
| W1 | 当たり | 非特異 209/228 = 91.67%（必要80%以上） | 2 |
| W2 | 外れ | 非特異 209/228 − 特異 32/37 = 5.18ポイント（必要20以上） | 非特異2 / 特異0 |
| W3 | 当たり | 固定266問のうち接する条件なし・raw特異/base非特異 5問（必要1問以上） | 分類欠測0 |
| W4 | 当たり | W3対象のうち D_base−D_raw≥40: 4/5 = 80.00%（必要3問以上） | 0 |

seed 0の主探索直後の同じ候補集合から各90秒で一度ずつ精密化した。Dは最良候補の目標値の絶対誤差の−log10（上限600）。最良候補は通過状態で選別しない。参照値は段階(1)の保存参照解のanswer。最終検証は行っていない。

今回の変更は保存refined.pklからのmeasure再実行のみ。探索・精密化は再実行せず、元measure JSONは*.measure.original.jsonとして保持。旧answer-measure-failed.mdは測定不具合による全欠測の旧結果であり、精密化性能を測定した結果ではない。詳細はmeasure-fix-note.md。

分母は固定分類の全該当問題。欠測を成功に数えない。追加除外・再分類・探索・精密化の失敗/外枠タイムアウトの再試行・別seedはない。W3/W4は接する条件なしの固定5問を使う。

| base区分 | raw区分 | 接する条件 | 全問 | 測定 | 欠測 | D_base≥300 | 固定分母割合 | 測定分母割合 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 不定 | 不定 | なし | 1 | 1 | 0 | 1 | 100.00% | 100.00% |
| 特異 | 特異 | なし | 34 | 34 | 0 | 30 | 88.24% | 88.24% |
| 特異 | 特異 | あり | 3 | 3 | 0 | 2 | 66.67% | 66.67% |
| 非特異 | 特異 | なし | 5 | 5 | 0 | 5 | 100.00% | 100.00% |
| 非特異 | 特異 | あり | 7 | 7 | 0 | 4 | 57.14% | 57.14% |
| 非特異 | 非特異 | なし | 190 | 189 | 1 | 178 | 93.68% | 94.18% |
| 非特異 | 非特異 | あり | 26 | 25 | 1 | 22 | 84.62% | 88.00% |

| 接する条件 | 全問 | 測定 | 欠測 | D_base≥300 | 固定分母割合 | 測定分母割合 |
|---|---:|---:|---:|---:|---:|---:|
| なし | 230 | 229 | 1 | 214 | 93.04% | 93.45% |
| あり | 36 | 35 | 1 | 28 | 77.78% | 80.00% |

| W3問題（接する条件なし） | σ_base | σ_raw | D_base | D_raw | 符号付き差 | ≥40 |
|---|---:|---:|---:|---:|---:|---|
| AIME-2013-II-04 | 4.06109650152105987e-2 | 0.0e+0 | 348.60 | 42.93 | 305.67 | ○ |
| AIME-2020-II-04 | 2.96050429582565398e-3 | 5.64327647787199144e-135 | 600.00 | 35.39 | 564.61 | ○ |
| HMMT-2006-FEB-GEO-01 | 1.63936116943781958e-1 | 0.0e+0 | 350.19 | 42.52 | 307.68 | ○ |
| HMMT-2009-FEB-GEO-01 | 3.19021598097584908e-1 | 0.0e+0 | 349.30 | 43.76 | 305.54 | ○ |
| JMO-2021-PRE-07 | 2.77624266246783864e-4 | 2.0493317896195138e-134 | 483.25 | 470.25 | 13.01 | × |

base不定は1問（D_base欠測0問）。型別表には含め、W1/W2の特異/非特異分母には入れない。

欠測を除いた参考成功率: 非特異 92.48%、特異 86.49%。欠測を全て不成功/成功とした率の範囲: 非特異 91.67%〜92.54%、特異 86.49%〜86.49%。
W2の率差の欠測感度範囲: 5.18〜6.06ポイント。W4成功率範囲: 80.00%〜80.00%。

外れた予測: W2。閾値や対象を変えず、そのまま報告する。
W1/W2がともに当たらない場合、正しい図での特異さが精密化の難しさを決めるという一般化は主張しない。W3/W4がともに当たらない場合、書き換え一般への原理の拡張は主張しない。

Dの欠測は計6問題×構成。返却候補の目標評価欠測58件、精密化で未処理166候補。非ゼロ/外枠打切り工程4件。理由は次表とCSV/JSONに保存。

| 問題 | 構成 | 欠測理由 |
|---|---|---|
| AIME-2008-II-11 | RAW | refine.RAW: returncode=1, reason=None; geosolver.problem.ir.errors.IRCompileError: 評価エラー (HP モード): circle radius must be positive (expr: 'Circle(O2, r)'); log=/tmp/mechanism-S7-run2-vitdtysc/runs/AIME-2008-II-11/refine.RAW.log |
| AIME-2019-II-11 | BASE | 全候補の目標評価不能: ValueError 1件; details=/tmp/mechanism-S7-run2-vitdtysc/runs/AIME-2019-II-11/BASE.measure.json; sha256=8750e1f17456c2e4236e4fcb45979c614fca9cc3678c80fd049bb508cfd6742c |
| AIME-2019-II-11 | RAW | 全候補の目標評価不能: ValueError 1件; details=/tmp/mechanism-S7-run2-vitdtysc/runs/AIME-2019-II-11/RAW.measure.json; sha256=023fc5e34de3854b006f705e1198c0da9236ea96c85b040b54450d9273bbc17a |
| JMO-2011-PRE-11 | RAW | refine.RAW: returncode=1, reason=None; geosolver.problem.ir.errors.IRCompileError: 評価エラー (HP モード): circle radius must be positive (expr: 'Circle(O, r)'); log=/tmp/mechanism-S7-run2-vitdtysc/runs/JMO-2011-PRE-11/refine.RAW.log |
| JMO-2017-PRE-04 | BASE | 全候補の目標評価不能: ValueError 20件; details=/tmp/mechanism-S7-run2-vitdtysc/runs/JMO-2017-PRE-04/BASE.measure.json; sha256=7511c96ebf267965f2e3f24ed48df0e5594964c717ee659a1d1eec56046dea9f |
| JMO-2017-PRE-04 | RAW | refine.RAW: returncode=1, reason=None; geosolver.problem.ir.errors.IRCompileError: 評価エラー (HP モード): circle radius must be positive (expr: 'Circle(O, r)'); log=/tmp/mechanism-S7-run2-vitdtysc/runs/JMO-2017-PRE-04/refine.RAW.log |

実行はkabatan-superPC、最大10並列、CPU [22, 23, 24, 25, 26, 27, 28, 29, 30, 31]、各1コア・内部1スレッド設定。runtime receiptのOS Threadsが1を超えたものは2件であり、実行条件監査はviolations。共有機の1分load averageは3.71〜76.25。壁時計予算下の結果であり速度を一般化しない。

BASEソース: `sha256:03a44bfbb743b972d95306c63a14c04b78c7d12b96a1ba83d147c56eea7f86a3`。rawはREADME/raw_switch.py記載のNO_RESIDUAL_REWRITE+T1。段階(1)と同じT1式・固定円円分枝を使う。接点、距離0の座標差、半径補助式は使わない。実行前の参照残差チェック266問は全件一致。

per-problem.csvは全266問の固定σ・型・D・時間・欠測、per-candidate.csvは全返却候補と未返却初期候補を記録する。小さい値は指数表記、CSVは25有効桁、生データは700桁で評価。判断は丸め前の値で行う。
生ログ・全座標・入力・ソースコピーは `/tmp/mechanism-S7-run2-vitdtysc`。全ファイル3,000,000bytes未満、hashはraw-hashes-*.json。実行前hashはpre-run-hashes.json、固定入力不変・最大並列・CPU/スレッド・同一初期候補の監査はaudit.json。


環境事故（/tmp容量超過・sandbox障害）で中断後、完了済み163問は元生ファイルのSHA-256一致を確認し探索・精密化を再実行しなかった（今回のmeasure修正では旧measureを.original.jsonに保持して照合）。problem_doneなしの8問は中断=結果に数えず、旧ファイルを退避し問題の最初から各1回のみ実行した。これは失敗の再試行ではなく中断の再開。未着手95問も元の条件で実行した。失敗(returncode≠0)・外枠タイムアウト工程の再試行はない。旧events.jsonlの全prefixと退避ファイルも不変。CPU割当は元のstreamのまま、全新規工程で/tmp空き6 GiB以上を開始条件とした。

中断して結果から除いた問題: AIME-2025-II-06, AIME-2025-II-14, HMMT-2009-FEB-GEO-01, HMMT-2009-FEB-GEO-09, HMMT-2013-FEB-GEO-04, HMMT-2024-FEB-GEO-09, JMO-2015-PRE-02, JMO-2017-PRE-10。ハッシュ更新履歴はhash-update-history.jsonとresume-history/pre-run-hashes.json。探索・精密化のworker、ソース、予算、分類、参照値、閾値、判定式は変更していない。


報告上の制約: 旧目標評価例外の全文は各BASE/RAW.measure.original.jsonに保持し、新測定の例外は各measure.jsonに保持した。CSV/欠測表は例外型・件数・参照先・hashに要約した。per-candidate.csvのerror_detailsはscratch/runs/<case_id>/に対する相対参照であり、親measure.jsonのhashはper-problem.csvとraw-hashesに保存した。CSVの要約は3 MB未満の表示制約のため。今回の測定修正では保存済み座標だけを同じ700桁・同じ参照値で再評価した。

実行条件逸脱: 次の終了receiptでOS Threads=2を観測した。CPU affinityは各1コア、OMP/BLAS等の設定値は1。追加スレッドの役割は保存receiptからは確定できない。symbolic reader threadの終了待ち残存というコード上の可能性はあるが、当該threadのID/stack記録がなく原因不明。元工程の内部1スレッド条件を満たしたとは主張しない。精密化は再実行していない。

- /tmp/mechanism-S7-run2-vitdtysc/runs/HMMT-2018-FEB-GEO-10/refine.BASE.runtime-end.json
- /tmp/mechanism-S7-run2-vitdtysc/runs/HMMT-2011-equilateral-hexagon/refine.BASE.runtime-end.json


測定修正の実行条件監査: pass。最大8並列、各1コア・内部1スレッド、正常終了527工程、対象外5工程。探索・精密化・失敗refineの再実行0。元生ファイル11019件のhashを確認。旧実行の2件のthread逸脱は取り消さない。

終了コードだけでは不足する欠測理由は、生ログの例外末尾をannotate_failures.pyで追記した。この補助スクリプトは実行開始後の報告用追加であり、探索・精密化・測定値・判定規則は変更していない。
