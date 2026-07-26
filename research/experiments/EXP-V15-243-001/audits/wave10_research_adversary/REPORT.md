# Wave 10 research adversary report

監査時点: `2026-07-19T07:29:20+09:00`

## 結論

**継続可は D0、改善 cycle、candidate-private composition までである。D2、development 145、production 統合、formal score 更新はすべて未承認。**

現行 formal development score は proof-bearing `121/145` のままである。`136/145` は source-safe 診断値、`131/145` は旧 target-only empirical 値であり、今回の search-only / generated / proof-component 結果をどちらにも加算してはならない。基準文書は `AUTHORITY_POLICY.md` SHA-256 `b6be9d59106ac46e9d14e0fd8f9d7777beaf171f66f4d3ad9ed83640b35dff38` とする。

今回の adversarial audit は、誤った D2 推薦を 1 件、formal authority へ進み得た raw-ledger soundness 欠陥を複数、candidate signal 違反を 1 系統、実験 artifact closure drift を複数回、promotion 前に fail closed させた。offline truth、validation 49、sealed 49、independent 60 を search / policy / exactification へ渡した証拠は検出していない。Oracle review は使用していない。

## P0/P1 findings と処置

### 1. Leverage 30 秒 gate の誤推薦を VETO

5 秒 V2 は独立監査済みで、control `57/72`、leverage `59/72`、gain `2`、loss `0`、異なる 2 structural strata、source-solved/CPU `+1.864%` だった。したがって 30 秒実行資格は正しく得た。

30 秒 V3 は 3 seed、全 `216/216` fresh process trial accepted、全 runtime closure 一致、AB/BA 同一 CPU 直列 trace `72/72`、独立 fresh source replay `6,908` endpoint、replay finding `0` だった。しかし結果は次のとおりである。

- source-solved: `64/72 -> 64/72`
- paired gain/loss: `0/0`
- safe endpoints: `776 -> 795`
- callbacks: `158,887 -> 159,574`
- CPU: `658.140885 -> 658.289012` 秒
- source-solved/CPU: `-0.02250%`
- source-solved/callback: `-0.43052%`

初期 analyzer は「zero loss + safe endpoint 非退行 + 5 秒 gate」を `clean` とし、30 秒 gain が 0 でも `d2_promotion_recommended=true` としていた。これは D1 の 30 秒 multi-structure gain / 10% efficiency gate を満たさない。旧 aggregate SHA `0b5e9005...` の推薦は独立 validator が明示的に拒否し、current decision は `D1_30S_NO_GAIN_IMPROVE_HOLD / NO_D2` となった。

正式な post-run validator artifact は `THIRTY_SECOND_RESULT.json` SHA-256 `d3c7dc878b489addc0724f8d3c18c897879ced9f2669665b42bcec5bce033103`。5 秒の promising evidence は保持してよいが、30 秒で source-solved gain が消えたため D2 へは進めない。異なる方向の改善機会として normalized trust/rank D0 を与えた結果は current `GENERATED_RESULT.json` SHA `3fc5e4f9...` 上で `60 -> 59`、coupled-cubic loss `1` であり不採用。監査時点の AlgorithmCard/Decision は別 SHA `1c981a61...` の `60 -> 60` tie を記述しており current bytes と不整合なので、文書を current regression に修正するまで当該 cycle の author decision は無効とする。次は additive proposal placement の 1 cycle だけが妥当である。

### 2. Raw-ledger v1/v2 の formal-authority 穴

raw-ledger v1 は次の P0 により VETO された。

- nested `variables.bounds` が黙って落ち、domain 外 endpoint を proof component として受理できた。
- raw AST occurrence と prepared AST / exact DAG の対応が aggregate count に留まり、branch / definedness identity を一意に結べなかった。

v2 の初期版でも `(x/x)+(x/x)` の 2 raw division occurrence が両方の prepared sibling path へ対応する 2-to-2 ambiguity が見つかった。また JSON fractional literal が Python binary64 へ丸められ、pre-normalization exact identity を失う穴も見つかった。最終 v2 は次を fail closed にした。

