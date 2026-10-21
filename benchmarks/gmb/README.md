# GMBの独立実行環境

GeoSolverを変更せず、公式GMBをLinux x86-64で実行するための環境です。
環境作成だけでは本評価用の問題を実行しません。
CPU計測用runnerを追加していますが、GeoSolverとの共通幾何検査器はまだ含みません。

## 論文39問の計測

過去の計測結果は `experiment` ブランチに移管しています。[保存先と閲覧方法](../../docs/archive.md)を参照してください。このディレクトリには再利用する実行環境・protocol・runnerを残しています。

条件と成功の意味は[PROTOCOL.md](PROTOCOL.md)を参照してください。
公開入力36問をそのまま実行し、表現非対応3問も集計に残します。
rootのPython環境（`psutil`を使用）から起動し、GMBは専用venvだけで実行します。

```bash
# 最初に人工問題で計測hookの座標不変性を確認（IMO問題は使わない）
.venv/bin/python -m benchmarks.gmb.campaign smoke benchmarks/local-evaluation/gmb-harness-check

# harness/protocolをcommitしてから、未使用の出力directoryへ条件・入力を固定
.venv/bin/python -m benchmarks.gmb.campaign prepare benchmarks/local-evaluation/gmb-imo39-baseline
.venv/bin/python -m benchmarks.gmb.campaign run benchmarks/local-evaluation/gmb-imo39-baseline
.venv/bin/python -m benchmarks.gmb.campaign summarize benchmarks/local-evaluation/gmb-imo39-baseline
# 必要な人間向け報告書を加えた後、全artifactをhash固定
.venv/bin/python -m benchmarks.gmb.campaign seal benchmarks/local-evaluation/gmb-imo39-baseline
.venv/bin/python -m benchmarks.gmb.campaign verify benchmarks/local-evaluation/gmb-imo39-baseline
```

既定はCPU4、1ジョブ、seed 0、各180秒。CPUは`prepare --cpu N`で変更可能です。
CPU番号は論理CPU番号で、1実行に許可する番号は必ず1つです。
`run`は完了済みrunを再実行せず、不完全なrunが残れば人の確認を要求します。
raw artifactはGit対象外です。確定した結果表・報告・SHA一覧はexperimentブランチ、生データは対応worktreeへ保存します。
既存campaignに対する別条件の再実行・結果上書きは行わず、別directoryを作ります。

### seedを変えた追加試験

既存のseed 0を変更せず、同じ`campaign.run_one`でseed 1・2を追加する処理です。
条件は[追加試験方針](REPLICATION_PROTOCOL.md)を参照してください。

```bash
.venv/bin/python -m benchmarks.gmb.replication prepare benchmarks/local-evaluation/gmb-imo39-replicates --baseline benchmarks/local-evaluation/gmb-imo39-baseline --seeds 1 2
.venv/bin/python -m benchmarks.gmb.replication run benchmarks/local-evaluation/gmb-imo39-replicates
.venv/bin/python -m benchmarks.gmb.replication combine benchmarks/local-evaluation/gmb-imo39-replicates --baseline benchmarks/local-evaluation/gmb-imo39-baseline
```

追加分だけの`summary.json`と、3反復の`combined-summary.json`を区別します。
報告書を追加した後は、既存の`campaign seal/verify`で追加campaignを固定・確認します。
`replication combine`を再実行すると、元の2campaignから3反復の集計が一致することを確認できます。

## 固定内容

