# 確認記録

2026-10-24 JST、10:38頃開始、10:50頃完了（約12分、2時間以内）。solverは逐次実行。昇格・ネットワーク操作なし。共有worktreeのsrcへの書込み、このリポジトリでのcommit/pushなし。

## 土台と差分

先に読んだもの：`inventory/switches-priority.md`、`run-7/jssa-ablation-67ad79a-vs-60db4b6.patch`、`capability-1024/ablation34/ablation34_driver.py`、`results/mechanism-attribution/README.md`。設計資料の最終検証変更案は今回の指定に従って採用しなかった。既存スイッチと同じ `runtime.ablation.ablated()` を使った。

開始時に `/tmp/switch-impl` が既存だった。既存物は `/tmp/switch-impl.preexisting-20261024-0139` に退避した。退避側には開始直後に適用した既存patchとBASE1コミットが残るが、納品用の土台としては使っていない。新しい `/tmp/switch-impl` では指定どおりsrcだけを展開し直した。

```sh
mkdir /tmp/switch-impl
git -C /home/kabatan/work/solver archive 60db4b6 src | tar -x -C /tmp/switch-impl
cd /tmp/switch-impl
git init
git add src
git -c user.name='Switch Implementation' -c user.email='switch-impl@localhost' commit -m 'BASE0 frozen 60db4b6'
git tag BASE0
git apply <wt>/jssa/difficulty/mechanism-1024/run-7/jssa-ablation-67ad79a-vs-60db4b6.patch
git add src
git -c user.name='Switch Implementation' -c user.email='switch-impl@localhost' commit -m 'BASE1 existing Windows ablation switches'
git tag BASE1
# 新スイッチを実装し、確認後に最終コミット。
git diff --no-ext-diff --binary BASE1 HEAD -- src > <wt>/jssa/difficulty/mechanism-1024/switches/new-switches.patch
```

CRLF警告は発生せず、`--ignore-whitespace` は不要だった。ローカルの3コミット：

```text
42e5be12a7944c9a7cd2b48a8b41427ffba5e585 BASE0 frozen 60db4b6
f01efc14f07e8d1fcfd0d4cb097893dd5f40f2cf BASE1 existing Windows ablation switches
3cf08aad904c79b0e7f9b8394d3aa7f7933f9cce Add residual rewrite and diverse selection ablation switches
```

BASE1→最終版は11ファイル、99行追加・10行削除（救済の既存選択をelseへ移した7行とlockの2行を含む）。patchは15,064 bytes。SHA-256：`ed69a17d9155dc7718a84a91ab7451291bb02a40333b17f6366dc87aaa21f0df`。

## (a) OFF時の既存処理、integrity、最終検証

`/tmp/switch-check/audit.py` で、新スイッチをFalseとしてASTを簡約し、条件付きの空kwargsを除いた。追加import、スイッチ名宣言、引継ぎ用の内部フィールドも除外した上で、既存Pythonファイル9件すべてがBASE1と構文一致。追加helperはimport・関数定義だけで、import時に選択処理を実行しない。目視でも既存処理の計算式・閾値・予算変更なしを確認した。

候補の引継ぎには `SearchBatchResult.refinement_selection_pool` を追加（既定None、repr/equality対象外）。ONのときだけ設定・伝播し、探索途中の `candidates` を変えずに最終境界で置き換える。これによりhybridの初期値や広い救済台帳を維持する。`all_records`・`guard_feasible_ledger` は保存。主探索・第2探索の各stageと救済新規バッチに適用し、精密化済み候補の結合や離散ターゲット補完を20個へ再圧縮しない。

`NO_RESIDUAL_REWRITE` は精密化の共通入口と `requires_smoothing` の採用条件だけを変更。整数closureの分岐、通常の解析微分、元の残差による認証は共通。最終検証2ファイルはBASE0とバイト比較して不一致0：

| ファイル | SHA-256 |
|---|---|
| verification_numerics.py | `e781e0e5a0318e0941e596294c51b80ed6e6c2f2f24d6fc3607a039c8390b67f` |
| final_verifier.py | `64351d787c7ffcb2637d95b3e8d6a2e7077e5d9d9a222e965a80be6751366e3a` |

source hashは `runtime/integrity.py:source_tree_hash()` を使用（相対名、NUL、LF正規化本文、NUL、engine-lock除外）。

| 版 | source_hash |
|---|---|
| BASE0 | `sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5` |
| BASE1 | `sha256:e2115f553d6a59d6d85a30413e5719992c09e376d23d3e3e124fd07fd135b8ee` |
| 最終版 | `sha256:03a44bfbb743b972d95306c63a14c04b78c7d12b96a1ba83d147c56eea7f86a3` |

