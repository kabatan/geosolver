# 段階2の実装と記録

段階1の選択・DSL・予測・lockは変更しない。前回の段階2は最初のツール実行前に中断しており、引き継ぐ試行はなかった。許可根拠、環境とhashは `execution/receipt.json`。

- 全56,000局所枠・840完成枠を先に `/tmp/q41-stage2/slots.jsonl` に列挙した。生成不能の102条件は計画どおり失敗枠として保持。実行するのは178条件の35,600局所枠・534完成枠。
- 実行コードはこのディレクトリに置き、solverは `/tmp/q41-clean/src` のみをimportする。依存版は凍結pyproject/lock対応の既存環境。BLAS/OMPは1スレッド、同時実験は最大2。各ランナーコマンドは210秒以内。
- 局所は凍結 `_collect_local_start_record` を直接呼ぶ。SciPyの戻り値を観測するだけで変更しない。各枠2秒、検証1秒。nと、guard/hard罰則を足す前のlower後の等式数で、凍結関数がLM/Powellを選ぶ。生DSLの等式数も別に保存する。
- 採点は元のDSLの等式残差。loweringが追加した帰結式・平滑化・正答の同定式を採点の残差に混ぜない。元のguard/hardを維持し、targetを含む構築の有限性を確認する。floatを通った同じ終点を十進17桁経由で80桁再評価する。位置は動かさない。採点器は `execution/implementation.lock.json` で最初の局所試行前に固定。
- 完成solverは通常のpublic serviceと凍結workerを使う。外部ラッパーは `FloatCandidate` / `RefinedCandidate` の生成を全件保存し、各段階の採否・乱数・予算を変更しない。有限差分用の内部評価点は候補レコードではない。時刻はsolver内で候補が生成された時点であり、内部の代数計算がスカラー根を計算した時点ではない。保存費用は実時間に含める。
- 完成solverの全候補は実行後、1件1秒の同じ採点器で再評価する。候補数の上限は置かない。再評価コマンドを分割するときも未処理候補だけを続ける。観測欠測はT=180。最終solve時間で代用しない。
- HP座標の保存は、凍結版が精密化中の `float(mpf)` を禁じることを静的点検で確認し、完成solverを1回も走らせる前に十進文字列による保存へ修正した。旧observer bytes・lockを外部保存し、`execution/observer-revision.json` に記録した。共通採点器・solver・予測は変更していない。
- Jはp・T測定後に、各条件の局所成功番号の小さい順に最大5点だけを選ぶ。80桁・5秒の凍結精密化、元条件の再確認後、登録した3刻みの中心差分とSVD。数値rankの表示閾値はσmaxの1e-8。全特異値とn−m個のゼロを残す。構造自由度と特異点を区別できない例は機構支持0とする。

実行は `run_stage2.py local`、`full`、`verify` の順に未処理枠がなくなるまで反復する。次に `jacobian_stage2.py prepare`、`run_stage2.py scaling`、`jacobian`。最後に `analyze_stage2.py` と `audit_stage2.py`。ランナーの途中終了を再試行の理由にせず、開始済みで結果のない試行は中断失敗として残す。

生の始点・終点、発生時刻、候補、検証、Jは `/tmp/q41-stage2/` に保存。リポジトリには5MB以下のコード、集計、台帳、外部ログのhashのみを置く。

J測定を1回も始める前の静的点検で、操作の有効性を計る分母が元図の点間距離となるよう、同じ座標で元版の構築を評価し、ベクトルを点に混ぜない実装へ改訂した。旧bytesとlockは外部保存、改訂記録は `execution/jacobian-revision.json`。成功率・時間の採点器、Jの終点選択・差分刻み・閾値は不変。

`jacobians.csv` は特異値の最小値・最大値・rank等の集計と外部記録の参照先を置く。全特異値は `/tmp/q41-stage2/jacobian/*/done.json` に保存し、5MB超の詳細出力がリポジトリへ入らないようにする。
