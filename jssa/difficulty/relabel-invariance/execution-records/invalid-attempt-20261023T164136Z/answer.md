4基準の判定：①直感に反する＝未判定、②深い理論が必要＝未確認、③広がりと再現＝未検証、④solverならでは＝未確認。**Aの中心を担えるか：現時点では不可（段階2が実行契約違反で未完）。** 仮説を棄却したという意味ではない。

Q38・段階2、2026-10-24 JST。**計840実行のうち、最初の4実行で読込先の契約違反が検出され、固定計画に従って停止した。4件は無効・未採点、836件は未実行である。正答率・時間の変化割合も、Q34と同じ機構かも判定できない。** 予測・変換規則・問題選択・DSL・実行計画・solver・採点器は変更していない。再試行、次のbatch、追加seedは実行していない。

**固定内容と開始記録。** 許可対象はcommit `58e399315f259699e99cc1b190aa46c78d573e5a`、commit時刻は `2026-10-23T16:18:31Z`。ユーザーのpush確認と、このcommitを含むローカルの `origin/claude/project-thread-9bdbbg` を確認した。ネットワークでの再確認は行っていない。`prediction.lock.json` 自体も同commitの内容と一致した。

- lockのSHA-256：`1db2ccc64213d70f5ea97e8b89f90efb4989f81db9292068f5fa7fd7430e4bc5`
- 予測本文のSHA-256：`91a1c5d5ab8a01dcb541a046ae6a8b0a86d4b991390d8b07eeba935680c914f1`
- ロック対象261ファイル、全200変換DSL、manifestのハッシュを開始前と停止後に照合。一致。静的再検証も240文書・210batchで通過、新規solver呼出し0。
- クリーンな実行用checkoutの `src/`・runner・元コーパス・依存lockは `60db4b6` と一致。親プロセスのruntime fingerprintとengine lockも通過。
- 実行開始：**`2026-10-23T16:41:36.567667Z`**。停止：**`2026-10-23T16:41:50.766927Z`**。[開始記録](execution-records/execution-start.json)、[事前検査](execution-records/preflight.json)、[停止receipt](execution-records/000.json)。

前担当の `16:23:27Z` の記録は起動要求と空のlauncherログだけで、runコマンドのreceipt・campaign manifest・solver成果物がなかった。ユーザーの「solver未開始」と一致し、旧記録は別の一時領域へそのまま保存した。今回は開始時刻を新たに記録した。[再開監査](execution-records/resume-audit.json)

**停止した4件の全件表。** 固定されたbatch 0、`point_names`、seed `380101`、各180秒予算。時間は保存された未採点の診断値であり、主比較の観測値には採用しない。

| 問題 | solverの返却status | 診断上のwall秒 | CPU秒 | 固定CPU | 採点・扱い |
|---|---|---:|---:|---:|---|
| HMMT-2006-FEB-GEO-01 | solved | 2.839 | 1.35 | 1 | 読込先契約違反、無効・未採点 |
| HMMT-2021-FEB-GEO-03 | solved | 0.718 | 0.53 | 2 | 同上 |
| HMMT-2023-FEB-GEO-04 | solved | 11.820 | 5.79 | 0 | 同上 |
| JMO-2019-PRE-04 | solved | 13.627 | 13.40 | 3 | 同上 |

全4件でCLIのreturn codeは0、外部timeoutはfalse、唯一の契約違反は `executed_import_root_mismatch`。runnerはreturn code 2で停止し、`assess` と `summarize` には進まなかった。`solved` は厳密答え集合の完全一致を意味しない。4件を正解にも問題の不正解にも数えず、採点器の `matched` を独自に作り直していない。実行済み4件の記録欠落は0件である。

**停止原因。** 親runnerは `/tmp/q38-58e3993-clean/src/geosolver` を読んだが、4件すべてのworkerは `/home/kabatan/work/solver/src/geosolver` を読んだ。固定環境の `PYTHONPATH=src` は相対パスであり、凍結版の [worker起動処理](../../../src/geosolver/engine/runner.py) は作業ディレクトリを新しい一時ディレクトリへ変える。この場所では `src` がcheckoutを指さず、既存venvの `_editable_impl_geosolver.pth` に登録された `/home/kabatan/work/solver/src` が使われる。

