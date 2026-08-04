# 一般互換修正後の性能測定（180秒 / 1 core）

`experiment` branch のDSLを、個別ケースの式置換ではなく、公開geometry APIと高精度(mpmath) backendの共通境界を修正した上で再測定した記録です。

## 条件

```text
runtime: /home/kabatan/work/solver-experiment-runtime
seed: 7
budget: 180秒
外側hard timeout: 180秒
jobs: 1
CPU affinity: [0]
```

全302 JSONをfresh subprocessで実行しました。結果は
[`benchmark_results_180s_1core_after_general_fix_final.json`](benchmark_results_180s_1core_after_general_fix_final.json) に保存しています。AIME-2011-II-10は、全走査後に`%1000`の一般化したpresentation formatterを反映して同条件で再実行し、AIME-2021-I-11は`AssumeConvex`追加後に同条件で再実行して、それぞれの行を置換しています。

## 集計

| status | 件数 |
|---|---:|
| `success` | 259 |
| `no_solution` | 16 |
| `timeout` | 8 |
| `exception` | 2 |
| `reference_only` | 17 |
| **合計** | **302** |

現行IRで実行可能な285 filesのうち、公開解答があり`reference_only`でない206件では次の結果です。

| 判定 | 件数 |
|---|---:|
| 代表解が期待値に一致 | 181 / 206 |
| 期待値集合を全て含む | 135 / 206 |
| 余分な候補なしの厳密集合一致 | 122 / 206 |

contest別の代表解一致は AIME 88/102、HMMT 83/90、JMO予選 10/14 です。

## 一般化した互換修正

次の修正は、JSONの各問題を特別扱いするものではなく、公開DSLの呼び出し規約をbackend全体で受理するためのものです。

| 公開DSLの呼び出し | 共通backend修正 |
|---|---|
| `Line(a,b,c)` | 係数形式を高精度`MPLine`へ変換（ゼロ法線は明示的に拒否） |
| `Rotate(P, angle, center)` | 公開順序をcanonical化し、旧内部順序`(P, center, angle)`も境界で互換処理、center省略は原点 |
| `Tangent(P, circle)` / `TangentLine` | 接線リストを一つの線へ正規化し、別名の引数順も境界で受理 |
| `IncircleContactPoint(..., side="BC")` | `"BC"/"CA"/"AB"`、0/1/2、頂点別名を共通の辺pairへ正規化 |
| `Perimeter(P1,...,Pn)` | 3点固定のlegacy helperを廃し、任意のn点・Polygon/sequenceを巡回和として処理 |
| 数式中の`^` | Python AST生成前に`**`へ変換し、数学的な指数優先順位を保持（文字列中の`^`は変更しない） |
| singleton construction result | `Intersect`境界でsingleton list/tupleをunwrapし、構成の合成を安定化 |
| guard不成立の変数なし経路 | `phasec_result`を空のassembly resultで初期化し、未初期化参照を防止 |

実装箇所は外部runtimeの次のファイルです。

- `geosolver/src/geosolver/geometry/mp/mp_api.py`
- `geosolver/src/geosolver/geometry/mp/mp_api_geometry.py`
- `geosolver/src/geosolver/geometry/mp/mp_api_common_wrappers.py`
- `geosolver/src/geosolver/geometry/mp/mp_api_measurements.py`
- `geosolver/src/geosolver/ir/compiler_validation.py`
- `geosolver/src/geosolver/_internal/pipeline/orchestration/run_external_pipeline.py`

外部runtimeはこのGit worktreeの管理対象外なので、適用状態は
[`runtime_general_fix_manifest.json`](runtime_general_fix_manifest.json) のSHA256で固定しています。

自然な公開DSLに戻したAPI不一致ケース（AIME-2006-II-09、AIME-2007-I-12、AIME-2007-II-09、AIME-2020-II-04など）は、これらの共通修正後に実行可能になりました。JSON側で`Line`を別形式へ書き換える、引数順をケースごとに反転する、といった回避策は残していません。

## 回帰テストと監査

次の回帰テストは、上記の公開→高精度境界を一度に検査します。

```bash
PYTHONPATH=/home/kabatan/work/solver-experiment-runtime/geosolver/src \
  /home/kabatan/work/solver-experiment-runtime/solver/python/.venv/bin/python \
  runtime_api_compat_regression.py
# runtime API compatibility regressions: PASS
```

DSL監査も再実行し、`302 JSON / 548 source rows / 0 errors`、変数数は全件0--7、`reference_only=17`を確認しました。

```text
audit_rows=548, dsl_files=302, errors=0, runnable_files=285
variable_histogram={0:43, 1:39, 2:62, 3:55, 4:52, 5:23, 6:17, 7:11}
```

なお、AIME-2021-I-11は、問題文の「cyclic quadrilateral」の頂点順を表す`AssumeConvex([A,B,C,D])`を追加して意味を明示しましたが、代表解はなお`301`に一致していません。これはAPI互換問題が解消した後に残る数値解探索/枝選択の課題として、互換修正の成功とは分離して扱います。
