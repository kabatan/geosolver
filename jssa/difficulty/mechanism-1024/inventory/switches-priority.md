# 新スイッチと段階別比較の入口（先行納品）

## 結論

**2案とも、対象を下記の範囲に固定すれば、小さな変更で作れる見込み。実装・solver実行はしていないため、動作確認済みとはしない。** 2時間という条件に対する工数判断もコード読解に基づく見積もりである。

| 構成 | 判断・固定する意味 |
|---|---|
| BASE | 凍結版の動作。 |
| NO_ALGEBRAIC | 既存名 `GEOSOLVER_ABLATE_NO_ALGEBRAIC`。67ad79a の実装本体はこのリポジトリにないため、実装範囲の一致は未確認。 |
| NO_SECOND_ATTEMPT | 既存名 `GEOSOLVER_ABLATE_NO_SECOND_ATTEMPT`。第2探索を止めるものとして記録あり。救済を止めるものとは別。 |
| NO_RESIDUAL_REWRITE | **採用候補**。高精度精密化の接条件・距離0・正の半径補助行に加え、最終検証の同種の接条件・点と直線の距離0の変換も止める。依存する解析微分も使わせない。検証自体とその閾値は維持。目安60–120分。 |
| NO_DIVERSE_SELECTION | **採用候補**。各探索結果から精密化へ渡す候補を、選択前の同じ台帳から生の残差ノルム順の上位20へ替える。幾何的な近接除去・seed枠を入れない。探索の初期値や救済箱の多様性は別の機構。目安60–120分。 |

全種類の式変換を一斉に削除する案、初期値・救済箱・代数枝・整数列挙まで含めて「あらゆる多様性を止め、全実行で20候補以内」にする案は、意味と予算配分の変更が広く、**2時間枠から外す**。下記の限定した比較と混同しない。

## 読んだ版と既存スイッチの根拠

- 対象コミット `60db4b679b04167175c51c479c87c22fa663fda0`。既存の `/tmp/mech-inv-clean/src/` を `git archive 60db4b6 src` の全251ファイルとバイト比較し、不一致・余分なファイルとも0。再展開による上書きは不要だった。
- `runtime/integrity.py:21–44` と同じ方式（相対名、NUL、LF正規化した本文、NUL。engine-lockを除く .py/.json/.toml）で250ファイルをハッシュし、`sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5` に一致。
- 以下のコード位置はすべてこの展開物の行番号。`E/` は `src/geosolver/engine/standard/`、`G/` は `src/geosolver/`。共有worktreeのsrcは読んでいない。
- `rg`で既存名を確認：`jssa/difficulty/capability-1024/ablation34/ablation34_driver.py:31–38` に NO_SECOND_ATTEMPT / NO_NOMAD / NO_ALGEBRAIC / NO_SCALE_CHART / NO_RESCUE / NO_ANALYTIC_JAC。ブランチの所在と差分範囲の記録は同ディレクトリ `README.md:5`。ローカルに67ad79aオブジェクトはない。したがって「既存」は記録上の存在を指し、この凍結版に環境変数が実装済みという意味ではない。
- 別の既存実験に **`GEOSOLVER_ABLATE_NO_SIGNED_TANGENCY`** がある：`jssa/results/tangency-signed/README.md:5–9`。同記録は `_smooth_zero_constraint_residuals` 全体を止めたと明記しており、今回の精密化側の残差群と対応する。ただし解析微分の整合処理までは記録から確認できない。最終検証にも別実装が見つかったため、今回の新名を既存名の完全な別名とは扱わない。

## 1. NO_RESIDUAL_REWRITE

### 対象群の全分岐

