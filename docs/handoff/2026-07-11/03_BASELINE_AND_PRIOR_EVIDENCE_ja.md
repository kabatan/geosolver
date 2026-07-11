# 現 baseline と過去 evidence

## 1. baseline artifact

| 項目 | 値 |
|---|---|
| file | `benchmarks/results/raw/solver-lab-baseline.json` |
| SHA-256 | `B495F81FDA8376C28017123D9DCD78D733057E7BC2040F37E50E472D111F7817` |
| schema | `geotarget.solver-experiment/v1` |
| Git | clean `e2cf389346f5ffa3a307e52204542ad219ebdd07` |
| environment | Julia 1.12.6、1 thread、`x86_64-w64-mingw32` |
| variant | `core-lmqr-bounds-scaled` |
| options | bounds coordinate scaling、declared residual scaling、120 iterations/start、600 evaluations/start |
| prefixes | 2 / 4 / 8 starts |
| corpus | 8 family 各 1 deterministic case + MultiRoot target-collision companion |
| tolerances | residual `sqrt(eps(Float64))`、configuration/target `1e-6` |

prefix 集計:

| starts | all-target cases | targets | configurations | false-candidate proxy | false-target proxy | evaluations |
|---:|---:|---:|---:|---:|---:|---:|
| 2 | 3/9 | 6/16 | 6/18 | 3 | 3 | 3,244 |
| 4 | 5/9 | 8/16 | 8/18 | 8 | 8 | 5,455 |
| 8 | 6/9 | 9/16 | 9/18 | 13 | 14 | 12,391 |

全 72 attempts で exception 0、runner budget overrun 0、runner-counted evaluation と variant report の mismatch 0 だった。

重要: この表は endpoint-based scorer の現出力である。`reported_accepted` を primary recall の条件にしていないため、製品 solver が返す答えの正確率として引用しない。また `CoreBaseline.jl` は 120 iterations / 600 evaluations と `LocalSolveOptions` default residual tolerance `sqrt(eps(Float64)) ≈ 1.49e-8` を使う。一方、production の nominal local options は 250/2000 と residual `1e-12` で、その後に target-image/root-correction/candidate validation を行う。旧 artifact は production output の baseline ではない。reported/assessor metrics、`prod-tol-120x600` control、`prod-options-250x2000` diagnostic を分けて再生成する。

## 2. prefix 8 の case 別結果

| family / target map | targets | all | false candidate | false target | duplicate target | evaluations | 観測 |
|---|---:|:---:|---:|---:|---:|---:|---|
| ScaleLadder | 1/1 | yes | 0 | 0 | 7 | 224 | scaling case は容易、重複 work が多い |
| CurvedChain | 1/1 | yes | 0 | 0 | 7 | 794 | 全 start が同 target、局所 work はやや大きい |
| NearRankDeficient | 0/1 | no | 7 | 7 | 0 | 1,864 | 7 endpoint を converged/accepted と自己判定するが Gold configuration と離れる |
| RedundantOverdetermined | 1/1 | yes | 0 | 0 | 7 | 152 | 容易、重複 work が多い |
| TangentCircleLine | 2/2 | yes | 4 | 5 | 1 | 592 | recall は達成するが endpoint quality が不安定 |
| MultiRootWarped `z1` | 0/4 | no | 1 | 1 | 0 | 4,192 | 7/8 が local evaluation cap、根を一つも回収しない |
| MultiRootWarped `z1²` | 0/2 | no | 1 | 1 | 0 | 4,192 | 同 latent roots/starts の collision companion、独立 geometry と数えない |
| StrictGuardBoundary | 1/1 | yes | 0 | 0 | 3 | 193 | prefix 2 は miss、4 以降 success |
| OpaqueTranscendentalC0 | 3/3 | yes | 0 | 0 | 5 | 188 | black-box C0 表現力を保ったまま回収 |

現時点で最も大きい failure class は二つある。

1. **local endpoint correctness / conditioning:** NearRank と Tangent。
2. **local capture/global discovery:** MultiRootWarped。

easy family の duplicate hit は archive-aware scheduling の余地を示すが、close root を hard suppression する根拠にはならない。

