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

## 本計測driverの完成（2026-10-24、準備済み固定物への追加）

今回のユーザー指示で累積7構成のsuperpc実行が許可された。run-plan.jsonのpreparation時のexecution_authorized=falseは原本を保持し、許可・選択した1113枠はrun-superpc/measurement-freeze.jsonへ別に固定する。元のREADME/driverはREADME-preparation-v1.md / driver-preparation-v1.pyにバイト保存した。旧hashes.json / SHA256SUMSは変更せず、measurement_preflight.pyはこの2原本に対して旧hashを検証する。verify_preparation.py原本も保持。

driver.pyのrun/resume/gradeは--machine superpc|winpc、--configs（空白/カンマ区切り）、--max-parallel（上限8）、--base-src（srcを含むBASE1ルート）、--repo-root（DSLの相対パスの起点）、--python、--output、--raw-rootを受け取る。N+1はC1へalias。元の3816枠の回転順序を一切変えず、指定機械・構成をfilterする。既定は累積7構成のみ。単独5構成を選ぶには後続の別指示が必要。run-on-winpc.mdは追記せず、新しい起動説明はwinpc-driver-usage.md。

S6/run/driver.pyのFIFO、排他lock、独立新規プロセス、所有木のPID/create_time監視と回収、CPU/OS thread affinity/環境の監視をmeasurement_runtime.pyへ流用。S6/run/grade.pyの数学的正規化をmeasurement_exact.pyへ、採点方針をmeasurement_grade.pyへ流用した。親の生成threadをspawn直前にCPUへ固定して子へ継承し、直後に親を復元する。子側bootstrapもexec前に固定を確認。異なる物理コアを最大8個選ぶ。GEOSOLVER_*を全部除去して8スイッチを全指定し、数値thread環境はconfigsの通り1。PYTHONPATHはBASE1/srcだけ。profile等の観測コードは入れない。

両機の既定メモリ契約は所有木RSS 4096 MiB（0.5秒標本監視、超過時失敗/180秒）、プロセス毎address space上限16384 MiB、単一書込ファイル上限2,900,000 bytes。stdout/stderrと監視ログは2,000,000 bytesで分割保存。外側deadlineは180秒。起動直前から終了検出までのwallと、所有木回収までのtotal wall、cleanupを別々に保存し、完全一致の費用にはtotal wallを使う。標本監視の間に生滅する短命子孫の直接観測は保証できないが、CPU/環境/AS/file-limitは継承される。

start/endは一時ファイルからatomic linkで排他的に固定し、出力dir全体をflockする。resumeは有効endと生ファイルhashを検証してskip。startのみは中断受領証を作り再実行しない。中断を結果数や費用180に数えずok/C=null、問題の3seed集計も未完として残す。未開始枠だけ続行できる。失敗・timeoutは180秒、再試行なし。模擬subprocess契約の記録はmeasurement-contract-results.json。実問題を単体確認に使わない。

採点参照はreferences.json / references-hashes.jsonへ本計測前に固定。S4.6（run-7b）のpre-run manifestの独立expected_keys、S3/run manifest、S6/run/references.json、開発外34問の既存のverified cases.jsonlのanswerを照合・正規化した。106/106で参照あり、重複参照の矛盾なし。採点不能一覧はungradable-references.md（今回0件）。新しい正解の計算は不要であり、実行していない。将来欠落・矛盾があれば対象を除外せず採点不能とし、独立の公式解答と元DSL targetとの対応を人が確認して別の事前固定手続きを行う。本計測から正解を逆算することはしない。

生ログはリポジトリ外の/tmp/mechanism-S8-superpc-raw-*へ保存し、各終了受領証に全ファイルのSHA-256とサイズを保存。ソース/入力/依存/Python binary/host/OS/CPU/機械filter/開始時load/資源監視を受領証へ記録。採点は計測の終了後に別プロセスで行い、参照をsolverの引数や環境へ渡さない。WinPC合算前の53問の結果はrun-superpc/answer.mdへ記録する。事前登録16補遺の時間比は両構成で解けた問題について正解seed実時間の構成内中央値の比、さらにその問題間中央値。対応seedで両方正解した比も補助値として記す。

新規driver一式のhashはmeasurement-driver-hashes.json、実行前のコード・参照・準備物hashとキューはrun-superpc/measurement-freeze.json、実行後の成果物hashはrun-superpc/artifact-hashes.json。commit/pushは行わない。

## 2026-10-24 再開始（attempt 2）

旧run-superpcは[run-superpc-aborted-attempt1/](run-superpc-aborted-attempt1/README.md)へ削除せず退避した。現存は開始19・終了11（全11はsolver status=solved、wall約3〜4.6秒）。quotaを示すログは残らず、resource_violationsはsolver内部のGEOSOLVER_MEMORY_LIMIT_BYTES/SYMBOLIC_PARENTを環境改変とした監視誤検出だった。「全30枠がsolver失敗/資源超過」とは立証できない。ユーザーの明示した全面やり直しと、旧試行の未完・監視不備を理由に試行全体を中断扱いとし、全件を結果・費用から除外する。旧rawも保持。詳細証拠とhashは旧dir/incident-audit.json。

本体source・references・入力・割当・seed・構成・資源契約は元の固定値を保持。再開始前に監視のみ修正し、solverが内部で追加する上記2変数を比較対象から外す（実値は引き続きreceiptsへ保存）。8スイッチ・数値thread環境・未知のGEOSOLVER変数の変更は引き続き違反。各新規枠の直前に/tmpとrawの空き6GiB以上を確認し、未満なら新規開始せず稼働枠終了後停止。明示的quota/no-spaceは環境中断として記録し、新規開始を停止する。新試行内では開始済み枠の再試行をしない。変更後の模擬subprocess契約6件と負荷照合の合成テストに合格。旧driver hashesはmeasurement-driver-hashes-attempt1.jsonへ保持。

[report_superpc.py](report_superpc.py)の負荷照合・時間ペア判定規則を本計測開始前にrun-superpc/analysis-freeze.jsonへhash固定。driver開始時loadをper-runに残し、外部ログの各utcから60秒の区間を実行時刻と照合。high_load_overlapは真/偽/不明の3値（欠測を偽にしない）。時間の比較は同問題・seedで1秒以上同時実行、開始load差≤5、外部high_load既知かつ同値、外部cpu_pct_otherの加重平均差≤200という固定条件を満たすペアのみ。全体C平均と事前登録式の算術値は参考であり、速度効果の支持判定には使わない。正解数は有効。WinPC合算前のsuperPC分のみ集計する。

[supervise_superpc.py](supervise_superpc.py)をdetachし、driver終了後に全endを確認して独立採点と負荷照合を行う。driver異常終了は同じ引数のresume（既開始枠は中断受領証を作ってskip）だけを許す。空き不足・明示的storage事故・正常中断時は自動で次の枠を開始しない。他プロジェクトに触れない。commit/pushなし。