| 書き換え | 入口と生成箇所 | 止めたときの代替 |
|---|---|---|
| `Distance(点,点)=0` | `E/refinement/mpmath_refiner.py:529–545,618–626` | 座標差2行を使わず、元の非負の距離1行。0の折れ目が戻る。 |
| 接点が証明できる直線・円 | 同`:628–646`、`E/problem/tangency_contacts.py:125–190` | 半径と直線方向の内積による単純な零点を使わず、元の `IsTangent`。 |
| 接点が証明できる円・円 | 同`:628–646`、`tangency_contacts.py:192–210` | 半径同士の外積÷半径を使わず、元の `IsTangent`。 |
| 一般の円・円（弧の支持円を含む） | 同`:647–653`、`G/geometry/mp/signed_tangency.py:29–35` | 近い方の内接・外接の符号付き距離差を使わず、元の非負述語。中心一致・非正半径では既定でも元へ戻る。 |
| 一般の直線・円 | 同`:654–680` | 正規化済み直線の符号付き距離の二乗−半径の二乗を使わず、元の述語。上記signed_tangency内の直線分岐はこの呼出経路では使わない。 |
| `Distance(中心,直線)=半径` という表現の接条件 | 同`:572–579,607–610`、`tangency_contacts.py:217–269` | 接点証明による内積行を使わず、距離−目標半径。ゼロ目標だけが対象ではない。 |
| 正の半径で割った補助式 | 同`:580–588,683–688`、`E/problem/positive_radius_contacts.py:150–216` | 追加行だけを省く。元の距離条件は残る。中心が半径にアフィン、基点が外接円上、内接距離条件が一致する限られた形。`Circle`の厳密な正半径の構成条件を根拠にする。 |
| 最終検証の接条件 | `E/evaluation/verification_numerics.py:168–201,246–274` → `G/geometry/mp/signed_tangency.py:4–36` | `_SignedTangency`を使わず元の`IsTangent`。直線・円では距離−半径、円・円では内外接の近い方を使う別の平滑化が現行にはある。 |
| 最終検証の点と直線の距離0 | `verification_numerics.py:207–220` | `Distance(P,Line(A,B))`の符号付き外積÷辺長への変換を止める。点同士の距離を2行にする精密化側の処理とは別。 |

精密化側の対象は `_smooth_zero_constraint_residuals` 一か所に集まる。呼出は `mpmath_refiner.py:1354–1360`。それを有効にするpartialは `:1409`（LM）、`:1700,1731`（LM後のclosure）、`:2010`（LM前のclosure）。整数closureがある場合は `:1353` でこの群を通らず、整数式の別の書き換えを使う。最終検証側は論理式の葉にも `_smooth_zero_equation` を適用する（`verification_numerics.py:266–274`）。

### 最小変更案と落とし穴

1. 新しい環境変数名を `GEOSOLVER_ABLATE_NO_RESIDUAL_REWRITE` とする。`mpmath_refiner.py:1354` の実効フラグにOFF条件を追加する。これで全4呼出経路に効く。素朴な代替は直前の `evaluate_hp_residual` が返す元の残差ベクトル。
2. **必須の連動修正**：同`:1026–1037` の解析微分採用判定にも同じ実効フラグを使う。`analytic_jacobian.py:74–104` は接条件を別の滑らかな式にして微分し、`:128` に `requires_smoothing` を付ける。残差だけOFFにしてpartialの `smooth_zero_constraints=True` を残すと、行数が同じ場合に誤ったJacobianを採用しうる。`requires_smoothing=True` の計画だけ無効化し、通常の解析微分は残す。
3. `evaluation/verification_numerics.py:199,207` の2分岐にも同じOFF条件を置く。関数全体を素通しにするとabs・Area・min・論理式の処理まで外れるため、**接条件と距離の分岐だけ**を止める。論理式の葉もこの共通関数を通る。正規化済み式がevaluatorに保存されるため、各腕で新しいevaluatorを作る（同じオブジェクト上で環境変数だけ変更しない）。
4. 既存のNO_SIGNED_TANGENCYを流用する場合も上記2を確認する。それだけでは上記3が残る。NO_ANALYTIC_JACを腕全体で併用するだけでは、通常の解析微分まで同時に外す別の比較になる。

