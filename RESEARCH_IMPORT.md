# 整理済みsolverと323問のresearchへの移植

2026-08-30。`research`の旧solverを整理済み最新版へ置き換えた。
アルゴリズム・探索設定・DSL・参照値の変更は行っていない。

この文書と`RESEARCH_IMPORT_MANIFEST.json`は移植commit `faf43a85`時点の記録。
その後の未使用補助関数の削除・MP backend接続修正は[追加整理記録](RESEARCH_CLEANUP.md)を参照。
移植時のhashを現在の値で上書きせず、現在の製品hashは`src/geosolver/engine-lock.json`で管理する。

作業場所はその後`/home/kabatan/work/solver`直下へ統合し、以下で述べる一時的なresearch worktreeは解消した。
元の未commit変更と資料の保全先は[現在の作業場所・旧資料](README.md#作業場所と旧資料)を参照。
以下の移植元・移植先パスは、移植当時の履歴として記載している。

## 移植元と保全

- 移植元：`/home/kabatan/work/solver`、`codex/solver-hardening`。
  HEADは`c079b134d018a20a780639d3b88ba947ad5bc31c`だが、**その後の未commit修正を含む作業ツリー**を移植した。
  HEADだけをcheckoutしても今回の版にはならない。
- 移植前の`research`：`a3a915f1dcb97674240b4bcb6b03afcf9ae1e773`。
  `codex/research-before-import-20260830`を復旧用に残した。履歴のreset・書換えはしていない。
- 移植先worktree：`/home/kabatan/work/solver-wt/research`。
  元の作業ツリーはブランチ・未commit変更・過去artifactを含めて維持した。

[機械可読の移植台帳](RESEARCH_IMPORT_MANIFEST.json)に、変更せず移植した555ファイルのSHA-256と版識別を記録した。
Git履歴は共有しているので、これは作業ツリー・以降のcommitの整理であって、過去のGit objectを削除する操作ではない。

## 収録範囲

- `src/geosolver/`：219 Pythonファイルと5つのspec/schema/lock JSON。全224ファイルが移植元とbyte単位で一致。
- `benchmarks/dsl/`：323問。全ファイルが移植元とbyte単位で一致。
- `benchmarks/cases.jsonl`：埋込DSL・参照集合・出典・修正来歴をそのまま維持。
- 回帰テスト、独立な配置の検算、DSL・参照値の整合性検査。
- 正式な`research_runner.py`と、過剰並列の負荷診断用`stress_runner.py`。
- Python依存lock、CI、wheel確認、engine lock更新ツール。
- 最新の研究計画、原文照合・修復・重複除去の小さな台帳。

旧HTTP/UI・frontend・Julia・旧solver、約1GBの`local-evaluation/`、一時診断、
旧入力を再生成する一度きりの移行・修復コマンド、PDF、cache、build出力は移植対象外。
旧researchにあった不要ファイルは今回の置換commitで削除し、以前の履歴から復旧できる。
今後の`benchmarks/local-evaluation/`と`benchmarks/diagnostics/`はGit追跡対象外にした。
実験結果はrunnerのmanifest・SHA256SUMSとともに別途保存する。

## テスト資産の独立化

大容量の古いcampaignへの依存をなくすため、誤受理された2候補の座標と、独立に求めた12配置の代入式だけを
[`tests/fixtures/`](tests/fixtures/README.md)へ抽出した。元データの文字列を丸めず保持し、元artifactのSHA-256も記録した。
期待結果を古い実行結果から読み込むことはせず、各テストで再検証する。

修復済み入力の旧再生成器は読み取り専用の`records.py`へ置き換えた。
現在のDSL・参照値は`cases.jsonl`を使い、削除済み問題は監査用に明示的に読む場合に限り参照する。
原文・修復前後hash・重複・正しい配置・境界誤受理の検査は維持した。

元の299テストのうち、移植しないコマンドを対象とする次の3件のみ除外した。

- `test_staging_repairs_does_not_restore_removed_case`
- `test_legacy_reimport_refuses_to_overwrite_repaired_corpus`
- `test_apply_repairs_does_not_reintroduce_archived_aliases`

残る296件を実行し、全件成功した（111.23秒）。この所要時間は性能比較値ではない。

## 確認結果

- `uv sync --all-extras --frozen --offline`で移植先専用venvを構築。
- `python -m pytest -q -o addopts= -p no:cacheprovider`：296件成功。
- `research_runner.py validate`：inventory・DSL・runnable・truth verified・自然問題がいずれも323、issuesなし。
- engine lock・実import元・runtime依存の照合：成功。
- Ruff、Python構文、schema `--check`、独立processのimport：成功。
- Linuxでwheelを新規buildし、repo外の別venvへインストール。
  `doctor`、`sqrt(2)*pi+sqrt(3)`、`sqrt(2)+1e-110`、変数のある`x=2`問題の公開API実行に成功。

版識別は移植前後で同一。

| 対象 | SHA-256（`sha256:`接頭辞省略） |
|---|---|
| solver source | `3992894ba012da1f0b43c219b04a860ba29b3307f1bdc8cbfb0f9db88abcf678` |
| resolved config | `01d7484acce36b57593029e5fcff7f60110f5daf201f5b68499cd524d6c23df2` |
| dependency lock | `89449168db266c6414a6377be9ac90832624d1b340f558b0305872d6f22d53d5` |
| cases.jsonl file | `c5f92269783add80779a38b4159f298b7f49300386bca0008bb02d3c82d3fccb` |

今回は移植の検証であり、323問全件の新たな探索評価・Windows/macOS実機確認は行っていない。
全問成功や完全性の保証ではなく、323問は既に開発に使った集合である。
`solver-a0`等のfreeze tag作成、pushも行わない。

## 以降の作業

```bash
cd /home/kabatan/work/solver
uv sync --all-extras --frozen
uv run geosolver doctor
uv run python benchmarks/research_runner.py validate
```

正式実験はrepo直下の`research`ブランチのclean treeで実行する。別worktreeは不要。
