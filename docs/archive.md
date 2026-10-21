# 整理した研究資産と過去の評価記録

`research`には最新版solver、GMB実行環境、solver用323問とGMB比較評価、それらの検証・説明を残しています。
学習実験と過去の測定結果は、既存の`experiment`ブランチへ保存しています。

## GitHubで参照できる評価・分析資料

[experimentの資料索引](https://github.com/kabatan/geosolver/tree/experiment/research-archives/solver-evidence)に、10月11日の性能改善・不採用の高速化追試と、9月の機構分析から再利用する報告・集計・再現コードをまとめました。各ファイルの元の保存先とSHA-256は`import-manifest.json`にあります。
公開資料の保存commitは`7b6691be8d8a15a7a95816b532cad06cc2819112`（experiment）です。

生成88入力は[researchの追加benchmark](../benchmarks/generated-88/README.md)へ取り込みました。自然問題323問と分けて評価でき、正解の導出・凍結記録も含みます。取り込み時には求解を行っていません。

大きな生ログ・途中状態・環境はローカルの保存先に残しています。experimentの索引には、Gitで取得できる資料とローカル限定資料の範囲を記載しています。歴史的な報告の性能値や実装hashは、各実験当時の実装を指します。

## 2026-10-21の整理

保存commitは`052a4771f`（experiment）です。入口は`experiment:research-archives/2026-10-21/README.md`です。

```bash
git show experiment:research-archives/2026-10-21/README.md
git show experiment:research-archives/2026-10-21/snapshot/README.md
```

- `snapshot/`：整理直前の作業版。未コミット・未追跡のsolver改善、Qwen、Humpty、研究メモ、専用テストを含む。
- `snapshot-manifest.json`：元commit・作業状態と各ファイルのSHA-256。
- `working-tree.patch`と`index.patch`：整理前の変更。
- `local-manifest.json`：repo外へ移したローカル資産と移動検証。
- `validation-before.json`と`validation-after.json`：整理前後の検証記録。

このPCの保存先：

```text
/home/kabatan/work/solver-experiment/research-archives/2026-10-21/
```

Git対象外の環境・ログ・checkpoint・旧評価記録は同所の`local/original-tree/`にあります。
これらはcloneでは復元されません。移動前の絶対パスや仮想環境のshebangは履歴として保持しており、移動先での環境再利用には再構築が必要な場合があります。
共有モデルキャッシュは移動していません。

10月11日の性能報告は`snapshot/README.md`、生の記録は`local/original-tree/benchmarks/local-evaluation/optimization-20261011/`と`optimization-speed-20261011/`に保存しています。
記録内のhashは整理前のソースを指します。現在のソースの性能測定として流用しません。

## 2026-09-08以前

過去のsolver改善・GMB計測／比較・整理履歴の入口は、引き続き`experiment:research-archives/2026-09-08/README.md`です。

```bash
git show experiment:research-archives/2026-09-08/README.md
```

Git対象外の生データ：

```text
/home/kabatan/work/solver-experiment/research-archives/2026-09-08/local/benchmarks/local-evaluation/
```

benchmarkの出典・参照・入力監査資料と、再利用するrunnerはresearchに保持しています。
