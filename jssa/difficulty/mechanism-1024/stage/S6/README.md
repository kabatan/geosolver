# S6：事前登録13の実行前準備

本計測は未実行。solver、seed 501〜503、探索、精密化、最終検証、同定を実行していない。git commit/pushもしていない。事前登録のpush手順は今回の明示指示に従って実施せず、ローカルのSHA-256記録を残した。

## 固定した成果物

| ファイル | 内容 |
|---|---|
| `targets.json` | 44問。S3の12問＋S5の32問。開発群のIsTangent 24問はすべて既に含まれ、追加0問。重複は正規化IDで一つ |
| `select_targets.py`, `selection-audit.json` | 選定コード、開発群全走査ファイルのSHA-256、出現元・条件位置。成否による追加・除外なし |
| `groups.json` | 接点効果群6問、同式群33問、その他5問。接点効果群を優先 |
| `classify_groups.py`, `grouping-evidence.json` | 保存されたS3先頭候補のバイト・式一致、または実装の純粋な構文ヘルパーによる接点式有無の判定。判定コード・原文・ハッシュ |
| `switch-scope.md`, `switch-scope-evidence.json` | フルプロセスで環境変数を継承する経路、直接・間接の呼出グラフと結論、未適用の最小変更案 |
| `source-hashes.json` | `/tmp/s3-impl/src/geosolver` 全ファイルのSHA-256と指定source_hashの一致 |
| `reference-sources.json` | 既存の正解参照式の出所・ハッシュと有無。評価や新しい正解計算はしていない |
| `run-plan.json` | 44問×3seed×2構成＝264ジョブの**計画**。起動コードではない |
| `preparation-hashes.json` | 入力・準備コード・文書・計画のハッシュ、静的整合性検査結果、準備に使用したPythonの識別 |

接点効果群はS5分類の `type=P` の2問（HMMT-2014-FEB-GEO-08、JMO-2014-PRE-01）と、明示されたAIME-2018-II-14、JMO-2013-PRE-05、JMO-2024-PRE-06、HMMT-2023-FEB-GEO-07。
`measurement_type=P` でも `type=不定` の問題はPとして追加しない。

**監査上の制限：** 最終検証のランク選択ヘルパーはT1を読まず、最終検証の数式は切り替わらない。ただし、指定の「T2に接点式なし」で同式群になる15問は、T1固有の非接点Distance書き換えによって実際の式が異なる。33問すべてを式一致の対照群と解釈できない。群は指定どおり固定し、この15問を明示した。さらに完成したsolverの追加探索・候補選択には精密化からの間接効果がある。詳細と最小変更案は `switch-scope.md` を参照。

## 将来のdriver設計（設計のみ・起動禁止）

このディレクトリに本計測を起動する `driver.py` は作成していない。以下は将来の実装仕様であり、本作業では実行しない。

### 入力・構成・順序

- 入力は `targets.json` の正規化identityの辞書順。代表DSLをそのまま使い、候補が作れなかった問題・参照解なしの問題も含めて全44問を走らせる。対象・群を結果で変えない。
- 構成T2は `GEOSOLVER_S3_TANGENCY_MODE` 未設定。T1は同変数を `T1`。コードは両方とも `/tmp/s3-impl/src`、source_hashは `sha256:add5afaf829806ca3cbd11fb07b69d956102752e1c6738b0630581a3ceb121eb`。
- seedは501、502、503の昇順。固定キューは**問題→seed→構成**の順。問題indexをi、seed indexをj（ともに0始まり）とし、`(i+j)%2==0` はT2→T1、他はT1→T2。132対のうち66対ずつ。全264ジョブを省略せず実施する。
- `run-plan.json` に固定キューの全順序・環境変数の差分を保存した。順番は結果・所要時間・群によって変えない。未実装driverはこのキューをFIFOで起動する。

### プロセス・資源

- 完成した通常solverの公開入口 `geosolver.application.cli:solve` を新しいフルプロセスで呼ぶ設計。精密化のみのS3/S5 workerは流用しない。CLI引数は問題ファイル、`--time-limit-seconds 180 --cores 1 --seed <seed>`、構成別の出力パス。
- 全ジョブで `PYTHONPATH=/tmp/s3-impl/src`、`PYTHONDONTWRITEBYTECODE=1`。研究用 `GEOSOLVER_*` の親環境は除去し、予定したモードだけを加える。通常solverが内部で設定する変数は維持する。`GEOSOLVER_ABLATE_*` はすべて未設定。他の設定・精度・候補数は既定のまま。
- `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`, `NUMEXPR_NUM_THREADS`, `VECLIB_MAXIMUM_THREADS`, `BLIS_NUM_THREADS`, `OMP_THREAD_LIMIT` をすべて1にする。
- 将来のdriver起動時の `os.sched_getaffinity(0)` を昇順で取得し、先頭の `min(12,利用可能CPU数)` コアをslotに割り当てる。slotごとに同時に1ジョブ。各子を `taskset -c <slot CPU>` 相当で**起動前から**1コアに固定する。worker・symbolic workerを含め子孫のaffinityも同じ1コアを継承する。通常runnerの `set_affinity` も継承されたeligible CPUの先頭を使う。
- 最大12フルsolverプロセス。スレッドを含め各ジョブは1コア・内部1スレッドで、slotのCPUを同時共有しない。子孫PID、実affinity、スレッド環境、peak RSSを実行ログに残す。資源契約違反を検出したジョブは失敗として別記し、自動再試行しない。
- 各フルプロセスの計算上限は180秒。親のmonotonic時計で起動直前から計時し、180秒でプロセス木を停止する。cleanup待ち（最大2秒）は採点時間に含めず、180秒後の計算結果は受理しない。内部の既定予算配分は変更しない。起動・通常終了を含む親のwall timeをC用に保存し、solver報告のelapsedも別列に残す。
- 理論上の総上限は47,520コア秒（13.2コア時間）、12並列の理想値は3,960秒（66分）。共有機負荷・起動・cleanupで実時間は増え得る。キュー待ち時間はCに含めない。