engine-lockは `source_tree_hash` と `engines.standard.hash` の2値だけ更新。resolved_config_hash、dependency_lock_hashなどは維持。最終版と再適用版の `verify_engine_lock()` は `(True, 最終版source_hash)`。

凍結版d8fd9bb8…との差分ファイル一覧（BASE0→最終版、既存patch分を含む）：

```text
src/geosolver/engine-lock.json
src/geosolver/engine/standard/contracts/candidate_record.py
src/geosolver/engine/standard/orchestration/run_external_pipeline.py
src/geosolver/engine/standard/orchestration/run_rescue_search.py
src/geosolver/engine/standard/orchestration/run_search.py
src/geosolver/engine/standard/refinement/analytic_jacobian.py
src/geosolver/engine/standard/refinement/mpmath_refiner.py
src/geosolver/engine/standard/search/algebraic_branches.py
src/geosolver/engine/standard/search/nomad_backend.py
src/geosolver/engine/standard/search/residual_selection.py
src/geosolver/engine/standard/search/scalar_branch_scan.py
src/geosolver/engine/standard/search/scale_chart.py
src/geosolver/engine/standard/search/scipy_multistart_backend.py
src/geosolver/runtime/ablation.py
src/geosolver/runtime/worker.py
```

## (b) 開発問題4問の結果一致

`ablation34_driver.py` と同じthread環境（OMP/OpenBLAS/MKL/NUMEXPR各1）、外部seed 0、1 core、CPU 31固定、1件ずつ。既存の `_load_cases`、`_answer_keys`、参照の `describe_exact(...).canonical_key()` による答え集合比較を利用。起動環境から全 `GEOSOLVER_ABLATE_*` を除去し、対象スイッチだけ明示した。

公開CLIの15秒指定は `SolveOptions` の180～900秒検証により起動前に拒否された。この試行は動作確認件数に含めない。製品srcは変えず、既存 `EngineRunner.run()` を直接呼ぶ短時間ラッパーに変更した。実際の経路は通常のworker→pipeline→精密化→最終検証→同定。worker内で通常どおり2秒を保存用に予約する。外部監視は25秒、全16実行で超過・強制終了なし。

ラッパーの主要部分：

```python
problem = GeometryProblem.model_validate_json(Path(input_path).read_text())
artifact = EngineRunner().run(
    problem.engine_document(), seed=0, cores=1,
    time_limit_seconds=15, deadline_monotonic=time.monotonic() + 15,
).artifact
```

workerの `solver_status` は `success`、公開APIの状態は `solved` と名前が異なる。最初の集計でこの違いを取り違えたため、solverを再実行せず保存済みartifactを再集計した。公開serviceと同じ「受理されたexact answerがあればsolved」で状態を対応づけ、worker自身の `status=completed`、`public_solved=True` も確認した。答え・受理判定・artifactは改変していない。

| 問題 | 参照値 | BASE0 | BASE1 | 最終版OFF | 書き換え呼出数（3版共通） | 精密化入力数（3版共通） |
|---|---|---|---|---|---:|---:|
| HMMT-2016-FEB-GEO-02 | 14 | solved/一致 | solved/一致 | solved/一致 | 0 | 探索なし（定数直通） |
| HMMT-2014-FEB-GEO-02 | 169/24 | solved/一致 | solved/一致 | solved/一致 | 6 | 1 |
| HMMT-2008-FEB-GEO-02 | 3 | solved/一致 | solved/一致 | solved/一致 | 49 | 2 |
| HMMT-2006-FEB-GEO-01 | 20+sqrt(2) | solved/一致 | solved/一致 | solved/一致 | 1690 | 20 |

選択候補のUID・残差列も3版で完全一致。source_hash・PID・経過時間など版や実行時点に依存する出力値のバイト一致を主張するものではない。各artifactのimport_rootとsource_hashにより指定展開物からの実行を確認した。

## (c)(d) ON完走と実際の計数

`/tmp/switch-check/probe/sitecustomize.py` の観測用wrapperで `_smooth_zero_constraint_residuals` の実呼出、精密化入口の入力候補、残差順selectorの入出力を記録。戻り値や入力値、環境変数は変更しない。同じ観測をBASE0・BASE1・最終版へ入れた。製品patchに計数用コードは含めていない。

| 問題 | 構成 | 状態 | 書き換え実呼出 | 精密化入力 | 残差順選択の母集団→選択 | 外部秒 |
|---|---|---|---:|---:|---|---:|
| HMMT-2008-FEB-GEO-02 | NO_RESIDUAL_REWRITE | solved | 0 | 2 | 既定選択 | 1.393 |
| HMMT-2006-FEB-GEO-01 | NO_RESIDUAL_REWRITE | solved | 0 | 20 | 既定選択 | 10.342 |
| HMMT-2008-FEB-GEO-02 | NO_DIVERSE_SELECTION | solved | 49 | 2 | 2→2 | 1.397 |
| HMMT-2006-FEB-GEO-01 | NO_DIVERSE_SELECTION | solved | 1555 | 20 | 200→20 | 1.923 |

