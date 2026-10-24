# S10 部分B：スイッチ準備・動作確認

準備成果物は作成済み。**B045のnative正常動作は未確認であり、全構成の動作確認成功ではない。** 本計測への投入可否を承認する報告ではない。

継続作業では前任の14件の実問題smokeと11件の契約probe（BASE1＋10構成）の保存済み出力を検査した。実問題smokeは再実行せず、ローカルPyNomadの合成プロトコル切り分け4件だけを追加した。成果物の正本は[design.md](design.md)、[configs.json](configs.json)、[switch-b.patch](switch-b.patch)、[source-hashes.json](source-hashes.json)。適用後source hashは `sha256:2cb435fc35950aafaf6bb2e3a40df30a7415c9fdc65d3ff4b8d969c361ecac75`。

## 保存済みsmokeの判定

| 構成 | 契約probe | 実問題smoke（各2件） | 確認の範囲 |
|---|---|---|---|
| B0 | 成功 | 2件終了コード0 | BASE1との決定的probe stdout生バイト一致 |
| B014 | 成功 | 2件終了コード0 | 3種のfloat floor除去は合成probe。実問題traceでは当該floor未到達 |
| B046 | 成功 | 2件終了コード0 | 実問題でNOMAD出力の罰則除去を確認。候補record保持は合成probe |
| B005_006 | 成功 | 2件終了コード0 | 実問題で尺度依存解析停止。guard境界除去は合成probe |
| B005 | 成功 | 2件終了コード0 | guard境界除去、明示境界・構成域保持は合成probe |
| B006 | 成功 | 2件終了コード0 | 実問題で尺度依存解析停止 |
| B045 | 成功 | **2件SIGSEGV（-11）** | Python側の設定・無効点通知だけ確認。native正常動作は**未確認** |
| B014_046 | 成功 | 対象外 | 併用時の契約だけ確認 |
| B005＋B006 | 成功 | 対象外 | 箱がB005_006と一致 |
| 全フラグ値0 | 成功 | 対象外 | BASE1とのprobe stdout生バイト一致 |

実問題は固定済みinputs.jsonのAIME-2007-II-15（a）とAIME-2009-I-12（b）のみ。全14件の外側timeoutはfalse、各ジョブ10秒未満。12件の終了コード0は呼出しが正常に戻ったという意味で、問題が解けたことを意味しない。解答・正誤・桁数・品質・時間優劣は比較しない。詳細は[smoke/driver.json](smoke/driver.json)と[smoke/checks.json](smoke/checks.json)。B045はworker receiptを保存する前に終了したため、2件ともreceiptがない。未作成を正常終了として補完していない。

前任のpreflight-attempt-1ではCPU0に固定したBASE1契約probeが10秒timeout、solverジョブ開始0件。その後CPU31に変更した履歴を保持した。既存smoke_driver.pyは全件成功assert（110–115行）によりchecks.jsonを書けなかった。今回のverify_preparation.pyはソルバーを起動せず、保存済み契約assertを再評価し、B045失敗を含むchecks.jsonを新規作成した。

## B045のローカル切り分け

インストール済みPyNomadBBO 4.5.1を直接importし、2変数の有限二次目的関数、seed 0、MAX_BB_EVAL 8で確認した。geosolverや原問題は読み込まない。

| DISCO_MADS_OPTIMIZATION | HID_CONST | BB_OUTPUT_TYPE | 終了コード | callback回数 |
|---|---|---|---:|---:|
| true | true | OBJ | 0 | 8 |
| true | false | OBJ | **-11** | **0** |
| false | false | OBJ | 0 | 8 |
| true | false | OBJ-R（診断専用） | 0 | 8 |

証跡は[native/checks.json](native/checks.json)、[native/disco_plain.json](native/disco_plain.json)、[native/disco_plain.stderr](native/disco_plain.stderr)。失敗はcallback実行前に再現し、今回の有限罰則callback分岐を実行しなくても発生する。Python tracebackが示すのはPyNomad.optimize呼出しまでで、C++内部の故障箇所は**未確認**。

リポジトリ内の既存[組込みhelp](../../../../nomad-wall/nomad-parameter-help.txt)の147–157、177–196、207–221行は、hidden constraintモードを無効にするとDiscoMADSが不連続性検出を使い、その検出出力に`-R`を指定すると説明している。これは設定/output宣言への依存を示し、今回の再現結果とも整合する。ただし、上流の実装原因やすべての条件での再現性を断定しない。

OBJ-Rでは目的値を不連続性検出の対象にするため、M045だけを外す介入の定義に影響する。今回は診断に留め、OBJ-R、DiscoMADS停止、代替backendへのfallbackをpatchに加えていない。実問題でのOBJ-R版も試していない。B045は現在のnative環境では異常終了する構成として残し、正常動作・介入の独立性は**未確認**とする。

## バイト一致・保護・制限

- BASE1、適用後、凍結版の通常ファイル一覧と生バイトSHA256をsource-hashes.jsonと照合。replayの全通常ファイルも適用後と一致（__pycache__除外）。BASE1へのpatch適用check、適用後への逆適用checkは成功。
- 最終検証・同定の12ファイルをBASE1・適用後・replay・S1凍結版の間で直接生バイト比較し、すべて一致。engine lockは保存済み全probe・正常終了workerで有効。
- 未設定B0と全フラグ値0の契約probe stdoutはBASE1と生バイト一致。これは決定的probeの範囲の確認であり、全問題・期限依存の全プロセス出力の一致証明ではない。各フラグは文字列`1`だけで有効になり、通常の数値式・既定設定は保持する。
- 前任の固定済みpatch、configs、source-hashes、入力、実行コードと既存receiptを保持。design.mdだけ行番号訂正と確認範囲を追記し、旧hashをpre-smoke-hashes.jsonに保存したままsmoke/checks.jsonに変更を記録した。
- 実問題smokeは内部3秒・watchdog9秒・親10秒、並列1。追加native切り分けも親10秒・並列1、内部スレッド各1、nice +15、CPU31、core dump無効。全追加子プロセスは0.12秒未満で回収。
- 外部ネットワークの取得・ダウンロードなし。S8/run-*の内容参照なし。本計測、正誤/桁数比較、commit/pushなし。書込みはswitches/以下のみで、大きなファイルは生成していない。sandbox内で完了し、権限昇格は使用していない。

最終成果物・制御receiptのhashは[completion-hashes.json](completion-hashes.json)。verify_preparation.pyは静的監査専用、native_check.pyは既存native/があれば再実行を拒否する。smoke_driver.pyも既存smoke/への再実行を拒否する。今回の制限内で可能な動作確認と未確認箇所の記録は完了。