- duplicate key、NaN/Infinity/overflow、unknown nested fields の recursive rejection
- fractional JSON numeric literal の拒否（lossless token がない間）
- raw occurrence -> prepared path の path-bijection / disjoint expansion ownership
- equation relation composite root と top-level bound predicate root の traced evaluation
- actual worker DAG ordinal `0..N-1` coverage
- terminal の完全再実行と digest 再検証

current frozen closure:

- candidate `1ab96b55790b5b1536fb177823f1c9930e13ec839df7c9c0bc8cf373e8ecd715`
- tests `80b6370ec7042998be639bbbadbf59696c8851befff193aad67bdee75d081b76`
- runner `baa15b3e94b9b4735d3eb95ae23f3c4082c2720f681199ec33827fab615682d2`
- panel `cf8f31aae6f11a4e4cd227274674f4694f9d05f344aefff66be6822dd7d17cb8`

独立 re-audit は `GO_PRIVATE_COMPOSITION`。validator artifact SHA-256 は `8af8a255947a4224fbdd1299b0216117ba9c3e3411c4fa93a52fb9d3c0302662`。ただしこれは **proof component の candidate-private composition だけ**を許可する。standalone target release、common worker 変更、real D1/D2、completeness claim は許可しない。HP/source evaluator parity を同じ raw identity closure に結合し、terminal を再実行するまでは descriptor を解放してはならない。

### 3. Wall scheduler は signal whitelist 違反

wall scheduler の current cycle 3 は generated evidence としては再現した。gain `171`、loss `0`、false `0`、3 structures 各 `57`、insurance 最小 `25%`。初期 real adapter dry-run にあった `insurance_floor_all_runs=true` と実測 `0.189/0.238 < 0.25` の矛盾も修正され、current dry-run は全 arm exactly `0.25` となった。

それでも policy は per-callback `time.monotonic()` duration を EWMA と progress-per-wall selection に使う。§2.3 の許可 signal に callback wall duration は含まれない。deadline enforcement に monotonic clock を使うことはよいが、lane selection へ使ってはならない。独立 verdict は `HOLD_SIGNAL_NOT_AUTHORIZED`、validator SHA-256 `ef23ff2f3cfad6db383de367d2b444ade9942c1d22a0f3f46cdc2dc6ea2c1163`。real D1 は禁止。

callback/work ledger だけを使う別 candidate は方向として正しい。旧 wall evidence は流用せず、現行 source hash で generated D0 を再生成し、`merit_progress` が consecutive source residual / violation だけから worker-owned に計算されること、1 quantum = 1 charged source callback、uncharged terminal notice が work を増やさず無限 loop しないこと、insurance `>=25%` を独立監査してから thin real adapter へ進む必要がある。監査時点では `RESULT.json` が scheduler `ce8da658...` を bind する一方 current scheduler は terminal-notice 修正後 `ec2a118...` であり、artifact は stale。現行 bytes で再生成するまで HOLD とする。

## Candidate portfolio 判定

| 系統 | 現在の判定 | 根拠 |
|---|---|---|
| base local secant `ridge_1e-8` | `D1_FAIL / NO_30S` | control `59/72`、candidate `57/72`、gain `0`、loss `2` |
| leverage-filter secant | `IMPROVE_HOLD / NO_D2` | 5 秒 `+2/-0`、30 秒 `0/0`、efficiency 非改善 |
| leverage trust/rank cycle | `IMPROVE, axis rejected` | generated `60 -> 59`、1 structure regression |
| uncertainty reservoir | `STOP_TWO_CYCLE` | cycle 1 gain 0、cycle 2 `20 -> 8` regression |
| exact SVD hookstep | `STOP/HOLD_SINGLE_FAMILY` | base `120 -> 118`、retry `118 -> 119` は 1 family のみ、次 2 axes 無改善 |
| checkpoint kernel | `PASS_PARITY` | all-ordinal `440/440`、mature equivalence `8/8`、cross-source binding fail closed。kernel SHA `da66047b...`、parity SHA `301a651a...` |
| old cost-ratio scheduler | `HOLD_TRANSFER_SIGNAL` | real adapter は全 callback を `work_used=1`、generated gain は synthetic ratio 依存 |
| wall scheduler | `HOLD_SIGNAL_NOT_AUTHORIZED` | wall duration が許可外 selection signal |
| callback-ledger scheduler | `HOLD_REGENERATE_CURRENT_BYTES` | algorithm direction は適合、current source/result hash drift 未解消 |
| exact/source authority v2 | `GO_PRIVATE_COMPOSITION_ONLY` | strict raw identity mapping と exact replay は合格、target release は未承認 |
| topological facet scout | `D0_GO / HOLD_INFRA_BLOAT` | generated gain はあるが real seam に raw semantic token/local radius がない |
| saddle traversal | `D0_PASS / HOLD_INFRA_BLOAT` | real anonymous prevalence に F/J/token witness が 0 |
| opaque carrier | `HOLD` | eligible `3`、required `4` 未満 |
| semantic strata | `HOLD_INFRA_BLOAT` | complete trace eligible `0` |
| certified low degree | `HOLD` | eligible `0/145` |
| root-exclusion restart | `STOP` | gains `0/3 families`、loss `24/60` |