### 採点と費用C

正解判定はsolverの `status=solved` だけでは決めない。返された**答え集合全体**を独立参照集合と照合し、余分な答え・不足・異なる値が一つでもあれば不正解。集合の順序や重複には依存しない。代数的数は正規化した最小多項式と実根index、affine-piは係数と定数の正規化表現で照合し、同値表現を数学的に正規化する。小数の許容誤差だけで「完全一致」にしない。採点は計算時間計測の外側で行い、真値をsolverへ渡さない。

問題p・構成a・seed sの完全一致を `ok[p,a,s]` とすると、

```text
solved[p,a] = sum(ok[p,a,s] for s in [501,502,503]) >= 2
C_seed[p,a,s] = wall_seconds[p,a,s] if ok[p,a,s] else 180
C[p,a] = sum(C_seed[p,a,s] for s in [501,502,503]) / 3
```

成功したseedごとの集合が**同じ独立正解集合**に完全一致することが条件。多数決で一致した誤答は成功にしない。timeout・crash・候補なし・不一致・資源契約違反はすべてseed費用180秒で、理由を別に記録する。起動失敗・成果物欠損も黙って再実行しない。

`reference-sources.json` はS3の既存manifestとS5の入力メタデータにある参照式を静的に固定したもの。HMMT-2013-FEB-TEAM-03、HMMT-2022-FEB-TEAM-03には既存の参照式がない。候補生成・solver成功の有無とは別の欠測であり、除外や不正解への置換はしない。将来の正解採点には、これらの独立した正解集合を本計測前に固定する必要がある。参照が未確定のままなら成功/Cを確定できないと記録する。今回、新たな参照計算はしていない。

V1は接点効果群で `mean(C_T1)/mean(C_T2)>=1.5` またはT2で解けT1で解けない問題が1問以上。
V2は同式群で成功問題数差が±1以内、かつ `mean(C_T1)/mean(C_T2)` が0.8〜1.25（境界を含む）。
V3は全体でT2のみ成功の数がT1のみ成功の数以上。
費用平均は各群の全固定問題で等重みとし、欠測があれば勝手に分母を減らさず確定不能を明示する。V2は上記15問の介入不整合を伴うため、そのまま式一致の対照実験とは主張しない。予測を事後に書き換えない。

### 記録・再開・事前照合

各ジョブは一意キー `(identity, seed, mode)` を持ち、排他的な開始receipt→stdout/stderr/resultの原本→終了receiptとSHA-256を保存する。既存キーを上書きせず、再開時も開始済みで未完了のジョブは中断として残す。自動再実行・成功時の残りseed省略はしない。開始時刻、終了時刻、PID木、CPU、mode、実際のenv、Python実体hash、source_hash、入力hash、終了コード、wall time、参照集合hash、答え集合、完全一致判定、Cを記録する。

実行前には `preparation-hashes.json`、`source-hashes.json`、全入力hash、Pythonと依存lock、将来作成するdriver・採点コード・正解集合のhashを照合・固定する。異なれば自動的に別実装へ切り替えず停止する。現在は準備のみのため、実測用driver・採点コードのhashや実行receiptは存在しない。

scope監査で挙がった介入の不整合を解消する場合は、変更コード・source_hash・登録の説明を改めて固定してから将来の本計測へ進む。このREADMEや準備スクリプトから本計測を自動起動することはない。

## 今回実行した準備の再現

以下はJSON・ソースを読む準備だけを実行する。製品モジュールはimportせず、`classify_groups.py` が抽出するのはAST・文字列処理だけである。既存のpickleはdeserializeせずハッシュだけ照合する。`check_stage1.py` 自体は実行しない。

```text
python3 -B stage/S6/select_targets.py
python3 -B stage/S6/classify_groups.py
python3 -B stage/S6/audit_switch.py
python3 -B stage/S6/finalize_preparation.py
```

パスは `jssa/difficulty/mechanism-1024/` を基準とする。対象・群・ソースは内容hashで固定される。準備manifestの時刻・環境情報は再作成時に更新される。