各ONも参照答え集合に一致したが、これは実行可能性の確認であり優劣評価ではない。残差順selectorの全出力で昇順・最大20個を検査。200候補の例では、既定20個とON20個のUIDの共通数は1。全16実行の外部実行時間合計は約34.4秒。

## 境界・既存回帰・再適用

- 新規境界検査：23件通過、約1.05秒。空集合、20未満、20超、同点、NaN/inf、同一UID、同一座標・同一seedを検査。30件の同一座標・同一seedから20件が残り、近接除去・seed枠が入らないことを確認。
- 通常適格条件、NOMADのfallback上位64母集団、直通のhard_feasible=None・高精度十進値・枝の箱の保持、hybrid/単純結合時の母集団伝播、途中の候補・台帳がOFF/ONで同じことを模擬入力で検査。
- 救済の2box・60評価の模擬実行：探索回数・評価上限を維持、既定の近接除去後1件に対しONは生残差順20件。実問題での救済起動は未確認。
- 距離0、直線円接条件、正の半径補助式で、共通書き換え呼出はOFF時各1回、ON時各0回。ONの残差列が元のHP評価器と一致。行数は距離0が2→1、正の半径補助式が2→1、直線円接条件は2→2。
- 解析微分採用分岐：requires_smoothing=FalseならOFF/ONとも採用、TrueならONだけ不採用。J引数とrank-awareのderivative_fnの両方を観測。既存の実際の解析微分回帰も通過。
- 既存 `test_analytic_jacobian.py`・`test_candidates.py`・`test_engine_lock.py` の計40件通過。新スイッチは未設定。
- 変更Python10ファイルのruff検査、`git diff BASE1 --check` 通過。
- 新規BASE1展開物 `/tmp/switch-check/patch-replay` に `git apply --check` → `git apply`。253ファイルの名前・本文が最終版と全一致、余分・不足・不一致0。integrityも一致。`/tmp/switch-impl` の最終git statusはclean。

実行コマンド（検査は同時実行せず逐次）：

```sh
PY=/home/kabatan/work/solver/.venv/bin/python
PYTHONPATH=/tmp/switch-impl/src OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 "$PY" -m pytest -q -s /tmp/switch-check/test_new_switches.py
"$PY" /tmp/switch-check/smoke.py
"$PY" /tmp/switch-check/analyze_smoke.py
PYTHONPATH=/tmp/switch-impl/src OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 "$PY" -m pytest -q /tmp/switch-impl.preexisting-20261024-0139/tests/solver/test_analytic_jacobian.py /tmp/switch-impl.preexisting-20261024-0139/tests/solver/test_candidates.py /tmp/switch-impl.preexisting-20261024-0139/tests/solver/test_engine_lock.py
PYTHONPATH=/tmp/switch-impl/src "$PY" /tmp/switch-check/audit.py
```

scratchの実測artifact・stdout/stderr・probeは `/tmp/switch-check/runs/<問題>.<構成>/`、集計は `smoke-summary.json` と `smoke-final.log`。最初のCLI制限拒否は `cli15-rejected-*` に分離して保存した。検査スクリプトのSHA-256：

```text
1659bfe089fc0f3fafe7d0ae8c0a2ac56387d38f2ea9f2e07589546b6994c06a  /tmp/switch-check/audit.py
db2a56692289508c9095e94db044040c8019056000c85b8f38b1e183bab07967  /tmp/switch-check/test_new_switches.py
6289efe5cdb60199f11e92e6a2eade3c4339f7400f8744f3176c1f553a383584  /tmp/switch-check/smoke.py
d761a81edf321c31fd0f019c6162a4ca810162956f0504abf240aee201e95e9b  /tmp/switch-check/short_solve.py
960d45309477c476954f7f6bc083d25b319f7d4fc7353fdd9c37c44547c5ffe2  /tmp/switch-check/analyze_smoke.py
f4451c7b94b5234e771a2c49f584490775a7c4ece0a40e2c8e4b64400442a1f8  /tmp/switch-check/probe/sitecustomize.py
```

## 未確認事項

全323問・長時間・各スイッチの同時ONや既存スイッチとの全組合せ・Windows・実問題での救済と第2探索は未確認。入力20件でも整数closure派生・救済・複数attempt・精密化済み結果結合により、実行全体の検証対象が20以下になる仕様ではない。正解率、速度、精度の改善・悪化は評価していない。