## 要件適合監査

### Safety / leakage

- current promoted search policy で truth、known target/count、prior outcome、case-specific bounds/precision/restarts を使う証拠は検出しなかった。
- source hash / case ID は worker の integrity binding と scorer artifact には現れるが、leverage policy の branch input には渡っていない。
- raw v2 は source SHA を authority binding に使うが routing には使わず、`id` value を semantic projection から除外している。
- generated family/category/cost role は fixture owner metadata に留め、scheduler input にしてはならない。
- formal target authority は 3 許可 route の外へ拡張されていない。proposal-only residual、PSLQ、approximate guard から target を emit した証拠はない。

### Resource / isolation

- leverage formal D1 は fresh one-process-per-arm/case、native thread 1、8 distinct physical cores、same-case arms serial same CPU、AB/BA alternation、hash-closed first-party runtime、no-clobber output で実行された。
- required thread environment は全 trial で 1、runtime closure mismatch と fresh replay error は 0。
- candidate は `research/experiments/EXP-V15-243-001/candidates/` 内に隔離され、今回の promotion candidate による production API/CLI/schema 変更はない。
- dirty/untracked 既存成果は保持され、reset/clean/restore は行われていない。

### Research allocation

独立 algorithm hypotheses は多数実行され、適用性不足 candidate は compiler/framework を作らず HOLD/STOP された。二改善 cycle 規則は reservoir と hookstep で守られ、leverage も 30 秒無改善後に別方向の generated cycle を与えられている。

一方、総工数 `algorithm >=90% / support <=10%` は artifact から厳密には証明できない。wave10 top-level Python の単純 line proxy では validator/audit 系が約 14% 前後で、特に generic performance validator が大きい。これは工数そのものではないが support-heavy risk である。これ以上の共通 framework、DB、dashboard、runner retrofit を増やさず、既存の薄い candidate-private runner と read-only validator を再利用すること。

## 次に許可する作業

1. leverage は additive proposal placement という別方向の generated D0 を 1 cycle 実施する。30 秒の同じ failure を直接再実行する前に、別 family と frozen generated cases で検査する。loss/false が出れば即停止。
2. callback-ledger scheduler は current source/result closure を再生成し、独立 D0 validation を通す。wall/cost label を一切使わない real checkpoint adapter feasibility だけを次 gate とする。
3. raw v2 は exact-cert + HP parity との candidate-private composition を新 SHA closure で作る。component 単独では target を release せず、positive/negative/near-miss と forged proof を再実行する。
4. いずれも D1/D2 gate を新たに通るまで shared worker/production preset を編集しない。
5. development 145、validation 49、sealed 49、independent 60、final 243 は引き続き閉じる。formal score は `121/145` に固定する。

## 最終 promotion veto

次のいずれかが起きたら improvement cycle を待たず停止する。

- false/extra、source replay破壊、raw identity未対応、forged proof受理
- truth/case routing、case-specific tuning、wall-duration routing
- stale source/result hash のまま GO/D1/D2 を主張
- 30 秒 gain 0 を 5 秒 gain や safe endpoint count で代用して D2 を主張
- proof component を HP parity 未結合のまま target authority として release
