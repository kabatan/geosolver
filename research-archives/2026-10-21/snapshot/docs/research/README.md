# 研究開発ガイド

現在の目的は、**解法を知らなくても生成できる数値データから、モデルが未提示の幾何的関係の発見・証明・補助点利用へ転移できるか**を調べる学習実験です。
題材はHumpty点周辺（中線・垂心・二接円、直接つながるDumpty・等角共役を含む）で、SD周辺は別実験として分離します。
solver pipeline · Qwen3-4B環境 · DSL/GMBベンチマーク · 学習・評価セットが現行の管理対象です。

## 配置と役割

| 場所 | 役割 |
|---|---|
| [`src/geosolver`](../../src/geosolver) | 幾何solver本体。固定版は`solver-a1` |
| [`qwen/`](../../qwen/README.md) | 固定したQwen/Qwen3-4Bの環境・モデルlock・診断・単発推論。solverとは別のPython環境 |
| [`benchmarks/cases.jsonl`](../../benchmarks/cases.jsonl) と `benchmarks/dsl/` | 幾何323問。開発使用済み |
| [`gmb`](../../benchmarks/gmb/README.md)・[`gmb_comparison`](../../benchmarks/gmb_comparison/README.md) | GMB独立環境・比較入力・runner・入力監査資料 |
| [`humpty_configurations_v2`](../../benchmarks/humpty_configurations_v2/README.md) | 学習用求値セット v2：主学習37問・確認用3問・留保/延期/除外の判断・検証コード・レビュー画面 |
| [`humpty_proof_evaluation_v2`](../../benchmarks/humpty_proof_evaluation_v2/README.md) | 証明評価セット v2：転移3題・同配置3題・ヒント条件・採点基準・検証コード・レビュー画面 |
| `benchmarks/local-evaluation/` | Git対象外の実行出力・一時調査・ローカル保全物 |
| `tests/` | solver・benchmark・審査証跡の回帰検証 |

既存データのパスはhash台帳・manifest・検証コードが参照するため維持します。
参照値、証明、レビュー記録、解法をsolverや学習モデルの入力へ混入させないでください。
学習用と評価用の区分は各データセットのREADMEとmanifestが管理します。

## 研究メモ

現在の実験系（Humpty案）と過去の検討（SD案・報酬設計）を区別して保持します。

| 文書 | 内容 |
|---|---|
| [humpty-numeric-transfer-proposal-2026-09-20.md](humpty-numeric-transfer-proposal-2026-09-20.md) | **現行の実験計画書**。数値Q/Aから未提示の関係の言語化・証明・別配置利用までを一つの実験で追う設計 |
| [generic-geometry-judge-v1.md](generic-geometry-judge-v1.md) | 数学的価値（簡約・説明力）を評価する汎用judge案。J条件の報酬設計のたたき台 |
| [learning-transfer-replan-2026-09-19.md](learning-transfer-replan-2026-09-19.md) | 研究計画の再設計。目的の確認、旧案の問題点、9月の2条件・評価方針・日程 |
| [learning-transfer-geometric-reward-plan-2026-09-19.md](learning-transfer-geometric-reward-plan-2026-09-19.md) | 幾何的報酬の検討。簡約と説明力の評価基準、校正の進め方 |
| [learning-transfer-support-audit-2026-09-19.md](learning-transfer-support-audit-2026-09-19.md) | 旧SD実験の支持確認・judge監査記録 |
| [learning-transfer-discussion-2026-09-17.md](learning-transfer-discussion-2026-09-17.md) | 初期の相談記録（SD周辺の旧実験系） |

## 検証コマンド

リポジトリ直下から実行します。

```bash
uv sync --all-extras --frozen
uv run python -m pytest --import-mode=importlib
uv run ruff check src tests benchmarks qwen .github/scripts
uv run python benchmarks/research_runner.py validate
```

データセットの再生成・検証は各READMEの手順に従います。

```bash
python3 benchmarks/humpty_configurations_v2/build_dataset.py
.venv/bin/python benchmarks/humpty_configurations_v2/verify_dataset.py
python3 benchmarks/humpty_proof_evaluation_v2/build_evaluation.py
```

Qwen環境の構築・診断・推論は[qwen/README.md](../../qwen/README.md)を参照してください。

## 作業と履歴

通常の作業場所はrepo直下、ブランチは`research`です。solver変更、候補追加、レビュー証跡、整理は目的別のコミットにします。
一時スクリプトや実行出力は`benchmarks/local-evaluation/<campaign>/`に置き、再現に必要になったものは適切なpackageや審査shardに収録します。
固定tagと出典証跡を保持します。過去の実験結果はexperimentブランチへ保存します。
