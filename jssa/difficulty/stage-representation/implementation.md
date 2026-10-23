# Q39 段階2の実装対応

予測・診断設計・選択・src・既存採点器は変更しない。段階1の固定ファイルと
251個のsrcファイルのSHA-256を各batch開始時と各worker開始時に検査する。
ユーザーの段階2許可と最大3並列という資源指定は別の実行記録に保持する。

| 固定した接続点 | 実装 |
|---|---|
| 通常compiler/bundle/bounds | `GeometryProblem.engine_document` → `load_problem_bundle` → `infer_problem_bounds`をそのまま呼ぶ |
| 実際の書き換え行 | lowering後の式を段階1の構文分類器で再分類し、静的分類の種類・個数と照合。行→Bブロックを保存 |
| 53bitのB | float入力を既存の`boundary_float_to_mpf`でbinary値のまま境界変換し、凍結helperを`dps=15`で呼ぶ。`mp.prec==53`を検査 |
| 前段 | `NomadConfig`と`NomadBlackboxAdapter`をそのまま利用。目的値への入力だけproxyで切替。全callbackで元Aと凍結Bを計算する |
| 共通候補 | 元guard/hardを通る箱内有限点のQ最小、なければ箱内有限点のQ最小。tieは到着順。元A、B、Qと始点・候補のfloat.hexを保存 |
| 前段の予算 | native `MAX_BB_EVAL=1200`、`MAX_TIME=6`とadapterの6秒deadline。無効callbackを含む実回数と評価回数を両方保存 |
| 後段のA/B | 同じ保存FloatCandidateを1個ずつ既定の`MpmathRefiner.refine_candidates`へ渡す。Aだけsmoothをidentity化、Bは凍結helper |
| Jacobian | 全後段で`derivative_plan`の返り値をNoneにし、wrapper経由の差分では必ず`row_dependencies=None`。全stage・warm Newton・closureに作用 |
| L/R0/混合 | 設計された式の組立だけを外側で行う。R0の差分/closureに`one_sided_at_cusp=True`を渡す。最適化アルゴリズムはコピーしない |
| 同定前観測 | 入力・stage返却点・closure返却点・最終点を保存。mpf内部のbinaryタプルを保存するので、保存時のmp.dpsで丸めない |
| 参照答えの隔離 | 全前段のhash封印後だけ別の同一CPUの子プロセスが参照答えを読む。親solver workerは参照答えを読まない |
| 観測の順番 | 8候補の同定前座標を保存 → 別プロセスの180dps観測を保存 → hookを復元済みの元A evaluatorでPhase C |
| Phase C | `assemble_exact_results`を変更せず20秒の新しいdeadlineで実行。確認による座標改訂は同定前観測と別ファイル |
| 公式採点 | v2 rawへの形式変換だけを行い、凍結`research_runner.assess_campaign`をそのまま呼ぶ。正常保存された予算切れと外部強制終了のstatusを混同しない |

`diagnostic.py`はsolver接続と記録、`execute_stage2.py`はCPU固定・資源監視・
固定順のbatch提出、`measure_stage2.py`は独立な桁観測と消失次数、
`analyze_stage2.py`は固定分母の集計と既存採点器へのadapter、
`postprocess_stage2.py`は小さい後処理batchを担当する。

数値jobは各150秒の外側監視を持ち、同時に最大3個まで。長時間の親プロセスは
batchを提出するだけのcoordinatorで、探索・精密化はしない。子のsymbolic処理も
同じ1 CPUを継承する。workerと子の合計RSSは2 GiBで監視する。
保存は候補単位で原子的に行い、4,000,000 bytesに達する例外的なJSONは分割する。
小さい長さassertionで最終点を失わない。`RLIMIT_FSIZE=4,900,000`も継承する。

## 検査と実装上の修正記録

`wiring-check.json`は7構造層、A/B/Lの式対応、hook復元、500dps相当のbinary座標の
roundtrip、4 MB超の入力に対する分割保存を検査した結果。探索・精密化は0回。
`observation-check.json`は合成問題の2点だけを使う観測検査で、ベンチマークの
参照答えを使用しない。

初期の準備起動2件では、監視が`taskset`のaffinity設定前の瞬間を検出して停止した。
Python workerの開始markerも数値出力もないことを確認し、失敗記録を保存したうえで、
spawnするスレッドをfork前から固定する修正を加えた。再開したのは未着手の2件だけ。
詳細は`implementation-corrections.json`に保存した。

最初の前段3 jobの後に、まだ未実行だった`rear`関数へ独立観測の呼出しを追加した。
AST比較で前段関数や準備関数に変更がないことを確認し、hashと理由を
`execution/wrapper-version-3.json`に記録した。予測・診断仕様の変更ではない。
実行したworkerごとのwrapper hash、最初の実装コピー、後段開始時の実装コピーを保持する。

後段の開始前に、合成問題の観測チェックが`float(mpf)`のHP契約違反を検出した。
表示用の桁数への変換をHP評価の外へ移し、合成2点の再検査を通過した。
実際の後段試行やベンチマーク参照答えを使う前の修正であり、最適化の再試行はない。

## 共有ツリーの更新からの隔離

全前段の終了後・後段開始前に、別作業による共有`research_runner.py`の
null-diagnostics対応とタスク文書の更新をhash照合が検出した。
その変更を採用・取り消すことはせず、`isolate_runtime.py`でコミットにある
凍結済みの581ファイルを`execution/frozen-runtime/`へ取り出した。
src・採点器・corpus・DSLは`60db4b6`、静的監査資料は`59691a92`のbyteを用い、
source manifestおよび全選択DSLのhashを確認した。個々のコピーは読取専用。

`runtime-location.json`により、後段と採点のimportおよび入力の場所だけを
このコピーに切り替える。`isolated-runtime-check.json`は、前段と同じsolver source hash、
依存関係の一致、凍結採点器そのもののSHA-256を確認した記録である。
予測・診断設計・選択には変更がない。共有ツリーの他作業のファイルは保持する。
参照答えの数値cacheはこの検出直前に作成されたが、corpus hashの一致と
`reference_expressions`のAST一致を確認した。変更されていたのは採点結果の
null処理であり、参照式の分解ではない。公式採点には凍結版全体を使う。

生記録は`execution/`と`campaign/`に分割して保持し、両方をgitの対象外にする。
採否は`prediction.md`の基準だけで決め、失敗・timeout・NAも分母と要約に残す。