- 公式実装：[rkruegs123/geo-model-builder](https://github.com/rkruegs123/geo-model-builder)
- commit：`f070afe18ed874b3a31db519ea6f593f40a1be00`。公式コードへのpatchなし。
- Python：3.8.20
- TensorFlow：2.7.4、NumPy：1.18.3、Matplotlib：3.2.1
- Flask：1.1.1、tqdm：4.46.0
- 全55依存：`requirements.lock`でversionと配布物のSHA-256を固定。

公式`requirements.txt`の5条件は全て満たします。
TensorFlowの公式指定は`>=2.4.0`ですが、2.4～2.6系列のNumPy条件は公式の
`numpy==1.18.3`と衝突するため、両方の公式条件を満たす2.7.4を採用しました。
Flaskの周辺依存も互換versionに固定し、環境検査専用に`packaging`を追加しています。
これは**公式条件を満たす再現用環境**であり、原論文の実験環境と完全同一という主張ではありません。

Python 3.8など古い依存を含みます。信頼できる研究用DSLをローカルで実行する用途に限定し、
付属HTTP serverを公開しないでください。仮想環境による依存の分離であり、OSのセキュリティsandboxではありません。

## 使い方

repo直下で実行します。起動用Pythonには標準ライブラリしか必要ありません。
実際のGMBは必ず専用のPython 3.8で起動します。初回のみ`uv`、`git`、ネット接続が必要です。

```bash
python3 benchmarks/gmb/environment.py setup
python3 benchmarks/gmb/environment.py doctor
python3 benchmarks/gmb/environment.py smoke
```

- `setup`：固定commitを取得し、専用venvへhash検証付きで依存を導入。その後`doctor`を実行。
- `doctor`：Python・全依存・公式要求・CPU affinity・GPU無効化・GeoSolverとの分離を検査。
- `smoke`：自作の二等辺三角形＋中点の入力で、parse・graph構築・最適化・座標取得を確認。
  競技問題や今後の予備5問・本評価集合には含めません。緩い数値確認であり、正式な共通検査器ではありません。

個別のGMBLを公式CLIで実行する場合：

```bash
python3 benchmarks/gmb/environment.py run benchmarks/gmb/smoke.smt2
python3 benchmarks/gmb/environment.py --cpu 2 --timeout 180 run /absolute/path/problem.smt2 -- --n_models 1
```

CPUは現在許可された番号から一つを選びます。省略時はその最小番号です。
**並列で起動するときは、異なる物理コアに対応するCPU番号を明示してください。**
この起動器自体にはjob配分機能はありません。

GPUを無効にし、TensorFlow・BLAS等のthread数を1に固定します。
描画は非対話型、途中のplotは無効にします。探索・学習率等の既定値は変更しません。
`run`の成功exit codeは公式CLIの正常終了だけを意味し、有効配置発見の判定には使えません。
この単発起動器にはseed制御・座標保存・集計はありません。これらは上記`campaign`で行います。
共通の独立幾何検査器はまだ含みません。

## 配置と安全な運用

Git追跡するのは、説明・起動器・計測実装・依存定義/lock・人工smoke入力・lint設定と、
小さい計測結果・manifest・checksum一覧です。GMB本体・venv・大量のrawデータは含めません。
以下はすべてGit対象外の`benchmarks/gmb/.runtime/`に置きます。

- `source/`：固定した公式sourceの独立checkout。solverのworktreeではありません。
- `venv/`：GMB専用venv。repo直下のGeoSolver用`.venv`は変更しません。
- `runs/<mode>-<unique>/`：実行ごとのstdout・stderr・環境記録・一時作業領域。

GMBはカレントディレクトリの`.checkpoints`を削除・再作成するため、起動ごとに別の作業領域を使います。
過去logは上書きしません。既定の外側timeoutは180秒で、超過時はその実行のprocess groupだけを停止します
（終了処理のため最大約2秒の猶予）。これはGeoSolverの正式deadline契約とは別です。
公式sourceが変更されていた場合は起動を拒否します。

環境の再作成は上の`setup`を使います。通常はlockを再解決しません。
意図して依存を更新するときだけ、次を実行し、`doctor`と`smoke`を再確認します。

```bash
uv pip compile benchmarks/gmb/requirements.in --python-version 3.8 --python-platform x86_64-manylinux_2_17 --only-binary :all: --generate-hashes --output-file benchmarks/gmb/requirements.lock
```

2026-08-31にLinux上で`doctor`、自作smoke、公式CLI経由の同じ入力を確認後、
上記IMO集合の計測を実施しました。別途予定しているE1未使用問題の評価は行っていません。