**残る代替経路**：`run_external_pipeline.py:349–353,391` の代数的前処理が良い初期点を供給し、精密化の直接受理やclosureで差が隠れる可能性がある。代数経路自身も `search/algebraic_branches.py:495` → `search/cartesian_polynomials.py:230–267` でDistance・接条件を多項式化する。これは別の前処理なのでNO_RESIDUAL_REWRITEでは止めない。NO_ALGEBRAICとの相互作用を別途見る必要がある。

さらに、`evaluation/final_verifier.py:122–182` は検査だけでなく座標を最大8回補正する。上記3を入れても一般の補正・片側差分は残り、回復しうる。旧スイッチ相当の「精密化側だけOFF」では、最終検証の符号付き接条件まで代わりをする。この狭い条件を補助比較する場合は `NO_REFINEMENT_REWRITE` 等の別名で区別する。入力読込みの構成契約・OnSegmentの付加行・論理式の変換（`problem/load_problem_bundle.py:46–55`、`G/problem/incidence_residuals.py:15–67`）も残る。これらを一緒に外すと対象群以上の変更になる。

NO_SECOND_ATTEMPT・NO_RESCUE・NO_NOMAD・NO_SCALE_CHARTとはコード上の必須の同時OFF関係はない。ただし候補と残り時間を変える。基準の5構成は単独OFFとし、他の既存スイッチを暗黙に追加しない。

## 2. NO_DIVERSE_SELECTION

### 現在の選択・重複除去・数

| 層 | コード位置と既定値 | 精密化への影響 |
|---|---|---|
| 通常の広い台帳 | `E/search/build_guard_feasible_ledger.py:17–76`。OKかつguardかつhard_feasibleから、最良scoreを最初に選び、正規化座標距離の最遠点を追加。`run_search.py:328–331` で `max(20×8,64)=160` 件。 | 160は主精密化数ではなく、救済箱の材料にもなる台帳の上限。 |
| 通常の代表 | 同`:79–115,118–136`。台帳から再び最遠点を最大20。最後にscore順へ。 | 通常は `min(20,適格候補数)`。ここには距離閾値による重複排除がないため、同座標が残る場合もある。 |
| 通常台帳が空の旧経路 | `E/search/deduplicate_search_candidates.py:24–95`。score順、seedごと最小3枠、箱幅で正規化した距離 `<1e-4` を重複除去、最大20。 | NOMADでは各runのscore上位64を母集団にする（`nomad_backend.py:133–157`）。通常経路は全recordsを使うので64制限はかからない。 |
| 入口ごとの適用 | `nomad_backend.py:143–157`、`scipy_multistart_backend.py:1381–1395`、`orchestration/run_search.py:198–213`。 | 共通関数だけの修正でもこれらに効くが、下記の直通経路を覆わない。 |
| 直通・結合経路 | `search/scalar_branch_scan.py:55–66` は既に残差順で最大20。`run_external_pipeline.py:391` は代数結果を直通。`run_search.py:332–359,504–541` は整数・有限guard・尺度座標の結果を追加し、再圧縮しない。 | **パイプライン全体の20件上限はない**。 |
| 救済・離散補完 | `run_external_pipeline.py:482–505` の追加精密化と後続の離散補完。 | 救済は最大6箱×各6候補という別枠。整数closureは1候補から派生候補も作る。 |

距離正規化は `E/search/coordinate_distance.py:12–16`：各軸を `max(箱幅,1e-12)` で割ってユークリッド距離。初期値選択の近接閾値 `1e-2` は別（`select_search_start_points.py:35–60`、`nomad_config.py:19–23`）。

### 最小変更案（比較する選択点を固定）

**推奨は「探索終了→精密化」の境界で一度選び直す方式。** 共通台帳関数だけの差替えでは代数直通・追加候補を取り逃がすためである。