## 3. failure 仮説の切り分け

次の順で測る。Gold は assessor 側の原因分析にだけ使い、production routing に使わない。

| 観測 | 第一仮説 | 次の対照実験 |
|---|---|---|
| Gold start 近傍からも失敗 | F5/F9 local model、rank、singular endgame | LM vs TR、rank-aware correction、singular controls |
| Gold start なら成功し random start で miss | F4 capture / proposal coverage | fixed local champion で proposal stream 比較 |
| small residual だが configuration/target error 大 | F6/forward uncertainty | assessor/reported scorer、correction estimate、rank/condition stability |
| 同じ configuration/target を繰り返す | F11 duplicate allocation | soft novelty/order、independent-uniform D0 lane を残す |
| guard/domain/branch invalid | F2/F7/F8 semantics | canonical gate を固定し、step/restoration のみ比較 |
| evaluator time が local linear algebra より支配的 | F18 compiler/oracle cost | profile 後に compiler/AD card、algorithm と同時変更しない |

NearRank の現 endpoint は `rank=3` / `condition=Inf` が多く、scaled residual が tolerance 内でも normalized configuration distance はおよそ 0.044–0.286 になる。これは「residual を少し厳しくすれば解決」と決め打ちせず、forward uncertainty と correction stability を別に測るべき signal である。

## 4. 過去の最も有用な positive signal

`research/results/EXP-LOCAL-002/development-v0/development-report.md` は、48 frozen development instances × 32 paired starts の過去比較を記録する。これは locked validation でも production authorization でもないが、次の候補順序を決める実測 signal である。

prefix 32 overall:

| variant | P_local_gold | P_full_target | residual-qualified non-Gold | charged work | warm wall (s) |
|---|---:|---:|---:|---:|---:|
| NLS-TR | 0.9206 | 0.8958 | 82 | 343,469 | 0.3444 |
| NLS-LM | 0.8854 | 0.8750 | 131 | 493,424 | 0.7839 |
| NLS-RMN | 0.9206 | 0.8958 | 82 | 346,387 | 1.8100 |
| NLS-TR-STRICT | 0.9219 | 0.8958 | 82 | 356,176 | 0.3786 |
| LXR-LMQR | 0.7956 | 0.8125 | 134 | 534,029 | 3.4076 |

解釈:

- Trust Region は current lineage の LM-QR より recall/work の両方で強い signal を持つ。
- RMN は同 recall で遅い。
- 単に内部 residual tolerance を厳しくした variant の全 target 利得はなかった。
- up-front LM/TR router は LM を約 0.7% しか選ばず、追加診断費用を正当化できず gate fail した。
- 過去 adapter、budget、dependency と現在 lab が違うため、最初に truth-blind current runner で再現する。再現前に Core へ Trust Region を統合しない。

この evidence により、最初の major candidate は deflation や大規模 lifting ではなく Trust Region comparator とする。

## 5. handoff 時の in-memory sensitivity pilot

引継ぎ監査中に、current `solve_local` の residual tolerance と initial damping への感度を、truth-blind case API 上で stdout-only 診断した。repository 変更・JSON artifact・保存 script・formal claim はない。以下の数値は再監査不能な **anecdotal hypothesis generator** であり、experiment threshold、effect size、promotion decision には使わない。ALG-LAB-001 の clean artifact で再現できなければ捨てる。

共通条件:

- `representative_problems(start_count=8)`、prefix 8
- 9 cases、600 evaluations/start、120 iterations/start
- bounds coordinate scaling、declared residual scaling、central FD
- Julia 1.12.6、current `solve_local`
- runner scorer 自体の residual tolerance は旧来の約 `1.49e-8`

### residual tolerance sensitivity (`initial_damping=1e-3`)

| local tolerance | all-target cases | configurations | targets | scorer false c/t | reported accepted | evaluations | iterations |
|---:|---:|---:|---:|---:|---:|---:|---:|
| `1e-12` | 7/9 | 10/18 | 10/16 | 8/8 | 51 | 14,485 | 1,708 |
| `1e-14` | 7/9 | 10/18 | 10/16 | 2/2 | 42 | 14,703 | 1,738 |

