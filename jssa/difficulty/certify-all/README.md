# Q11 certify-all

最終報告は [answer.md](answer.md)。本計測返答JSONの不在により、保存された局所探索終点を用いた参考測定である。全343問を試行し、73問の候補集合を認証した。実行前hashは `runs/run-manifest.json`、元ソースのhashは `input-manifest.json`。

## 再現

リポジトリのルートから実行する。Python環境やsrcを変更しない。環境変数はthread数を抑え、補助変数生成順序を再現するために必要。

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src PYTHONHASHSEED=0 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/certify-all/run.py --dest replay
```

全343問の同一入力を新しい `replay/` に実行する。既存resultがあれば上書きを拒否する。最悪約86分、仮想メモリ最大3 GiB×4。保存された `inputs/` を使えば公式解を含む元caseファイルを読む必要はない。`prepare.py` はDSLと保存数値終点を抽出するが、保存済みmanifestを書き換えるため通常の再現には不要。

保存結果の再検算：

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src PYTHONHASHSEED=0 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /home/kabatan/work/solver/.venv/bin/python -B jssa/difficulty/certify-all/verify_results.py
```

`validation.json` を再出力する。小さい恒等式は生データで再検算し、ハッシュのみの2件は再生成する。この時間は元の60秒計測に加えない。記録済み検算では120問・132恒等式すべて一致した。

## ファイル

| ファイル | 用途 |
|---|---|
| preregistration.md | 成功定義、中止閾値、60秒、資源・保存上限 |
| protocol-details.md | 実行前に固定した採用規則、段階予算、欠測の扱い |
| input-manifest.json / inputs/ | 全343問の来歴・hash、答えフィールドを除いた入力 |
| prepare.py | 採点ラベルを使わない保存終点の抽出 |
| worker.py | Lの数値関数・PSLQ・代数化・証明生成・Fraction検算を再利用 |
| bounds.py | 元DSLの明示条件と保守的な有理数区間演算 |
| run.py | 最大4 worker、1問60秒、3 GiB、単一ファイル8 MiB |
| result_paths.py | 障害回復リストに従う採用resultの解決 |
| per-case.csv / summary.json | 最終採用343件の全問表・集計 |
| verify_results.py / validation.json | F・s・hash・恒等式・根集合の再検算 |
| semantic_audit.py / semantic-audit.json | 直線の向き・角二等分線の例外枝の監査 |
| self_check.py / self-check.json / synthetic-check/ | 実験前の合成DSL検査。343問の計測には含めない |
| recovery-plan.json / recovery2-plan.json | パス不在障害だけを再実行した固定リスト |
| recover.py / recover_second.py | 障害回復に用いたコード。既存planを上書きしない |
| artifact-manifest.json | 最終成果のサイズ・hash一覧 |

`per-case.csv` の `result_path` が採用原票。`runs/` には障害時の途中記録もあるため、全resultを単純合算しない。`summarize.py` は各問1件だけ採用する。新たに実行した `replay/` を既存の測定結果へ自動合算することもない。

## 再利用と保証範囲

Lの `certificate.py`、`vendor/algebraize.py`、`vendor/run_exact.py`、`verify_certificate.py` を読み取り専用でimportする。`experiment.py` は `polish`、`pslq`、`evaluator`、`hard`、`zero_dim` の関数定義だけをASTから読み、Lの実験mainやファイル操作は実行しない。`audit_source/` とLのanswerは設計・既存証明の意味の監査に利用し、新規workerの答えの供給元にはしない。

Fは元の条件の代数的な緩和。符号・不等式を捨ててできる余分な枝は元DSL由来の目標値域で除き、残れば失敗とする。図の厳密存在証明、原文→DSLの正しさ、形式検証済み変換器、Singular/msolveによる速度比較は対象外。本計測原票が得られれば、保存返答の抽出を置き換え、同じ基準で主測定を行う必要がある。
