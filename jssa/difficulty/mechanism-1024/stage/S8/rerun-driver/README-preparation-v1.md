# S8：事前登録15の実行前準備

指定された準備だけを完了。本計測106問×3seed×12構成=3816枠は0回、commit/pushも0回。事前登録文書は変更していない。固定物はローカルファイルとhashで保存し、事前登録15のpushによる固定は今回の指示に従って行っていない。

- [groups-env.md](groups-env.md) / [JSON](groups-env.json)：G1〜G6、8スイッチの正確な名前・値・コード位置・依存関係。
- [configs.json](configs.json)：12構成の8変数の完全な値。N+1はC1へのalias。
- [smoke-check.md](smoke-check.md) / [JSON](smoke-check.json)：2問×12構成、seed601、各20秒、最大6並列の実動作確認。24回完了、正誤記録なし、設定矛盾0件。全構成で8スイッチの実分岐を確認。救済探索は未発火であり、救済自体の動的動作は今回のログでは確認していない。
- [assignment.json](assignment.json) / [出典と規則](assignment-provenance.md)：既存の開発外34問＋機構72問をsha256順で53問ずつに固定。
- [nrr-final-check.md](nrr-final-check.md) / [JSON](nrr-final-check.json)：7bのNO_RESIDUAL_REWRITEは最終検証の接条件・距離0変換を止めない。verification_numerics.pyとfinal_verifier.pyはBASE0とバイト一致、evaluation内ablated参照0件。
- [patches/reconstruction.json](patches/reconstruction.json)：凍結版→既存ablation patch→new-switches.patchの再構築が指定finalの全srcと一致。同梱の凍結ソースarchiveとパッチを利用可能。
- [run-on-winpc.md](run-on-winpc.md) / [driver設計](driver-design.md)：WSLで同一BASE1を準備する手順、今後の本計測driver仕様。driver.pyはverify-plan専用で本計測の実行機能なし。driver.py自体も今回実行していない。
- [superpc-preflight.json](superpc-preflight.json)：source/engine lock、全入力、依存版、Pythonを読み取り専用で照合した記録。WinPCでの実行・検証は未実施。
- [source-hashes.json](source-hashes.json)、[hashes.json](hashes.json)、[SHA256SUMS](SHA256SUMS)：指定実装・固定物・診断ログ・パッチ・入力のhash。inputs.tar.gzは106問のDSLのみを元の相対パスで収録。

実装の境界で特に注意する点：NO_NOMADは通常探索をSciPyに替えるが、G2が有効なら救済MADSは残る。NO_ALGEBRAICでもG4の尺度chartは代数workerを呼びうる。NO_RESIDUAL_REWRITEは平滑化を必要とする解析Jacobian計画だけを拒否し、G6全体を止めるものではない。Nにも入力による変数削減・整数等の近道・最終検証/補正・PSLQは残る。

smokeの計画と観測コードはsmoke/freeze.jsonで実行前hashを保存。観測はprofileによる負荷を持ち、正答率や速度比較には使用しない。全生ログはsmoke/00〜23/に保存し、追加実行・再試行・別seed実行はしていない。