`1e-12` では Tangent の scorer false が 0 になり、NearRank target も 1/1 になったが、NearRank の scorer false は 6 残った。`1e-14` では NearRank の scorer false も 0 になった一方、Redundant は Gold endpoint 1/1 でも reported accepted 0 だった。単に tolerance を厳しくするほど product recall が上がるとは言えない。

### initial damping sensitivity (`local tolerance=1e-14`)

| initial damping | all-target cases | configurations | targets | scorer false c/t | reported accepted | evaluations | iterations |
|---:|---:|---:|---:|---:|---:|---:|---:|
| `1e-3` | 7/9 | 10/18 | 10/16 | 2/2 | 42 | 14,703 | 1,738 |
| `1e-16` | 7/9 | 14/18 | 13/16 | 0/0 | 55 | 6,062 | 759 |
| `1e-20` | 7/9 | 14/18 | 13/16 | 0/0 | 55 | 5,909 | 742 |

主な変化:

- MultiRoot `z1`: 0/4、4,759 eval → 2/4、約 1,834–1,843 eval
- collision `z1²`: 0/2 → 1/2
- NearRank: 2,494 eval → 152–287 eval
- representative target set の scorer 上の悪化は観測されなかった

ただし reported acceptance と scorer endpoint match は一致しない。例えば strict tolerance の Redundant は target 1/1 でも reported accepted 0 である。production はさらに root correction と candidate validation を通す。したがって固定 `1e-16` / `1e-20` を default にしてはならない。

この pilot が支持する仮説は限定的である。

> 現行 LM の固定 `initial_damping=1e-3` は problem/scale に対して過大な場合があり、globalization と damping initialization が大きな performance lever である。

次の正式 experiment は、固定極小 lambda の tuning ではなく、Moré-style implicit scaling/safeguarded damping と bound-aware Trust Region を current frozen-assessor/reported accounting で比較する。これにより現 solver の構造を生かしながら、過去の TR signal と current damping signal を同じ機構軸で検証できる。

### weak-direction exploration pilot

同じ session で、small-damping LM が MultiRoot の外側 root `-0.0015` を一つ得た後、その endpoint の bounds-normalized central-FD Jacobian を SVD した。最小右特異 vector `v_min` に沿って `u ± 2^-k v_min` (`k=6:18`) を新 start とし、同じ black-box local solver へ戻す exploratory probe を行った。

- Warped endpoint の singular values: およそ `[2.0950, 2, 2, 1.15e-8]`
- `k=10` の一方向が内側 root `+0.0005` を 37 evaluations で発見
- `k=11` が内側 root `-0.0005` を 28 evaluations で発見
- 大きい radius の反対方向は反対側の外側 root も発見
- base solve 約 270 eval + `k=6..11` の両符号 probes 約 1,038 eval、概算 1,308 eval で 4 configurations を探索
- 同 session の 32 saved-start diagnostic は 7,680 eval でも外側 2 configurations に留まった

Tangent でも singular values は約 `[3.3541, 0.001897]` で、弱方向の反対符号 probe が別 target を発見した。

runtime に family ID、Gold、target map は使わず、Gold は事後 label にだけ使った。しかし 1 instance/session、artifact なし、radius grid を結果と同時に見た exploratory pilot であり、effect size や一般性の claim はできない。

これは次の新規仮説を支持する。

> canonical-valid endpoint の weak Jacobian direction は、近接 root/tangent branch の局所探索 proposal として、independent-uniform restart より情報効率がよい場合がある。両符号・多尺度 proposal を既存 refinement queue に追加すれば、insurance lane を削らず all-target recall を上げられる可能性がある。

候補名は `condition-guided symmetric weak-direction exploration`。R2 の rank/correction 診断を再利用し、R3 で independent-uniform D0/QMC と別 ablation にする。production では新 solver loop を作らず、既存 refinement emitter へ normalized direction/radius hint を渡す。

必須 counterexample:

- multiple weak singular values / unstable subspace
- orthogonal・scale・equivalent-DAG representation
- manifold（無限 duplicate を出さない）
- strict guard/domain/branch crossing
- isolated regular root と nonroot stationary point
- close roots が weak direction と整列しない case
- preparation + failed probe work を全 charge