- `E/orchestration/run_external_pipeline.py:402–403` に小さい選択関数を挿入。母集団は `search_result.all_records`（空なら `candidates`）から、**生成経路ごとに元の適格条件を維持して**組み立てる。通常backendの適格条件は `evaluation_status==OK && guard_ok && hard_feasible`。残差は **`residual_norm_float`**。有限値だけを `(残差, candidate_uid, 元の順序)` で安定に並べ、上位20にする。seed割当と座標距離の重複除去をしない。同一来歴レコードの結合重複だけは両方式で同じ扱いにする。
- **直通経路は通常の適格フィルタに掛けない**。`algebraic_branches.py:690–711`、`scale_chart.py:74–87` の候補は `hard_feasible=None` のままで、代数候補はfloatのguard違反もHP検証へ送る設計。これらと有限guard・整数列挙の元の候補を母集団に加える。NoneをFalse扱いする一律フィルタは、選択法以外に候補生成経路を消してしまう。母集団を生成元で識別できない結合結果では、この境界案を適用しない。
- 通常の適格集合が空の場合も、既存の「不適格な探索点から精密化を試す」経路を消さない。旧fallbackと同じ候補集合・評価可否を使って上位20とする。NOMADのfallbackは各run上位64、SciPyはrecordsなので、その既存母集団を返す／識別する小さい補助が必要（`nomad_backend.py:133–157`、`scipy_multistart_backend.py:1388–1395`）。全raw recordsから新たにfallbackを作る案は比較条件を変えるため避ける。
- 選択済みの `SearchBatchResult.candidates` を `replace` し、要約も実際の精密化入力と一致させる。`all_records` と救済用の広い台帳は保存する。探索初期値・hybridの補助探索・救済箱の作り方はこのスイッチの対象外と明記する。
- 救済から入る**新規バッチ**にも同じ意味で適用するなら `run_external_pipeline.py:482–492` で選び、精密化とmergeの両方へ同じリストを渡す。既に精密化・検証した候補を20に切り直さない。離散補完中の整数ターゲット列挙は候補生成機構として残す。

この定義で、主探索から精密化へ渡る数は各attemptで最大20。通常経路は数が同じことが多く、選ばれる座標が変わる。代数・補助結果の結合で20を超えていたバッチは減る。精密化は締切で途中停止し、整数closureで候補が派生する（`mpmath_refiner.py:1153–1205`）ため、**入力20でも最終検証対象が必ず20以下とは言えない**。最終検証は残差順、状態の適格判定、締切による打切りがある（`assemble_exact_results.py:159–175`）。第2attempt・救済も含む実行全体の検証数はさらに別である。

注意：現行のscoreは正規化された残差とguard罰則を含む。生の残差順という指定は、多様性に加え**順位の尺度**も替える。比較記録にはscore・生の残差の両方を残す。多様性だけの寄与に厳密に分けたい場合は、同じscore順上位20の補助比較が必要（5構成へ無断で追加しない）。

既存6スイッチに同等名は見つからなかった。新規名は `GEOSOLVER_ABLATE_NO_DIVERSE_SELECTION`。NO_ALGEBRAICで台帳の由来、NO_SECOND_ATTEMPT/NO_RESCUEで選択バッチ数、NO_NOMAD/SEARCH_MODEでrecordsの意味が変わる。NOMADのrecordsは評価点、SciPyは主に局所探索後の状態なので、台帳を混ぜた件数だけで探索努力を比較しない。

## 3. 段階別比較の入口

