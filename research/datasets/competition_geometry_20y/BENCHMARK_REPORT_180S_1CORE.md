# DSL solver性能（180秒 / 1 core）

> **注意**: このファイルは自由度圧縮前の302件baselineを凍結した履歴artifactである。圧縮後の現行DSLは [`DOF_COMPRESSION_AUDIT.md`](DOF_COMPRESSION_AUDIT.md) を参照する。そこでは全302件が0--7変数、修正後39件を180秒/1 coreで再測定している。

`experiment` branchで、今回追加した競技幾何コーパス302 JSONを、固定runtimeのsolverに対して再計測した。既存の3秒/8並列結果（`benchmark_results.json`）は変更せず、この測定を別artifactとして保存している。

## 実行条件

```text
runtime: /home/kabatan/work/solver-experiment-runtime
seed: 7
budget: 180秒
subprocess wall timeout: 180秒（hard timeout）
jobs: 1
CPU affinity: [0]（taskset -c 0、runnerでも --require-one-core を検証）
```

各ケースはfresh subprocessで実行した。`wall_sec` はプロセス回収を含むため、hard timeout行は約180.106〜180.108秒となる。solver内部の探索予算だけを180秒にしたのではなく、外側のsubprocessにも180秒の上限を設定している。

## 全体結果

| 区分 | 件数 |
|---|---:|
| JSON / runs | 302 / 302 |
| 実行対象 | 285 files（279 unique） |
| `reference_only`（未実行） | 17 |
| `success` | 218 |
| `no_solution` | 38 |
| `timeout` | 25 |
| `exception` | 4 |

公開解答値がある行は全体212（実行対象206）だった。実行対象206行について、solverの代表解（`reported_answer`、なければ`selected_answer`）を公開解答値と数値比較した結果は次の通り。

| 判定 | 件数 | 分母 |
|---|---:|---:|
| 代表解が期待値に一致（`answer_match`） | 139 | 206 |
| 期待値集合を少なくとも全て含む（coverage） | 120 | 206 |
| 期待値集合と厳密一致（余分な候補なし） | 112 | 206 |
| coverageは満たすが余分な候補がある | 8 | 206 |

従来の`answer_set_complete`は「期待値がaccepted list内に全て現れる」というcoverage判定で、余分な候補を除外しない。今回の`answer_set_exact`は同じ数値許容誤差で双方向に比較し、余分な候補も不一致とした。例えばHMMT-2010-FEB-GEO-09は`70;160`に対して`70,160,180`を返すため、代表解・coverageは成功でも厳密集合は不一致になる。

## 競技別

| 競技 | files | success / no_solution / timeout / exception / reference | 期待値あり | 代表解一致 | coverage | 厳密集合 |
|---|---:|---:|---:|---:|---:|---:|
| AIME | 108 | 67 / 20 / 13 / 2 / 6 | 108 | 47 | 26 | 23 |
| HMMT | 135 | 107 / 13 / 5 / 0 / 10 | 90 | 85 | 87 | 84 |
| JMO予選 | 59 | 44 / 5 / 7 / 2 / 1 | 14 | 7 | 7 | 5 |
| **合計** | **302** | **218 / 38 / 25 / 4 / 17** | **212** | **139** | **120** | **112** |

HMMT/JMOのfiles数には、同一問題を別source rowとして保持した監査済み補助別名が含まれる。問題定義・`source_statement`・DSLはこの計測のために変更していない。

## Artifactと検証

- 生のrunner出力（solverのraw値・phase-c候補を保持）: [`benchmark_results_180s_1core.json`](./benchmark_results_180s_1core.json)
- coverage/厳密集合を付加した評価結果: [`benchmark_results_180s_1core_evaluated.json`](./benchmark_results_180s_1core_evaluated.json)
- 再検証スクリプト: [`validate_benchmark_180.py`](./validate_benchmark_180.py)

検証結果は `302 cases`、statusは `success=218 / no_solution=38 / timeout=25 / exception=4 / reference_only=17`、CPU affinityは `[0]` で一致した。既存の3秒結果は [`benchmark_results.json`](./benchmark_results.json) にそのまま残している。