solverを呼ばずに、同じPython・同じ環境変数で「checkoutからimport」と「一時ディレクトリからimport」を比較し、この差を再現した。[importのみの診断](import-diagnostic.json)。これは乱数や最適化の原因診断ではなく、実行環境の診断である。

両方のソースハッシュは `sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5` で一致し、別バージョンのsolverが動いた証拠はない。しかし、無変更の [research_runner](../../../benchmarks/research_runner.py) は読込先の一致も要求するため、有効な計測にはできない。親だけの事前検査では、子の作業ディレクトリ変更に伴うimport先の差を捉えられなかった。

継続には、子からもクリーンなcheckoutを参照する専用Python環境をオフラインで用意し、importのみで確認する必要がある。固定された `PYTHONPATH` やrunnerの契約検査を緩める変更は行っていない。加えて、[固定計画](execution-plan.md) は契約違反時の停止と無断再試行の禁止を定めているため、今回の4件を修正環境でやり直す扱いを確定しないまま続行することもしていない。

**割合・予測の判定。** A（正答率差≥2/3）とT（対応する成功seedのうち2個以上で同方向の3倍以上かつ2秒以上の差）は、ともに**算出不能**。0/40と報告することはできない。原本・変換の有効な対応組、原本の同seed反復比較、時間比較可能な問題はいずれも0。1/3差、正誤不一致seed数、改善／悪化、成功時費用も未推定である。

| 固定予測 | 今回の判定 |
|---|---|
| P1：Aが0〜4/40問、点予測2問 | 未検証 |
| P2：Tが12〜20/40問、点予測16問 | 未検証 |
| P3：点名だけではA=0、T=0〜2問 | 未検証 |
| 変数順を含む3modeが全Tの2/3以上 | 未検証 |

全840予定セルの状態を [runs.csv](runs.csv)、40問を [per-problem.csv](per-problem.csv)、8層を [per-stratum.csv](per-stratum.csv) に残した。未実行と無効を区別し、`matched`・A・Tの空欄は欠測である。数値要約は [results-summary.json](results-summary.json)。

**Q34との比較。** [Q34の結論](../fractal-basins/answer.md) は、局所の1ulp摂動で行き先変更3/12問、厳格なフラクタル認定0/12問、完成solverの同seed厳密答え集合変更0/24組だった。Q38では有効な原本比較がなく、これを補強も反証もできない。今回の読込先契約違反を初期値への鋭敏な依存と結び付ける根拠はない。

事前仮説では、変数順の変更は同seedの乱数を別の座標へ割り当て、条件順の変更は内部の尺度軸を変える場合がある。これらは有限の始点・座標の変更であり、Q34の1ulp摂動と同じ機構と即断できない。4件のcounters・phase timings・候補採用元などは [無効実行の診断要約](invalid-run-diagnostics.json) に保存したが、比較対象がないため効果の原因特定には使っていない。

**負荷と保存。** AMD Ryzen 9 9950X3D、16物理コア・32論理CPU。CPU 0/1/2/3は異なる物理コアで、各実行は1コア、同時solver実行は最大4。全4件で実際のaffinityは指定CPUと一致した。BLAS等のthread環境変数も1。CPU固定は他作業との共有やSMT兄弟の競合を除くものではない。

開始時のload average（1/5/15分）は **12.42／18.77／18.65**。実行中と停止時を含む記録範囲は **11.89〜12.42／18.34〜18.77／18.51〜18.65**。共有機の競合はwall時間を延ばし、時間予算内の探索量にも影響し得る。CPU時間とwall時間の差も、競合だけに帰属できない。原本反復が未実行なので背景変動の大きさを見積もれていない。

各batchを `nohup`・ログ付きの非同期セッションで起動する補助 [launch_batch.py](launch_batch.py) を追加した。[stage2.py](stage2.py) 本体は無変更で、長時間の複数batchコマンドは作っていない。初回のログ用ディレクトリ不足によるシェル起動失敗はPython起動前で、solver呼出しには含まれない。ディレクトリを作成した後の起動が上記4件である。

4.9MBのファイル上限を適用し、保存時assertionや上限超過による欠落はなかった。生データの最大ファイルは **2,285,879 bytes**。生データは `/tmp/q38-58e3993-execution/campaigns/` に置いたまま、リポジトリには小さな要約・receipt・ハッシュだけを追加した。生データの結合・コピー・commitは行っていない。再集計は [report_stopped.py](report_stopped.py) で行え、このスクリプトはsolverを呼ばない。