| 比較 | 既存の入口と取り出せるもの | 追加する小さい観測処理・注意 |
|---|---|---|
| ① 接条件：同じ候補から精密化し、直後と最終検証後を比較 | `E/orchestration/run_refinement.py:14–29` → `MpmathRefiner.refine_candidates`。入力は不変dataclassのFloatCandidate群。返値の `x_hp, residual_norm_hp, answer_hp, phase_history, *_precision_dps`（`contracts/candidate_record.py:83–159`）。後段は `assemble_exact_results.py:152`、単体検査は `evaluation/final_verifier.py:85`。 | **可能、標準の候補save/load CLIはない。** 精密化前に全入力フィールドとDSL・bounds・config・source_hashを保存し、別々のevaluatorで復元する。`initial_point_decimal` と `originating_branch_box` を落とすと代数候補の桁と枝が失われる。精密化直後を、最終検証で候補revisionが更新される前に保存する。最終検証後は `numeric_feasible_candidates` と失敗を含む `verification_records`、受理後は `candidate_records`。最終検証は補正も行うので、この2時点は必須。 |
| ① 残差・目標値誤差 | 精密化残差は書き換えをしない評価器で再評価される（`mpmath_refiner.py:1555–1571`）。最終結果に `residual_norm, normalized_residual, answer_hp, answer_uncertainty, values`。 | 比較用残差は両時点の座標を同じ評価器・同じ評価桁で測り直す。目標式の真値との差はsolver内にはないため、独立した参照値を用意して絶対誤差・必要なら相対誤差を計算。`answer_uncertainty`は誤差の見積りで、正解値との差そのものではない。失敗を落として成功点だけを比べない。 |
| ② 複数値：選択前台帳を保存し選択だけ替える | `SearchBatchResult.all_records` と `guard_feasible_ledger`（`candidate_record.py:182–191`）、`build_guard_feasible_ledger`はsolverを動かさずレコードに対して呼べる。 | **可能**。保存すべきは圧縮前の`all_records`。160件のledgerやdebug候補（既定32）だけでは足りない。bounds、score、残差、feasibility、uid、元の順序、既存fallbackの母集団も保存。BASEの特殊経路の元の`candidates`も保存して再生する。救済を含む全実行を同じ台帳で再生するには、attempt/boxごとの台帳と予算を分ける。各JSONL断片は3MB以下に分割し、切捨てで上限を守らない。 |
| ③ 保存高精度値に対しPSLQの精度と係数上限を別々に変更 | `G/exact/polynomial_search.py:246` の `find_minimal_polynomial(r, precision, max_degree, max_coeff, max_steps)`。固定次数だけなら同`:316` の `_find_polynomial_pslq`。いずれも探索や精密化を呼ばない。 | **既存関数で可能**。上位 `identify_answer` はtierに次数・係数・反復数が束ねられ、symbolic worker・π探索等も通るため純粋なPSLQ比較には下位関数を使う。precisionとmax_coeffは独立の引数。ただしprecisionは作業桁だけでなくPSLQ許容差も変える。係数上限はスケール変換後の関係に対する上限で、元の変数へ戻した最終係数の上限とは限らない。 |

PSLQの詳細：`find_minimal_polynomial`は作業桁 `max(現在のmp.dps, precision+40,80)`、下位PSLQは `max(現在のmp.dps, precision+30,60)`。許容差はprecision>100なら `10^(-precision//2)`、それ以外は `10^(-precision*3//10)`（`polynomial_search.py:256,282–290,325`）。保存値は十分な桁の十進文字列、またはmpfの正確な二進タプルで保存し、低い既定mp.dpsやfloatを経由させない。元値を高い作業桁で読み、各試行は明示したworkdpsで丸めて使用する。入力の既知精度を超える桁を真の情報として扱わず、発見した関係は別の十分高精度値で確認する。

既存の同候補比較フック `jssa/results/tangency-signed/probe/sitecustomize.py:44–91` は再利用の参考になる。ただし保存は残差桁数・時間・状態が中心で、共通候補の永続化、目標値誤差、最終検証後の比較までは満たさない。

## 実装時に必要な確認（今回は未実施）

通常の解析微分を残しつつ書き換え依存の計画だけ無効になること、整数closureが元の仕様で残ること、候補選択の同点処理・空集合・20件未満・特殊経路の結合、保存復元で高精度座標とuidが変わらないことを小さい単体確認で検査する。これらが2時間で確認できなければ該当スイッチを外す。性能改善や正解数の増減は、この読解だけでは判定しない。