同 session の target-space shifted deflation (`p=1/2`) 32-start probe は inner roots を増やさず、`z1` は最大 2/4、`z1²` は 1/2 だった。Jacobian reuse だけの probe も Warped recall 0/4 のままだった。いずれも artifact のない診断なので global rejection ではないが、deflation/J-reuse 単独より weak-direction refinement と globalization を先にする理由になる。

## 6. negative-result ledger

正本は `research/negative-results/ledger.json`。`prior_unreproduced` は注意仮説、`reproduced` は bounded evidence である。bounded rejection を algorithm family 全体の永久否定に拡大してはならないが、同一 mechanism/threshold をそのまま再実行してはならない。

| ID | state | 現 decision | reopen の要点 |
|---|---|---|---|
| NEG-001 | prior | residual-only hard start selection を default にしない | narrow/close basin を hard discard せず family-disjoint gate を通す |
| NEG-002 | prior | hard APOSMM-like suppression を使わない | soft emitter と independent-uniform D0 all-launch control、永久 discard なし |
| NEG-003 | prior | naive homotopy/lift-all を general default にしない | applicability predicate と 3 unrelated family の superiority |
| NEG-004 | prior | barrier proximity を strict-guard validity としない | canonical/validated sign separation を持つ guard-aware study |
| NEG-005 | prior | dynamic expression evaluation を production kernel にしない | reopen 予定なし。typed/no-eval architecture を維持 |
| NEG-006 | reproduced | separate dense rank diagnostic の LM/TR routing を reject | solver-native Jacobian/progress state を再利用し overhead gate を通す |
| NEG-007 | reproduced | sparse FD coloring を general default にしない | cached coloring/applicability route、zero mismatch、dense/cold overhead gate |
| NEG-009 | reproduced | CPQR subset 成功を general singular solution と呼ばない | isolated multiple/tangent/manifold/nonroot controls と zero false promotion |
| NEG-010 | reproduced | BigFloat point replay を root validation としない | 近傍 root evidence と target error coverage を独立に示す |
| NEG-012 | reproduced | frozen restarted good-Broyden S3 を reject | 新設計、endpoint-global budget、close-root metamorphic agreement |
| NEG-013 | reproduced | frozen archive-coupled deflated GN v2 を reject | false/no-root 0、deflation-specific signal、preparation economics |
| NEG-014 | reproduced | frozen S4 two-step candidate を reject | coordinate-stable final audit、12/15、metamorphic disagreement 0 |
| NEG-015 | reproduced | EXP-JAC-003 から algorithm 結論を出さない | 新 ID、serialization preflight、clean host、registered ABBA 完了 |

### 実務上の禁止事項

- `EXP-LOCAL-003` は formal C0/C1/C2 未実行・claim なし。通常開発で launch しない。
- S3 good-Broyden を iteration cap だけ緩めて再実行しない。
- S4 two-step を同じ representation-sensitive final gate のまま再実行しない。
- EXP-DEF-001 v2 を parameter retune だけして再利用しない。
- EXP-JAC-003 の failed formal attempt を cached Jacobian の positive/negative evidence として引用しない。
- sparse coloring は compiler profiling の後に fresh card として reopen するまで production default にしない。

## 7. evidence の重み付け

強い順:

1. frozen holdout + production path + independent replay
2. family-disjoint locked validation result
3. paired parameterized development result
4. representative 9-case lab
5. focused microbenchmark
6. anecdote / old implementation observation

現在の Trust Region signal は 3、current baseline は 4 である。どちらも solver completion claim には足りない。

## 8. baseline の再生成

```powershell
julia +1.12.6 --startup-file=no --history-file=no --project=julia `
  benchmarks/solver_lab/run.jl `
  --output=benchmarks/results/raw/solver-lab-baseline.json

Get-FileHash benchmarks/results/raw/solver-lab-baseline.json -Algorithm SHA256
```

assessor/reported metrics を追加した commit 後は schema version または metric field を更新し、上記 SHA を新しい primary baseline へ置き換える。旧 artifact はこの handoff ZIP に保存する。
