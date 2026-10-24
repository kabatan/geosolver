# 凍結版60db4b6：性能に関わる機構の棚卸し

**全148項目。既存スイッチで群としてカバーする項目13、個別比較に新規スイッチ・設定が必要な項目118、安全な単純OFFを提案しない項目17。**

件数は下表の行数で、独立したスイッチ数ではない。既存名は8種類を記録から確認した。例えばNO_SIGNED_TANGENCYで複数の書き換えが同時に止まるため、複数行に同じ既存名が現れる。代数前処理の細部はNO_ALGEBRAICでまとめて止められるが、**細部だけ**を比べるには新規スイッチが必要として数えた。新規には既存関数の引数だけで比較可能なものも含む。

最優先の結論は以下のとおり。先行保存した [switches-priority.md](switches-priority.md) にも同じ詳細を置いた。2スイッチは限定した範囲で採用候補とする。実装・solver実行はしておらず、2時間での安全な動作を実証したものではない。

## 最優先：新しい2スイッチと段階別比較

### 結論

**2案とも、対象を下記の範囲に固定すれば、小さな変更で作れる見込み。実装・solver実行はしていないため、動作確認済みとはしない。** 2時間という条件に対する工数判断もコード読解に基づく見積もりである。

| 構成 | 判断・固定する意味 |
|---|---|
| BASE | 凍結版の動作。 |
| NO_ALGEBRAIC | 既存名 `GEOSOLVER_ABLATE_NO_ALGEBRAIC`。67ad79a の実装本体はこのリポジトリにないため、実装範囲の一致は未確認。 |
| NO_SECOND_ATTEMPT | 既存名 `GEOSOLVER_ABLATE_NO_SECOND_ATTEMPT`。第2探索を止めるものとして記録あり。救済を止めるものとは別。 |
| NO_RESIDUAL_REWRITE | **採用候補**。高精度精密化の接条件・距離0・正の半径補助行に加え、最終検証の同種の接条件・点と直線の距離0の変換も止める。依存する解析微分も使わせない。検証自体とその閾値は維持。目安60–120分。 |
| NO_DIVERSE_SELECTION | **採用候補**。各探索結果から精密化へ渡す候補を、選択前の同じ台帳から生の残差ノルム順の上位20へ替える。幾何的な近接除去・seed枠を入れない。探索の初期値や救済箱の多様性は別の機構。目安60–120分。 |

全種類の式変換を一斉に削除する案、初期値・救済箱・代数枝・整数列挙まで含めて「あらゆる多様性を止め、全実行で20候補以内」にする案は、意味と予算配分の変更が広く、**2時間枠から外す**。下記の限定した比較と混同しない。

### 読んだ版と既存スイッチの根拠

- 対象コミット `60db4b679b04167175c51c479c87c22fa663fda0`。既存の `/tmp/mech-inv-clean/src/` を `git archive 60db4b6 src` の全251ファイルとバイト比較し、不一致・余分なファイルとも0。再展開による上書きは不要だった。
- `runtime/integrity.py:21–44` と同じ方式（相対名、NUL、LF正規化した本文、NUL。engine-lockを除く .py/.json/.toml）で250ファイルをハッシュし、`sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5` に一致。
- 以下のコード位置はすべてこの展開物の行番号。`E/` は `src/geosolver/engine/standard/`、`G/` は `src/geosolver/`。共有worktreeのsrcは読んでいない。
- `rg`で既存名を確認：`jssa/difficulty/capability-1024/ablation34/ablation34_driver.py:31–38` に NO_SECOND_ATTEMPT / NO_NOMAD / NO_ALGEBRAIC / NO_SCALE_CHART / NO_RESCUE / NO_ANALYTIC_JAC。ブランチの所在と差分範囲の記録は同ディレクトリ `README.md:5`。ローカルに67ad79aオブジェクトはない。したがって「既存」は記録上の存在を指し、この凍結版に環境変数が実装済みという意味ではない。
- 別の既存実験に **`GEOSOLVER_ABLATE_NO_SIGNED_TANGENCY`** がある：`jssa/results/tangency-signed/README.md:5–9`。同記録は `_smooth_zero_constraint_residuals` 全体を止めたと明記しており、今回の精密化側の残差群と対応する。ただし解析微分の整合処理までは記録から確認できない。最終検証にも別実装が見つかったため、今回の新名を既存名の完全な別名とは扱わない。
- **`GEOSOLVER_ABLATE_SEARCH_MODE`** も既存：`jssa/results/search-mode-ablation/README.md:3`。Phase Aの探索法を替える設定で、救済のMADSは維持すると記録されている。

### 1. NO_RESIDUAL_REWRITE

#### 対象群の全分岐

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

#### 最小変更案と落とし穴

1. 新しい環境変数名を `GEOSOLVER_ABLATE_NO_RESIDUAL_REWRITE` とする。`mpmath_refiner.py:1354` の実効フラグにOFF条件を追加する。これで全4呼出経路に効く。素朴な代替は直前の `evaluate_hp_residual` が返す元の残差ベクトル。
2. **必須の連動修正**：同`:1026–1037` の解析微分採用判定にも同じ実効フラグを使う。`analytic_jacobian.py:74–104` は接条件を別の滑らかな式にして微分し、`:128` に `requires_smoothing` を付ける。残差だけOFFにしてpartialの `smooth_zero_constraints=True` を残すと、行数が同じ場合に誤ったJacobianを採用しうる。`requires_smoothing=True` の計画だけ無効化し、通常の解析微分は残す。
3. `evaluation/verification_numerics.py:199,207` の2分岐にも同じOFF条件を置く。関数全体を素通しにするとabs・Area・min・論理式の処理まで外れるため、**接条件と距離の分岐だけ**を止める。論理式の葉もこの共通関数を通る。正規化済み式がevaluatorに保存されるため、各腕で新しいevaluatorを作る（同じオブジェクト上で環境変数だけ変更しない）。
4. 既存のNO_SIGNED_TANGENCYを流用する場合も上記2を確認する。それだけでは上記3が残る。NO_ANALYTIC_JACを腕全体で併用するだけでは、通常の解析微分まで同時に外す別の比較になる。

**残る代替経路**：`run_external_pipeline.py:349–353,391` の代数的前処理が良い初期点を供給し、精密化の直接受理やclosureで差が隠れる可能性がある。代数経路自身も `search/algebraic_branches.py:495` → `search/cartesian_polynomials.py:230–267` でDistance・接条件を多項式化する。これは別の前処理なのでNO_RESIDUAL_REWRITEでは止めない。NO_ALGEBRAICとの相互作用を別途見る必要がある。

既存NO_ALGEBRAICの移植位置にも注意が要る。凍結版の`run_external_pipeline.py:401`は`allow_algebraic`を`allow_integer_shortcuts`にも渡す。前処理の呼出だけを止める案と、このフラグをFalseにする案では整数二乗列挙等への影響が異なる。67ad79aの実装境界が未確認なので、既存名だけから後者まで止まると断定しない。

さらに、`evaluation/final_verifier.py:122–182` は検査だけでなく座標を最大8回補正する。上記3を入れても一般の補正・片側差分は残り、回復しうる。旧スイッチ相当の「精密化側だけOFF」では、最終検証の符号付き接条件まで代わりをする。この狭い条件を補助比較する場合は `NO_REFINEMENT_REWRITE` 等の別名で区別する。入力読込みの構成契約・OnSegmentの付加行・論理式の変換（`problem/load_problem_bundle.py:46–55`、`G/problem/incidence_residuals.py:15–67`）も残る。これらを一緒に外すと対象群以上の変更になる。

NO_SECOND_ATTEMPT・NO_RESCUE・NO_NOMAD・NO_SCALE_CHARTとはコード上の必須の同時OFF関係はない。ただし候補と残り時間を変える。基準の5構成は単独OFFとし、他の既存スイッチを暗黙に追加しない。

### 2. NO_DIVERSE_SELECTION

#### 現在の選択・重複除去・数

| 層 | コード位置と既定値 | 精密化への影響 |
|---|---|---|
| 通常の広い台帳 | `E/search/build_guard_feasible_ledger.py:17–76`。OKかつguardかつhard_feasibleから、最良scoreを最初に選び、正規化座標距離の最遠点を追加。`run_search.py:328–331` で `max(20×8,64)=160` 件。 | 160は主精密化数ではなく、救済箱の材料にもなる台帳の上限。 |
| 通常の代表 | 同`:79–115,118–136`。台帳から再び最遠点を最大20。最後にscore順へ。 | 通常は `min(20,適格候補数)`。ここには距離閾値による重複排除がないため、同座標が残る場合もある。 |
| 通常台帳が空の旧経路 | `E/search/deduplicate_search_candidates.py:24–95`。score順、seedごと最小3枠、箱幅で正規化した距離 `<1e-4` を重複除去、最大20。 | NOMADでは各runのscore上位64を母集団にする（`nomad_backend.py:133–157`）。通常経路は全recordsを使うので64制限はかからない。 |
| 入口ごとの適用 | `nomad_backend.py:143–157`、`scipy_multistart_backend.py:1381–1395`、`orchestration/run_search.py:198–213`。 | 共通関数だけの修正でもこれらに効くが、下記の直通経路を覆わない。 |
| 直通・結合経路 | `search/scalar_branch_scan.py:55–66` は既に残差順で最大20。`run_external_pipeline.py:391` は代数結果を直通。`run_search.py:332–359,504–541` は整数・有限guard・尺度座標の結果を追加し、再圧縮しない。 | **パイプライン全体の20件上限はない**。 |
| 救済・離散補完 | `run_rescue_search.py:128–143` で各箱score上位6を集めて近接除去し、`run_external_pipeline.py:482–505` で追加精密化と後続の離散補完。 | 救済は最大6箱×各6候補という別枠。返却された候補は近接除去済み。整数closureは1候補から派生候補も作る。 |

距離正規化は `E/search/coordinate_distance.py:12–16`：各軸を `max(箱幅,1e-12)` で割ってユークリッド距離。初期値選択の近接閾値 `1e-2` は別（`select_search_start_points.py:35–60`、`nomad_config.py:19–23`）。

#### 最小変更案（比較する選択点を固定）

**推奨は「探索終了→精密化」の境界で一度選び直す方式。** 共通台帳関数だけの差替えでは代数直通・追加候補を取り逃がすためである。

- `E/orchestration/run_external_pipeline.py:402–403` に小さい選択関数を挿入。母集団は `search_result.all_records`（空なら `candidates`）から、**生成経路ごとに元の適格条件を維持して**組み立てる。通常backendの適格条件は `evaluation_status==OK && guard_ok && hard_feasible`。残差は **`residual_norm_float`**。有限残差を小さい順、元の経路が保持していた非有限・未確定残差をその後に置き、同点は `(candidate_uid, 元の順序)` で安定に並べて上位20にする。NaNは比較キーだけ+infへ正規化し、評価状態は保存する。新しい有限値フィルタで元のfallback候補を消さない。seed割当と座標距離の重複除去をしない。同一来歴レコードの結合重複だけは両方式で同じ扱いにする。
- **直通経路は通常の適格フィルタに掛けない**。`algebraic_branches.py:690–711`、`scale_chart.py:74–87` の候補は `hard_feasible=None` のままで、代数候補はfloatのguard違反もHP検証へ送る設計。これらと有限guard・整数列挙の元の候補を母集団に加える。NoneをFalse扱いする一律フィルタは、選択法以外に候補生成経路を消してしまう。母集団を生成元で識別する修正を2時間で確認できなければ、この構成を外す。
- 通常の適格集合が空の場合も、既存の「不適格な探索点から精密化を試す」経路を消さない。旧fallbackと同じ候補集合・評価可否を使って上位20とする。NOMADのfallbackは各run上位64、SciPyはrecordsなので、その既存母集団を返す／識別する小さい補助が必要（`nomad_backend.py:133–157`、`scipy_multistart_backend.py:1388–1395`）。全raw recordsから新たにfallbackを作る案は比較条件を変えるため避ける。
- 選択済みの `SearchBatchResult.candidates` を `replace` し、要約も実際の精密化入力と一致させる。`all_records` と救済用の広い台帳は保存する。探索初期値・hybridの補助探索・救済箱の作り方はこのスイッチの対象外と明記する。
- 救済の**新規バッチ**にも適用する。`run_rescue_search.py:132–138` の近接除去の代わりに、直前の `rescued_candidates`（各箱score上位6を集めた最大36件）から残差順20を選んで返す。`run_external_pipeline.py:482–492` は同じ返却リストを精密化とmergeへ渡す。返却後だけを切り直すと既に除去された点を復元できない。各箱上位6という生成元の保存枠、救済箱の選び方、整数ターゲット列挙は残す。この枠まで外して全raw救済評価点の上位20にする拡張は、母集団を替える別比較として2時間枠から外す。既に精密化・検証した候補を20に切り直さない。

この定義で、主探索から精密化へ渡る数は各 `_run_pipeline_stage` の**入力バッチで最大20**。不完全な代数列挙の通常primary補完（`run_external_pipeline.py:548–575`）は別バッチなので、primary全体が20以内になるとは限らない。通常経路は数が同じことが多く、選ばれる座標が変わる。補助結果の結合で20を超えていたバッチは減る。一方、旧fallbackや救済で近接除去後が20未満だった場合は、除去を止めることで渡す数が増える場合もある。精密化は締切で途中停止し、整数closureで候補が派生する（`mpmath_refiner.py:1153–1205`）ため、**入力20でも最終検証対象が必ず20以下とは言えない**。最終検証は残差順、状態の適格判定、締切による打切りがある（`assemble_exact_results.py:159–175`）。第2attempt・救済も含む実行全体の検証数はさらに別である。

注意：現行のscoreは正規化された残差とguard罰則を含む。生の残差順という指定は、多様性に加え**順位の尺度**も替える。比較記録にはscore・生の残差の両方を残す。多様性だけの寄与に厳密に分けたい場合は、同じscore順上位20の補助比較が必要（5構成へ無断で追加しない）。

既存6スイッチに同等名は見つからなかった。新規名は `GEOSOLVER_ABLATE_NO_DIVERSE_SELECTION`。NO_ALGEBRAICで台帳の由来、NO_SECOND_ATTEMPT/NO_RESCUEで選択バッチ数、NO_NOMAD/SEARCH_MODEでrecordsの意味が変わる。NOMADのrecordsは評価点、SciPyは主に局所探索後の状態なので、台帳を混ぜた件数だけで探索努力を比較しない。

### 3. 段階別比較の入口

| 比較 | 既存の入口と取り出せるもの | 追加する小さい観測処理・注意 |
|---|---|---|
| ① 接条件：同じ候補から精密化し、直後と最終検証後を比較 | `E/orchestration/run_refinement.py:14–29` → `MpmathRefiner.refine_candidates`。入力は不変dataclassのFloatCandidate群。返値の `x_hp, residual_norm_hp, answer_hp, phase_history, *_precision_dps`（`contracts/candidate_record.py:83–159`）。後段は `assemble_exact_results.py:152`、単体検査は `evaluation/final_verifier.py:85`。 | **可能、標準の候補save/load CLIはない。** 精密化前に全入力フィールドとDSL・bounds・config・source_hashを保存し、別々のevaluatorで復元する。`initial_point_decimal` と `originating_branch_box` を落とすと代数候補の桁と枝が失われる。精密化直後を、最終検証で候補revisionが更新される前に保存する。最終検証後は `numeric_feasible_candidates` と失敗を含む `verification_records`、受理後は `candidate_records`。最終検証は補正も行うので、この2時点は必須。 |
| ① 残差・目標値誤差 | 精密化残差は書き換えをしない評価器で再評価される（`mpmath_refiner.py:1555–1571`）。最終結果に `residual_norm, normalized_residual, answer_hp, answer_uncertainty, values`。 | 比較用残差は両時点の座標を同じ評価器・同じ評価桁で測り直す。目標式の真値との差はsolver内にはないため、独立した参照値を用意して絶対誤差・必要なら相対誤差を計算。`answer_uncertainty`は誤差の見積りで、正解値との差そのものではない。失敗を落として成功点だけを比べない。 |
| ② 複数値：選択前台帳を保存し選択だけ替える | `SearchBatchResult.all_records` と `guard_feasible_ledger`（`candidate_record.py:182–191`）、`build_guard_feasible_ledger`はsolverを動かさずレコードに対して呼べる。 | **可能**。保存すべきは圧縮前の`all_records`。160件のledgerやdebug候補（既定32）だけでは足りない。bounds、score、残差、feasibility、uid、元の順序、既存fallbackの母集団も保存。BASEの特殊経路の元の`candidates`も保存して再生する。救済は`RescueSearchResult`に全recordsがなく、`run_rescue_search.py:128–132`でbox別`adapter.records`と選択前集合を追加保存する必要がある。全実行の再生ではattempt/boxごとの台帳と予算を分ける。各JSONL断片は3MB以下に分割し、切捨てで上限を守らない。 |
| ③ 保存高精度値に対しPSLQの精度と係数上限を別々に変更 | `G/exact/polynomial_search.py:246` の `find_minimal_polynomial(r, precision, max_degree, max_coeff, max_steps)`。固定次数だけなら同`:316` の `_find_polynomial_pslq`。いずれも探索や精密化を呼ばない。 | **既存関数で可能**。上位 `identify_answer` はtierに次数・係数・反復数が束ねられ、symbolic worker・π探索等も通るため純粋なPSLQ比較には下位関数を使う。precisionとmax_coeffは独立の引数。ただしprecisionは作業桁だけでなくPSLQ許容差も変える。係数上限はスケール変換後の関係に対する上限で、元の変数へ戻した最終係数の上限とは限らない。 |

PSLQの詳細：`find_minimal_polynomial`は作業桁 `max(現在のmp.dps, precision+40,80)`、下位PSLQは `max(現在のmp.dps, precision+30,60)`。許容差はprecision>100なら `10^(-(precision//2))`、それ以外は `10^(-((3*precision)//10))`（`polynomial_search.py:256,282–290,325`）。保存値は十分な桁の十進文字列、またはmpfの正確な二進タプルで保存し、低い既定mp.dpsやfloatを経由させない。元値を高い作業桁で読み、各試行は明示したworkdpsで丸めて使用する。入力の既知精度を超える桁を真の情報として扱わず、発見した関係は別の十分高精度値で確認する。

既存の同候補比較フック `jssa/results/tangency-signed/probe/sitecustomize.py:44–91` は再利用の参考になる。ただし保存は残差桁数・時間・状態が中心で、共通候補の永続化、目標値誤差、最終検証後の比較までは満たさない。

### 実装時に必要な確認（今回は未実施）

通常の解析微分を残しつつ書き換え依存の計画だけ無効になること、整数closureが元の仕様で残ること、候補選択の同点処理・空集合・20件未満・特殊経路の結合、保存復元で高精度座標とuidが変わらないことを小さい単体確認で検査する。これらが2時間で確認できなければ該当スイッチを外す。性能改善や正解数の増減は、この読解だけでは判定しない。

## 表の読み方と確認方法

対象は主にengine配下と、その呼出先のproblem・geometry/mp・exact・runtime。ファイル一覧を確認し、入口からの呼出追跡と`scale / bounds / penalty / tolerance / seed / cache / deadline / closure`等の検索で、アルゴリズム、数値安定化、候補配分、再利用を拾った。一般的な型定義、単純な委譲、表示だけの処理は別機構として水増ししない。各行の「発見」に調査経路を記した。想定問題種はコードの適用条件・数式に基づくもので、正解率や速度の改善を測った結果ではない。効果の方向だけの予想は「推測」とした。

`E/` = `src/geosolver/engine/standard/`、`G/` = `src/geosolver/`。行番号は凍結展開物のもの。CSVの場所列は省略なしのパス。変更案の位置は同じ行の「場所」を指し、複数の入口が必要なら併記した。表のスイッチ名は共通接頭辞`GEOSOLVER_ABLATE_`を省略し、CSVは完全名とした。`dps`は十進作業桁、`eps`はその場の演算精度に依存する最小刻みの尺度、`hard`はguardに幾何の定義域・非退化等を加えた適格判定。

**既存**はリポジトリの実験記録に名前・用途があるという意味で、この凍結srcに環境変数が実装済みという意味ではない。67ad79aのコード本体はローカルで確認できず、内部の細かな境界の一致は未確認。根拠は`jssa/difficulty/capability-1024/ablation34/ablation34_driver.py:31–38`と同`README.md:5`、`jssa/results/tangency-signed/README.md:5–9`、`jssa/results/search-mode-ablation/README.md:3`。新規名はすべて案。設定値を替える提案は必ずしもbooleanスイッチではない。

「可（案）」は挿入位置・代替が読めるという判断で、実装済み・動作検証済みではない。精度や受理の信頼性を弱める診断用比較はその旨を明記した。2時間枠の採否は冒頭の2スイッチに限る。入力の意味を失うもの、証拠なしに受理するものは単純OFF不可とした。

尺度の工夫は一つではない。正の相似尺度固定、探索箱、探索残差行、候補距離、差分幅、Newtonの行・列、最終検証の変数・残差、幾何カーネル、PSLQの値尺度を分けた。NO_SCALE_CHARTでこれら全部が消えるわけではない。

| 分類 | 項目数 | 既存 | 新規 | 単純OFF不可 |
|---|---:|---:|---:|---:|
| 入力・探索領域・制約の表現 | 14 | 1 | 9 | 4 |
| 数値評価・幾何の安定化・再利用 | 22 | 0 | 19 | 3 |
| 初期値・探索と探索中の尺度 | 19 | 2 | 17 | 0 |
| 候補選択・重複除去 | 7 | 0 | 6 | 1 |
| 代数的前処理・有限列挙 | 14 | 1 | 12 | 1 |
| 高精度精密化・微分・残差変換 | 25 | 7 | 18 | 0 |
| 最終検証と答の誤差見積り | 16 | 0 | 13 | 3 |
| 厳密値復元・PSLQ | 14 | 0 | 12 | 2 |
| 時間配分・追加探索・seed・実行資源 | 17 | 2 | 12 | 3 |

## 入力・探索領域・制約の表現

| ID・名前 | 何の困難のためか | 場所 | 既定値・閾値 | スイッチと最小変更案 | 想定する問題種・根拠 | 発見・注意 |
|---|---|---|---|---|---|---|
| M001 構成契約と定義域を明示する | 未定義の構成を零残差として通さない | E/problem/load_problem_bundle.py:46; E/problem/compile_problem_hard_feasibility.py:1 | 構成契約→接続条件→論理等式→定義域guardを付加 | 単純OFF不可: なし。単純OFF不可: 半径正・直線非退化など問題の意味が変わる。評価費用だけの比較には別実装が必要 | 円・交点・三角形等。根拠: 構成式からhard条件を生成 | 発見: load_problem_bundleからdomain_bounds・guardコンパイルを追跡。 |
| M002 固定変数を構成へ代入 | 自由度0の軸を最適化器へ渡さない | E/problem/load_problem_bundle.py:56 | 数学的上下限が一致する変数を消去 | 新規: NO_FIXED_VARIABLE_ELIMINATION。可（案）: 同位置の消去を省き、固定軸を扱える入口を補う | 固定パラメータ。根拠: lower==upper判定 | 発見: load_problem_bundleからdomain_bounds・guardコンパイルを追跡。境界幅0を嫌うSciPyとの連動が必要。単なる1行OFFではない |
| M003 変数0の問題を直接評価する | 未知数がない問題に探索器を起動する費用 | E/orchestration/run_external_pipeline.py:818 | float/guardと120dpsの残差・答を評価し、通常の最終検証・厳密復元へ送る | 単純OFF不可: なし。単純OFF不可: 0次元の通常探索器への委譲はAPIの前提を満たさない。直接評価と同値の専用代替が必要 | 固定変数消去後・定数図形。根拠: 空座標のdirect_evaluation専用経路 | 発見: load_problem_bundleからdomain_bounds・guardコンパイルを追跡。 |
| M004 パラメータの数学的区間 | 線分・弧・多角形の外側を解としない | G/problem/domain_bounds.py:52 | 線分・弧は[0,1]、多角形パラメータは開区間を保持 | 単純OFF不可: なし。単純OFF不可: 探索箱と異なり問題の定義域。推定だけ外してもguardは残す | PointOnSegment/Arc等。根拠: 構成別の区間付加 | 発見: load_problem_bundleからdomain_bounds・guardコンパイルを追跡。 |
| M005 アフィンguardから探索境界を推定 | 狭い許容領域を無駄に探す | G/problem/domain_bounds.py:127; G/problem/domain_bounds.py:235 | 有理数・厳密定数による上下限、開閉を保存 | 新規: NO_GUARD_BOUND_INFERENCE。可（案）: 探索箱への反映だけ省く。元guardとHPの数学的境界は維持 | 狭いBound/AssumeGt等。根拠: アフィン係数解析 | 発見: load_problem_bundleからdomain_bounds・guardコンパイルを追跡。 |
| M006 定数と依存関係による探索箱の大きさ | 桁の異なる入力を一律の箱で探す | G/problem/domain_bounds.py:184 | 各軸初期10、依存する定数の2倍、10～20000。指数・枝番号を尺度に含めない | 新規: NO_SEARCH_BOX_SCALING。可（案）: 未拘束端を固定±10へ。明示境界は保持 | 大座標・大半径。根拠: 構成依存を遡って定数を収集 | 発見: load_problem_bundleからdomain_bounds・guardコンパイルを追跡。 |
| M007 非有理境界の外向き丸め | float丸めで真の端点を箱の外にする | G/problem/domain_bounds.py:241 | 非Fractionの下端をnextafter(-inf)、上端をnextafter(+inf) | 新規: NO_OUTWARD_BOUND_ROUNDING。可（案）: 探索箱でのnextafterだけ省く | π等の境界上の解。根拠: 厳密guardを最終権威として箱だけ拡張 | 発見: load_problem_bundleからdomain_bounds・guardコンパイルを追跡。 |
| M008 NOMADの未拘束端拡張 | 推定箱の端で探索を止める | E/search/nomad_backend.py:17; E/search/nomad_backend.py:71; E/search/nomad_config.py:24 | 箱幅の25%。数学的に固定された端は拡張しない | 新規: NO_BOUND_EXPANSION。可（案）: bound_expansion_ratio=0 | 推定箱に近い解。根拠: infer_bound_expansion_locksを使用 | 発見: load_problem_bundleからdomain_bounds・guardコンパイルを追跡。 |
| M009 正の尺度座標を1に固定 | 同形図形の大きさの自由度で代数列挙が連続になる | E/problem/positive_scale_chart.py:23; E/search/scale_chart.py:12 | 正の尺度、全構成・guardの同変性、答の次数0を確認。1変数減らし1.5秒の代数呼出 | 既存: NO_SCALE_CHART。可（記録上）: 尺度候補を追加する呼出を省く | 相似不変な答。根拠: 変換後の全条件とanswer degreeを確認 | 発見: load_problem_bundleからdomain_bounds・guardコンパイルを追跡。既存名はablation34記録。通常の距離・行・列スケーリングは残る |
| M010 OnSegment等の接続条件を残差にも加える | 不等式guardだけでは等式面へ近づきにくい | G/problem/incidence_residuals.py:15; E/problem/load_problem_bundle.py:47 | 接続条件の零残差を追加、元の条件も保持 | 新規: NO_INCIDENCE_RESIDUALS。可（案）: 付加する等式行だけ省く | 線分上・図形への所属条件。根拠: incidence loweringの追加行 | 発見: load_problem_bundleからdomain_bounds・guardコンパイルを追跡。 |
| M011 論理等式のベクトル化 | OR条件をboolean罰則だけで解く | G/problem/logical_equalities.py:46; G/problem/logical_equalities.py:132; E/evaluation/logical_vectors.py:43 | 最大32節・16行。各節の最大絶対残差が最小の節を選び、同点は前の節 | 新規: NO_LOGICAL_RESIDUALS。可（案）: 追加残差とlogical_planを一緒に省く。元guardは維持 | 等式の選言。根拠: compare ==のAND/ORのみ展開 | 発見: load_problem_bundleからdomain_bounds・guardコンパイルを追跡。NO_RESIDUAL_REWRITEの対象外。通常guardだけになるため探索難度は大きく変わりうる |
| M012 等式残差と不等式guardを分離 | 小さな残差だけでは不等式や定義域を保証しない | E/evaluation/evaluate_float_residual.py:1; E/evaluation/guard_penalty.py:25; E/evaluation/verification_domains.py:218 | 等式はノルム最小化、不等式は罰則・hard判定・最終誤差付き判定 | 単純OFF不可: なし。単純OFF不可: guardの最終受理を省くと別問題になる。探索罰則だけは別項でOFF可 | 狭い領域・開境界。根拠: 残差評価とguard評価が別入口 | 発見: load_problem_bundleからdomain_bounds・guardコンパイルを追跡。 |
| M013 guard違反量と余裕の正規化 | 単位や大きさにより罰則が偏る | E/interpreter/guards/compile.py:436; E/interpreter/guards/compile.py:589 | 通常許容差10^-max(12,dps//2)。正のgap/max(1,尺度値)。最終検証は別規則 | 新規: NO_GUARD_MARGIN_SCALING。可（案）: 探索用marginの除算を1へ。最終検証は維持 | 大小混在の比較式。根拠: lhs/rhsでmargin尺度を決める | 発見: load_problem_bundleからdomain_bounds・guardコンパイルを追跡。閾値単独比較は新しい設定引数を追加。最終検証の100×誤差とは混同しない |
| M014 float hard条件の退化余裕 | ほぼ潰れた図形で探索が偽の極小へ寄る | E/evaluation/_hard_feasibility_core.py:36; E/evaluation/_hard_feasibility_core.py:169 | float: 直線・除外交点1e-12、三角形1e-14。HPは正であること（閾値0） | 新規: NO_FLOAT_MARGIN_FLOOR。可（案）: floatの閾値だけ0へ。定義域とHP検証は保持 | 薄い三角形・近接点。根拠: allow_floatで閾値を切替 | 発見: load_problem_bundleからdomain_bounds・guardコンパイルを追跡。 |

## 数値評価・幾何の安定化・再利用

| ID・名前 | 何の困難のためか | 場所 | 既定値・閾値 | スイッチと最小変更案 | 想定する問題種・根拠 | 発見・注意 |
|---|---|---|---|---|---|---|
| M015 float段階でも数値幾何を53bitで評価 | 探索中に記号計算を繰り返す費用 | E/evaluation/float_expressions.py:25 | mp.workprec(53)の数値カーネル。結果をfloat残差へ | 新規: FLOAT_EVAL_PRECISION。可（案）: 同位置の精度を設定化して比較 | 構成の多い問題。根拠: 全残差callbackがこの入口 | 発見: 評価器の呼出先とscale/tolerance/cacheのrg検索。旧記号評価へ戻すのは大変更。これは精度比較用の新規設定案 |
| M016 残差ノルムのhypot退避 | 二乗和のoverflow/underflow | E/evaluation/float_expressions.py:52 | 通常はsqrt(sum(r²))、非有限・subnormal域はmath.hypot | 新規: NO_SAFE_FLOAT_NORM。可（案）: 通常式だけにする | 極大・極小残差。根拠: sys.float_info.minと非有限で分岐 | 発見: 評価器の呼出先とscale/tolerance/cacheのrg検索。 |
| M017 float→HPの明示境界と型検査 | 低精度値を高精度と誤認する | E/precision/type_guards/boundary_float_to_mpf.py:50; E/precision/type_guards/strict_to_mpf.py:26 | IEEE floatを直接mpf化、非有限・高精度経路へのfloat混入を拒否 | 単純OFF不可: なし。単純OFF不可: 精度保証の前提を失う。検査費用の比較は入力同一性を別途保証する必要 | 高桁精密化全般。根拠: strict_to_mpfの型別拒否 | 発見: 評価器の呼出先とscale/tolerance/cacheのrg検索。 |
| M018 直線係数の単位長正規化 | 同じ直線を係数倍したとき距離が変わる | G/geometry/mp/mp_core_types.py:67 | (a,b,c)/sqrt(a²+b²) | 新規: RAW_LINE_COEFFICIENTS。可（案）: 素朴な非正規化表現への置換は、distance・接条件の分母も同時修正 | 大小の直線係数。根拠: distance_to_pointが除算なしで利用 | 発見: 評価器の呼出先とscale/tolerance/cacheのrg検索。横断的な不変条件。2時間の優先スイッチには不採用、実装量は未見積り |
| M019 外接円を原点移動して計算 | 遠い原点からの二乗で桁落ちする | G/geometry/mp/mp_impl.py:238 | Aを原点にした差分、外積はmp.fdot | 新規: NO_CIRCUMCIRCLE_TRANSLATION。可（案）: 元座標の行列式による式へ差替え | 大きな平行移動・小図形。根拠: 平行移動してから二乗 | 発見: 評価器の呼出先とscale/tolerance/cacheのrg検索。 |
| M020 角度を外積・内積のatan2で計算 | acosの端点付近で角度の桁が落ちる | G/geometry/mp/mp_line_relations.py:73 | mp.fdotで積和、atan2(abs(cross),dot)。直線角はabs(dot) | 新規: NAIVE_ANGLE_ACOS。可（案）: 同じ角度範囲のacos式へ替え、零ベクトル拒否は保持 | ほぼ平行・直角。根拠: fdotの一回丸めとatan2 | 発見: 評価器の呼出先とscale/tolerance/cacheのrg検索。 |
| M021 面積の尺度・精度に応じた退化閾値 | 小図形を固定絶対閾値で棄却する | G/geometry/mp/mp_impl.py:204; E/config/environment/mp_degenerate_floors.py:14 | max(abs_floor,max(32eps,rel_floor)×辺長²)。実呼出の両floor既定0 | 新規: FIXED_AREA_FLOOR。可（案）: 既存GEOSOLVER_MP_DEGENERATE_*で固定floor比較可。OFF名を使うならラッパ追加 | 極小・細長い図形。根拠: 実呼出はrelの関数既定1e-30を0で上書き | 発見: 評価器の呼出先とscale/tolerance/cacheのrg検索。既存環境設定で比較可能だが既存GEOSOLVER_ABLATE_*ではないため新規に分類 |
| M022 内接円・接点の小さい図形への閾値 | 短辺・小周長で除算が不安定になる | G/geometry/mp/mp_incircle_helpers.py:39; G/geometry/mp/mp_incircle_helpers.py:55; G/geometry/mp/mp_incircle_helpers.py:83 | 接点の短辺がtol=10^(-(dps-10))未満なら端点を返す。周長&lt;1e-30で辞退、面積尺度はmax(1,辺長) | 新規: NO_INCIRCLE_FIXED_FLOORS。可（案）: 固定周長floorを0、尺度の下限1を外す診断分岐。真の零長・零面積は拒否 | 微小な内接円・接点。根拠: 専用カーネルの閾値 | 発見: 評価器の呼出先とscale/tolerance/cacheのrg検索。外接円と同じ尺度規則ではない。接点の短辺代替だけを比べるなら別スイッチが必要 |
| M023 多角形の相対閾値 | 大平行移動による桁落ち | G/geometry/mp/mp_polygon_checks.py:27 | max(10^-(dps-10),16n eps×座標尺度/直径) | 新規: FIXED_POLYGON_TOLERANCE。可（案）: 相対閾値を固定値にする診断設定 | 多角形の凸性・交差。根拠: 直径と座標の比で相殺を見積もる | 発見: 評価器の呼出先とscale/tolerance/cacheのrg検索。受理条件も変わりうるため、cache比較と分ける |
| M024 多角形の判定cache | 同じ形の凸性・交差を再検査する費用 | G/geometry/mp/mp_polygon_checks.py:171 | LRU512、mp.precと正確な二進座標が鍵 | 新規: NO_POLYGON_CACHE。可（案）: mp_is_convex/mp_has_self_intersectionから_uncachedを直接呼ぶ | 頂点を再利用する問題。根拠: 可変MPPointのidや近接比較を鍵にしない | 発見: 評価器の呼出先とscale/tolerance/cacheのrg検索。 |
| M025 交点の枝選択と間隔証拠 | 近い別の交点や同点を取り違える | G/geometry/mp/mp_primitives_intersections.py:20; G/geometry/mp/mp_primitives_intersections.py:50 | 許容差10^(-0.8dps)×距離尺度、辞書順n、near/far同点は拒否。excludeは候補間隔で余裕を測る | 単純OFF不可: なし。単純OFF不可: n/near/far/excludeは入力の意味。枝追跡費用のみ外すには別の検証証拠が必要 | 複数交点・接点近傍。根拠: selectorごとにtraceとmarginを生成 | 発見: 評価器の呼出先とscale/tolerance/cacheのrg検索。 |
| M026 構成から得た円上の所属証拠 | 数値近接だけでは所属を確定できない | G/geometry/mp/mp_core_types.py:105 | 定義点・パラメータ点の状態と座標を保持、変更で失効 | 新規: NO_INCIDENCE_WITNESS。可（案）: 証拠の再利用だけ止め、通常の数値経路へ | 外接円上の点・接線構成。根拠: _has_proven_incidenceは近接閾値を使わない | 発見: 評価器の呼出先とscale/tolerance/cacheのrg検索。 |
| M027 必要な構成だけ遅延評価 | 答やguard専用の構成を残差ごとに再計算する | E/evaluation/snapshots.py:46; E/evaluation/snapshots.py:132 | DSL順を維持し式の依存先だけmaterialize、失敗も記録 | 新規: NO_CONSTRUCTION_SLICING。可（案）: 全構成を同じ順で評価する。partial時のエラー処理を合わせる | 構成の多い問題。根拠: requiredが依存先を逆順追跡 | 発見: 評価器の呼出先とscale/tolerance/cacheのrg検索。無関係な未定義構成まで失敗させないよう調整が必要 |
| M028 座標・精度ごとの評価snapshot | 残差・guard・hard・答の同じ計算を重複する | E/evaluation/snapshots.py:239; E/evaluation/snapshots.py:262 | LRU256、(演算種,mp.prec,全mpf二進タプル)。traceを再生 | 新規: NO_EVALUATION_CACHE。可（案）: getで毎回新snapshot。座標を丸める代替は使わない | 候補再検査・差分。根拠: 同一座標で評価を共有 | 発見: 評価器の呼出先とscale/tolerance/cacheのrg検索。 |
| M029 定数構成・scalar葉の再利用 | 変数に依らない長い式を再評価する | E/evaluation/snapshots.py:139; E/evaluation/snapshots.py:175; E/evaluation/snapshots.py:253 | 精度別定数bucket最大32、scalar cache最大512 | 新規: NO_CONSTANT_CACHE。可（案）: 定数bucketとscalar memoの取得・保存だけ無効化 | 定数幾何の多い問題。根拠: variable_dependentで分離 | 発見: 評価器の呼出先とscale/tolerance/cacheのrg検索。 |
| M030 論理式の葉・節の遅延共有 | AND/ORの同じ葉を何度も評価する | E/evaluation/logical_vectors.py:14 | 1座標1精度で葉・score・選択を共有、証拠を再生 | 新規: NO_LOGICAL_LEAF_CACHE。可（案）: leaf/scoreのmemoだけ省き比較順は維持 | 共有葉の多い選言。根拠: leaves/scores辞書 | 発見: 評価器の呼出先とscale/tolerance/cacheのrg検索。節選択法を替えるスイッチとは別 |
| M031 静的解析・式コンパイルのcache | 反復ごとに依存関係やASTを作り直す | E/problem/analysis_plan.py:17; G/problem/ir/compiler.py:193 | solve内bounds/整数条件/依存関係を保持。式compile LRU各1024 | 新規: NO_STATIC_ANALYSIS_CACHE。可（案）: 各getterで再計算しコンパイルcacheを迂回 | 多数候補・大きな式。根拠: cached_property/lru_cacheを確認 | 発見: 評価器の呼出先とscale/tolerance/cacheのrg検索。時間比較用。数値点に依存する値はここに置かれない |
| M032 guardの評価を少なくとも80桁で行う | float段階の極小marginが丸めで消える | E/evaluation/guard_penalty.py:35; E/evaluation/guard_penalty.py:69 | max(ambient dps,80)。残差callbackの53bitとは別 | 新規: NO_GUARD_PRECISION_FLOOR。可（案）: 探索中だけ53bitに固定する分岐。最終検証は維持 | 狭いguard・相殺。根拠: guard評価入口に独立のworkdps | 発見: 評価器の呼出先とscale/tolerance/cacheのrg検索。通常worker ambient&gt;=180なので実際には180桁以上になる呼出もある |
| M033 数値literalを元の文字列からHP化 | DSLの十進定数をPython floatに丸める | G/problem/ir/compiler.py:105; E/evaluation/exact_constants.py:29 | ast.get_source_segment→mpf文字列/厳密Rational。boolは除外 | 単純OFF不可: なし。単純OFF不可: 定数の意味を変える。丸めを入れる実験は精度劣化の別条件 | 小数・大桁の定数。根拠: AST値reprより元sourceを優先 | 発見: 評価器の呼出先とscale/tolerance/cacheのrg検索。 |
| M034 弧中点の対蹠点で角度式へ退避 | 向かい合う半径の和が0で割れない | G/geometry/mp/mp_primitives.py:36; G/geometry/mp/mp_primitives.py:117 | 閾値10^(-0.8dps)×max(半径成分,半径,1)。小さい半径和はatan2+π/2の2候補 | 新規: NO_ARC_MIDPOINT_FALLBACK。可（案）: 完全な零和は未定義として辞退し、それ以外は和の正規化だけ使う | 半円・ほぼ半円。根拠: sum_normにより式を切替 | 発見: 評価器の呼出先とscale/tolerance/cacheのrg検索。枝のincluding/excluding選択は維持。OFFで定義できない形が増えうる |
| M035 特殊三角形中心の斉次な辺二乗式 | 逆三角関数・消えるsinで特異になる | G/geometry/mp/mp_triangle_centers_special.py:13 | X13～X16、辺二乗/max辺二乗、積の重心重み、32epsで有限性検査 | 新規: NAIVE_SPECIAL_TRIANGLE_CENTER。可（案）: 通常の三線座標の三角関数式を同じ定義域で実装して比較 | X13～16・特殊角近傍。根拠: inverse trigとsin除算を避ける | 発見: 評価器の呼出先とscale/tolerance/cacheのrg検索。新しい代替式が必要。2時間の優先候補には含めない |
| M036 整数条件の滑らかな探索残差 | 丸め距離の不連続な勾配 | G/geometry/mp/mp_number_constraints.py:16 | IsInteger(x)=sin²(πx)。素数は丸め整数isprime確認、tol=max(100eps,1e-100)、未達には追加罰則 | 新規: NAIVE_INTEGER_RESIDUAL。可（案）: 整数残差をabs(x−nearest_integer)へ替える。素数判定は保持 | 整数・素数制約。根拠: 数値述語の専用実装 | 発見: 評価器の呼出先とscale/tolerance/cacheのrg検索。整数closureは後段の別機構。素数の有限lookup上限はない |

## 初期値・探索と探索中の尺度

| ID・名前 | 何の困難のためか | 場所 | 既定値・閾値 | スイッチと最小変更案 | 想定する問題種・根拠 | 発見・注意 |
|---|---|---|---|---|---|---|
| M037 一様probeと再利用 | 探索前に場所と残差尺度の見当を付ける | E/orchestration/run_initial_probe.py:20; E/orchestration/run_initial_probe.py:118 | 50点/seed。関数既定seed0..4、productionはprimary1・fallback5。random.Random(seed) | 新規: NO_RANDOM_PROBE。可（案）: probe数を0にし既存の代替startを利用。scale推定も使えなくなる | 広い箱。根拠: seed別一様点の生成 | 発見: run_initial_probe→run_search→backendとsamplerの呼出を追跡。cache鍵は箱・seed・点数・index。独立の寄与を測るなら固定probeを再生 |
| M038 残差行ごとの尺度推定 | 大きい単位の式だけが目的関数を支配する | E/orchestration/run_initial_probe.py:65; E/evaluation/scaled_score.py:1 | 正の残差中央値。&gt;1e-12が2行以上かつ尺度比&gt;=10で有効、極小行は幾何平均のfloor | 新規: NO_RESIDUAL_SCALING。可（案）: constraint_scalesを全1（またはNone）に統一 | 長さ・面積等の混在。根拠: 行ごとの中央値で割る | 発見: run_initial_probe→run_search→backendとsamplerの呼出を追跡。NOMADのscoreとSciPyの残差へ伝播。manifold追加後には尺度再推定しない |
| M039 初期点のguard優先と近接除去 | 不適格点や同じ場所から何度も出発する | E/search/select_search_start_points.py:35 | guard優先→score、箱幅正規化距離1e-2で除去。空なら対角線分点 | 新規: NO_START_DEDUP。可（案）: 同じ並びの先頭から必要数を採り距離判定を省く | 同じ谷にprobeが集中する問題（推測）。根拠: 近接点を飛ばす | 発見: run_initial_probe→run_search→backendとsamplerの呼出を追跡。NO_DIVERSE_SELECTIONでは残す |
| M040 距離条件の円周初期値 | 面積の小さい等式面に一様点が乗らない | E/search/sampling/manifold.py:28; E/search/sampling/manifold.py:279 | 固定点から正距離のPoint(x,y)へ円周12点、他軸は中央、guard確認 | 新規: NO_DISTANCE_MANIFOLD_SEEDS。可（案）: DistanceManifoldSamplerを戦略列から外す | 固定長の点。根拠: 支持するDistance構文だけを検出 | 発見: run_initial_probe→run_search→backendとsamplerの呼出を追跡。 |
| M041 アフィンguard内点のLP | 一様probeにguard可行点がない | E/search/sampling/affine_guards.py:101; E/search/sampling/affine_guards.py:203 | 既存guard可行点0の時だけ。正規化LP、余裕&gt;1e-9、HiGHS presolve、1thread、最大0.25秒 | 新規: NO_AFFINE_GUARD_SAMPLER。可（案）: AffineGuardSamplerを外す | 狭い多面体。根拠: 線形不等式の内点を探索 | 発見: run_initial_probe→run_search→backendとsamplerの呼出を追跡。 |
| M042 内点からhit-and-runで広げる | LPの1点だけでは探索が偏る | E/search/sampling/affine_guards.py:159 | 32点、burn-in=3×次元、座標方向とGaussian方向を交互、区間の5～95% | 新規: NO_GUARD_HIT_AND_RUN。可（案）: LP内点のみ返す | 細長い許容領域。根拠: 方向別の可行線分を計算 | 発見: run_initial_probe→run_search→backendとsamplerの呼出を追跡。 |
| M043 NOMADの大域探索 | 滑らかでない残差・隠れた定義域 | E/orchestration/run_search.py:360; E/search/nomad_backend.py:59 | primary DISCO-MADS、標準200BB/seed、sanity100 | 既存: NO_NOMAD。可（記録上）: NOMAD呼出を外す既存実験名。代替SciPyの時間を固定して比較 | 非滑らか・無効点の多い問題。根拠: blackboxの失敗信号とDISCO設定 | 発見: run_initial_probe→run_search→backendとsamplerの呼出を追跡。ablation34で名前確認。救済NOMADまで含むかは67ad79a本体未確認 |
| M044 DISCO-MADSと通常MADSの切替 | 不連続な隠れ制約を探索する | E/search/nomad_config.py:61; E/contracts/external_pipeline_config.py:60 | global=disco_mads、rescue=mads。BB_OUTPUT_TYPE OBJ | 既存: SEARCH_MODE。可（記録上）: 値をmadsへ。Phase Aのsearch_modeを替える既存実験 | 幾何が未定義になる領域。根拠: DISCO_MADS_OPTIMIZATION true/false | 発見: run_initial_probe→run_search→backendとsamplerの呼出を追跡。jssa/results/search-mode-ablation/README.md:3で既存名を確認。救済のmadsは維持 |
| M045 NOMAD無効点をhidden constraintとして通知 | NaNを普通の良い評価値として扱う | E/search/nomad_blackbox_adapter.py:53; E/search/nomad_config.py:8 | hidden設定true、無効出力1e20、評価失敗を記録 | 新規: NO_HIDDEN_CONSTRAINT_MODE。可（案）: 失敗を有限大罰則の有効評価に替える。最終検証は維持 | 構成失敗の多い問題。根拠: invalid callbackの戻り値とhidden設定 | 発見: run_initial_probe→run_search→backendとsamplerの呼出を追跡。無効点を候補受理する変更ではない |
| M046 NOMAD hard違反の罰則 | 残差が小さくても幾何的に不適格 | E/search/nomad_blackbox_adapter.py:119; E/search/nomad_config.py:18 | 正規化残差二乗和+hard不適格なら1e6 | 新規: NO_NOMAD_GUARD_PENALTY。可（案）: 探索scoreのguard_penalty=0。候補の適格判定は保持 | 狭いguard・退化極小。根拠: hard_feasibleで罰則加算 | 発見: run_initial_probe→run_search→backendとsamplerの呼出を追跡。 |
| M047 SciPyのguard・hard補助残差 | 連続最適化を許容領域へ導く | E/search/scipy_multistart_backend.py:453 | 残差末尾に10×guard違反、10×hard罰則。hard失敗1e3、guard例外1e6、無効vector1e10 | 新規: NO_SCIPY_GUARD_PENALTY。可（案）: 補助2行を0にする。行数と最終hard検査を保持 | 不等式のある局所探索。根拠: augmented residual生成 | 発見: run_initial_probe→run_search→backendとsamplerの呼出を追跡。marginありなら1e-6/max(margin,1e-30)。通常include_margins=Falseなので常に効くとは限らない |
| M048 Halton多始点 | 少ない初期値では狭い吸引域を逃す | E/search/scipy_multistart_backend.py:36; E/search/scipy_multistart_backend.py:272 | scramble付きHalton320、burn-in3、単位箱から各軸へ写像 | 新規: NO_HALTON_STARTS。可（案）: 同数のseed固定一様乱数へ替える | 多峰性（推測）。根拠: 各局所探索のstart列を分散生成 | 発見: run_initial_probe→run_search→backendとsamplerの呼出を追跡。 |
| M049 中央・対角の固定anchor | 低差異列が規則的な場所を避ける | E/search/scipy_multistart_backend.py:251 | 各軸0.2/0.4/0.6/0.8、中央、対角点 | 新規: NO_ANCHOR_STARTS。可（案）: anchor列だけ省く | 中央や対称な解（推測）。根拠: 箱内の決定的anchorを追加 | 発見: run_initial_probe→run_search→backendとsamplerの呼出を追跡。 |
| M050 seedをまたぐ浅い探索とstartの交互順序 | 最初のseedや長い末尾が予算を独占する | E/search/scipy_multistart_backend.py:297; E/search/scipy_multistart_backend.py:436 | 追加点・次元依存Halton・anchorを交互、各seedの短いprefixを先に処理 | 新規: NO_INTERLEAVED_STARTS。可（案）: 同じstart集合をseedごとの単純順にする | 短時間・多峰性（推測）。根拠: prefixの全seed処理後にtail | 発見: run_initial_probe→run_search→backendとsamplerの呼出を追跡。 |
| M051 劣決定ならPowell、通常はLM | 残差行より変数が多いLMが使えない | E/search/scipy_multistart_backend.py:563 | nvars&gt;制約数でPowell最大400・ftol1e-16、通常LM最大80評価・tol1e-14 | 新規: NO_POWELL_FALLBACK。可（案）: 劣決定時の候補生成を省きTRFに任せる | 自由度が残る問題。根拠: 次元数による分岐 | 発見: run_initial_probe→run_search→backendとsamplerの呼出を追跡。単に全件LMへ替えるとAPI条件違反になりうる |
| M052 有界TRFを第二の局所法にする | LMが箱外や不適格な谷へ出る | E/search/scipy_multistart_backend.py:749; E/search/scipy_multistart_backend.py:791 | Halton24start、最大1200評価。hard/guard/有限/残差順でstartを選ぶ | 新規: NO_BOUNDED_TRF。可（案）: TRF familyを省く | 境界近傍。根拠: bounds付きleast_squares | 発見: run_initial_probe→run_search→backendとsamplerの呼出を追跡。 |
| M053 1変数の全行符号反転走査 | 一つの局所解だけで止まり複数根を逃す | E/search/scalar_branch_scan.py:19; E/search/scipy_multistart_backend.py:868; E/search/scipy_multistart_backend.py:1019 | 最大2秒、grid=max(81,min(401,BB+1))、標準201。端点とnextafter、全残差行をbrentq | 新規: NO_SCALAR_SCAN。可（案）: scalar prepassとbackend内scanをともに省く | 1変数の複数根。根拠: 各行の符号変化を集め全系で後検証 | 発見: run_initial_probe→run_search→backendとsamplerの呼出を追跡。brentq max80、xtol最小subnormal、rtol4eps |
| M054 1変数の接根・最良grid点も保存 | 偶数重根は符号が変わらない | E/search/scipy_multistart_backend.py:965; E/search/scipy_multistart_backend.py:1088 | 局所最小の谷上位10、minimize xatol1e-11/max80、raw grid上位8も保存、完全同値floatのみ除去 | 新規: NO_SCALAR_BASIN_MINIMIZATION。可（案）: 谷の最小化だけ省き符号走査とraw候補を保持 | 接根・二重根。根拠: residual normの谷を別探索 | 発見: run_initial_probe→run_search→backendとsamplerの呼出を追跡。 |
| M055 有限guardの枝固定探索 | 離散的な等式選言を連続探索で見つけにくい | E/search/finite_guard_search.py:35; E/search/finite_guard_search.py:149; E/search/finite_guard_search.py:240 | 1軸2～16択、最大6軸/256組、compile0.25秒。探索min(12秒,予算20%)、良点3+乱数2、最大160評価/tol1e-11 | 新規: NO_FINITE_GUARD_SEARCH。可（案）: 追加search呼出だけ省く | 離散座標のOR条件。根拠: 有理アフィン値を列挙してfree軸を最適化 | 発見: run_initial_probe→run_search→backendとsamplerの呼出を追跡。元guardは残る。残差&lt;=1e-5で追加、hard状態は記録し後段でも検査。予算指定なしのlocal既定は2.4秒 |

## 候補選択・重複除去

| ID・名前 | 何の困難のためか | 場所 | 既定値・閾値 | スイッチと最小変更案 | 想定する問題種・根拠 | 発見・注意 |
|---|---|---|---|---|---|---|
| M056 可行候補の広い台帳 | 低残差の同じ谷だけに探索結果が偏る | E/search/build_guard_feasible_ledger.py:17; E/orchestration/run_search.py:328 | OK&amp;&amp;guard&amp;&amp;hard。最良scoreの後に最遠点。上限max(20×8,64)=160 | 新規: NO_DIVERSE_SELECTION。可（案）: 精密化境界でraw台帳から残差上位20へ。台帳自体は観測・救済用に保存 | 複数の配置・複数値（推測）。根拠: 残差順位だけでなく距離で追加 | 発見: SearchBatchResultの全生成元と精密化への境界を追跡。優先資料の経路別適格条件を必須とする。160は精密化入力数ではない |
| M057 台帳から多様な代表20件 | HP計算を別々の吸引域へ配る | E/search/build_guard_feasible_ledger.py:79; E/orchestration/run_external_pipeline.py:402 | 最遠点で最大20、最後はscore順。通常経路には近接閾値なし | 新規: NO_DIVERSE_SELECTION。可（案）: 同じ適格母集団をresidual_norm_float順に安定選択 | 多根・同じ解への集中（推測）。根拠: 最小座標距離の最大化 | 発見: SearchBatchResultの全生成元と精密化への境界を追跡。生残差順への変更はscoreの尺度変更も含む。同点uid+元順序を固定 |
| M058 旧fallbackのseed枠と近接除去 | 可行台帳が空でも探索点を精密化へ渡す | E/search/deduplicate_search_candidates.py:24; E/search/nomad_backend.py:133; E/search/scipy_multistart_backend.py:1388 | seedごと最小3、距離&lt;1e-4除去、最大20。NOMAD母集団は各run上位64 | 新規: NO_DIVERSE_SELECTION。可（案）: 旧fallbackの同じ母集団から残差順20。空集合の扱いを維持 | 全float点がhard不適格の問題。根拠: ledger空時のfallback | 発見: SearchBatchResultの全生成元と精密化への境界を追跡。all_recordsへ無条件に母集団を広げない。通常の最遠点経路とは別 |
| M059 箱幅で座標距離を正規化 | 単位の大きい軸だけが多様性を決める | E/search/coordinate_distance.py:12 | delta_i/max(width_i,1e-12)のL2 | 新規: NO_COORDINATE_DISTANCE_SCALING。可（案）: distance関数を生座標L2へ替える | 軸の尺度が異なる問題。根拠: 台帳・重複除去・救済が共通距離を使う | 発見: SearchBatchResultの全生成元と精密化への境界を追跡。positive_scale_chartとは別。NO_DIVERSE_SELECTIONでは初期値・救済側に残る |
| M060 直通・追加候補を一律に再圧縮しない | 有限列挙した別枝を通常選択で消す | E/orchestration/run_search.py:332; E/orchestration/run_search.py:504; E/orchestration/run_external_pipeline.py:391 | 代数候補直通、整数・有限guard・尺度候補を結合。全経路共通の20件上限なし | 新規: NO_DIVERSE_SELECTION。可（案）: 402行の境界で生成元の適格条件を保持して選び直す | 有限列挙・補助探索。根拠: tuple連結と直通代入 | 発見: SearchBatchResultの全生成元と精密化への境界を追跡。algebraic/scale_chartはhard=None。通常フィルタの一律適用は禁止。詳細は優先資料 |
| M061 救済候補の近接除去 | 同じ谷の重複候補で追加精密化を埋める | E/orchestration/run_rescue_search.py:128; E/orchestration/run_rescue_search.py:132 | 各箱score上位6、合計最大36から距離1e-4で除去。全体箱幅で距離正規化 | 新規: NO_DIVERSE_SELECTION。可（案）: 132行のdedupの代わりに同じ最大36件を残差順20へ。返却後でなく除去前に変更 | 複数の救済箱が同じ谷へ入る場合（推測）。根拠: rescued_candidatesを共通dedupへ渡す | 発見: SearchBatchResultの全生成元と精密化への境界を追跡。元の各箱6枠は保持。近接除去が強かった場合は候補数が増えうる。非有限残差は元の扱いを保持して末尾へ |
| M062 uid・revisionと枝箱を保存 | 候補ID衝突や別座標の検証結果の混同 | E/contracts/candidate_record.py:1; E/contracts/candidate_record.py:83; E/orchestration/assemble_exact_results.py:86 | attempt・backend・seed等の来歴、座標更新でrevision。高精度decimalとorigin boxを保持 | 単純OFF不可: なし。単純OFF不可: 保存再生・検証cacheの同一性が崩れる | 多attempt・救済・離散補完。根拠: candidate_keyで検証とmergeを対応付ける | 発見: SearchBatchResultの全生成元と精密化への境界を追跡。 |

## 代数的前処理・有限列挙

| ID・名前 | 何の困難のためか | 場所 | 既定値・閾値 | スイッチと最小変更案 | 想定する問題種・根拠 | 発見・注意 |
|---|---|---|---|---|---|---|
| M063 有限多項式枝の任意前処理 | 数値探索だけでは小さい吸引域や多根を逃す | E/search/algebraic_branches.py:57; E/search/algebraic_branches.py:654; E/orchestration/run_external_pipeline.py:349 | 1～12変数、論理planなし。内CPU0.5秒/外wall1.5秒。成功でもHP・元条件検証 | 既存: NO_ALGEBRAIC。可（記録上）: primaryの代数prepassを省く既存実験名 | 多項式化できる有限解。根拠: eligibleと全実根の候補生成 | 発見: search_algebraic_branchesから多項式化・消去・根の再検証を追跡。既存記録は入口単位。尺度chartが同じworker関数を呼ぶため、その実装範囲は67ad79a確認が必要 |
| M064 Distance・接条件の多項式化 | 平方根・絶対値のままでは消去できない | E/search/cartesian_polynomials.py:230; E/search/algebraic_branches.py:274 | 零関係の専用式、分母除去、最大3回のradical norm（4回目は変換結果の判定） | 新規: NO_ALGEBRAIC_ZERO_RELATIONS。可（案）: zero_relationの専用変換を省き通常式へ。未対応なら前処理を辞退 | 距離0・接条件。根拠: target==0時の専用変換 | 発見: search_algebraic_branchesから多項式化・消去・根の再検証を追跡。親NO_ALGEBRAICで一括停止可。NO_RESIDUAL_REWRITEでは残す |
| M065 角度の必要多項式条件 | Angleを含む式を代数入口へつなぐ | E/search/angle_equations.py:4; E/search/algebraic_branches.py:275 | 対応する角度式のみ必要条件へ。元の角度条件で後検証 | 新規: NO_ALGEBRAIC_ANGLE_EQUATIONS。可（案）: necessary_angle_equationを恒等写像にし未対応なら辞退 | 角度拘束。根拠: polynomial化前の変換 | 発見: search_algebraic_branchesから多項式化・消去・根の再検証を追跡。必要条件の根がすべて元問題の根とは主張しない |
| M066 平方因子を外した零条件を追加 | 重根構造で消去が難しくなる | E/search/polynomial_zero_consequences.py:26; E/search/algebraic_branches.py:251 | 元行は残す。因数分解を厳密に再構成してからsquarefree行追加 | 新規: NO_SQUAREFREE_CONSEQUENCES。可（案）: augment_zero_rowsのsquarefree追加だけ省く | 二乗された接条件・重根。根拠: 重複因子の指数を検出 | 発見: search_algebraic_branchesから多項式化・消去・根の再検証を追跡。既存NO_ALGEBRAICは全体停止のみ。単独寄与は新規 |
| M067 二次の平方和から一次零条件を追加 | 実数解では0になる項が二次式内に隠れる | E/search/polynomial_zero_consequences.py:57 | 有理・半正定値を厳密消去で証明、追加行合計上限32、元行維持 | 新規: NO_SOS_CONSEQUENCES。可（案）: 平方和からの追加だけ省く | 距離二乗の和=0。根拠: sign×F=sum(d_i L_i²),d_i&gt;0を検証 | 発見: search_algebraic_branchesから多項式化・消去・根の再検証を追跡。 |
| M068 定数行結合から隠れた一次式を抽出 | 距離二乗同士の差にある直線条件を見逃す | E/search/algebraic_branches.py:86 | 2～32行、単項式&lt;=96、有理係数bit&lt;=4096。拡大行列rrefの証拠を保持 | 新規: NO_AFFINE_CONSEQUENCES。可（案）: affine_polynomial_consequencesの追加を省く | 複数円・距離等式。根拠: 非線形単項式係数を相殺 | 発見: search_algebraic_branchesから多項式化・消去・根の再検証を追跡。 |
| M069 厳密一次消去で未知数を減らす | 元の変数数のままGroebnerを計算する費用 | E/search/algebraic_branches.py:515 | linear_eq_to_matrix→rref、残り自由変数へ厳密代入 | 新規: NO_ALGEBRAIC_AFFINE_ELIMINATION。可（案）: 全変数のまま有限成分処理へ。上限超過時は辞退 | 線形拘束の多いCartesian問題。根拠: pivotsを代入してactiveを減らす | 発見: search_algebraic_branchesから多項式化・消去・根の再検証を追跡。 |
| M070 変数・方程式の独立成分に分割 | 無関係な変数をまとめて消去する費用 | E/search/algebraic_branches.py:332; E/search/algebraic_branches.py:547 | 変数出現の連結成分ごとに解き直積。総候補&lt;=16 | 新規: NO_ALGEBRAIC_COMPONENT_SPLIT。可（案）: 1つの成分として有限列挙を試す | 独立な点や小系の組合せ。根拠: support graphを辿る | 発見: search_algebraic_branchesから多項式化・消去・根の再検証を追跡。guardは成分を結ぶ場合があるため、受理は全系で実施 |
| M071 Groebnerと単変数実根分離 | 局所最適化の取りこぼしを避ける | E/search/algebraic_branches.py:361; E/search/algebraic_branches.py:392 | 多変数成分&lt;=7、次数&lt;=4。lex basis、零次元のみ。scalar次数&lt;=16、除数とのgcd=1 | 新規: NO_FINITE_ROOT_ISOLATION。可（案）: 非線形列挙を辞退し通常探索へ。一次消去のみ残せる | 有限多根。根拠: real_rootsと厳密逆代入 | 発見: search_algebraic_branchesから多項式化・消去・根の再検証を追跡。上限は完全性を断念して通常探索へ戻る条件。途中の根だけ返さない |
| M072 分離線形形式を追加して形を変える | 通常の変数順ではshape positionにならない | E/search/algebraic_branches.py:434 | T=sum(k^i x_i)、k=1,2,3。項数&lt;=60、演算数&lt;=250 | 新規: NO_SEPARATING_FORM。可（案）: shape_solutions失敗後のseparating_shapeを省く | 投影で根が重なる系。根拠: 元の複素根集合を保つ持ち上げ | 発見: search_algebraic_branchesから多項式化・消去・根の再検証を追跡。 |
| M073 代数根のguard・平方根符号の厳密枝刈り | 二乗して増えた偽の枝にHP時間を使う | E/search/algebraic_branches.py:315; E/search/algebraic_branches.py:578; E/search/algebraic_sign_ledger.py:16 | 符号条件&lt;=96、厳密にFalseを証明できた根だけ除外、不明は残す | 新規: NO_EXACT_BRANCH_PRUNING。可（案）: 除外判定を省き全候補を元HP条件へ送る | 根号・内外接・厳しいguard。根拠: norm前の非負条件を保存 | 発見: search_algebraic_branchesから多項式化・消去・根の再検証を追跡。最終guard検証は必須。除外を止める比較なら問題の意味を保持 |
| M074 分離した根の箱と出自内受理 | 別枝へ収束した候補で列挙完了と誤認する | E/search/algebraic_branch_boxes.py:6; E/search/algebraic_branch_boxes.py:50; E/orchestration/run_external_pipeline.py:644 | 180桁decimalで相異根を保持、厳密有理箱で元枝に属するか確認 | 単純OFF不可: なし。単純OFF不可: 完了判定の根拠を失う。候補生成だけの比較ならNO_ALGEBRAIC | 近接した代数根。根拠: accepted_within_origin_boxでcoverageを確認 | 発見: search_algebraic_branchesから多項式化・消去・根の再検証を追跡。 |
| M075 整数二乗の差から全候補を列挙 | 整数制約の非滑らか残差を連続探索する | E/search/discrete/square_difference.py:208 | 1変数・整数式2個以上、二乗差が非零整数、絶対値&lt;=10^12、根&lt;=128 | 新規: NO_INTEGER_SQUARE_ENUMERATION。可（案）: scan_integer_square_branchesを省く | 2距離が整数で平方差一定。根拠: 約数の偶奇から整数対を列挙 | 発見: search_algebraic_branchesから多項式化・消去・根の再検証を追跡。これはNO_ALGEBRAICの記録上の範囲と同一とは確認できない。別候補生成入口 |
| M076 二次方程式の桁落ちを避ける根式 | 小さい方の根が差の相殺で消える | E/search/discrete/square_difference.py:139 | 80dpsでq=-(b+sign(b)sqrt(D))/2、根q/a,c/q。floatで潰れる別根は前処理を辞退 | 新規: NO_STABLE_QUADRATIC_ROOTS。可（案）: 通常の±根式へ替える。根数・表現可能性の検査は保持 | b²が4acより大きい系。根拠: 小根の相殺を避ける式 | 発見: search_algebraic_branchesから多項式化・消去・根の再検証を追跡。 |

## 高精度精密化・微分・残差変換

| ID・名前 | 何の困難のためか | 場所 | 既定値・閾値 | スイッチと最小変更案 | 想定する問題種・根拠 | 発見・注意 |
|---|---|---|---|---|---|---|
| M077 代数候補の高精度初期値を保持 | 180桁の種をfloat経由で16桁に落とす | E/refinement/mpmath_refiner.py:1854; E/contracts/candidate_record.py:104 | initial_point_decimalを200dpsで読む。通常候補はfloat境界変換 | 新規: NO_DECIMAL_INITIAL_POINT。可（案）: 初期化でx_floatだけ使う | 代数前処理からの候補。根拠: decimalがある場合の優先分岐 | 発見: MpmathRefinerの全入口・LM・closure・差分を追跡。 |
| M078 高品質候補の直接経路 | 既に小残差の点でLMを繰り返す | E/refinement/mpmath_refiner.py:1611; E/refinement/mpmath_refiner.py:1864 | 残差&lt;=1e-15、120dpsでhard確認。integer/closureを後続実行 | 新規: NO_DIRECT_ACCEPT。可（案）: direct_accept_residual=None | 高精度種・良いfloat解。根拠: direct経路にだけ入口閾値 | 発見: MpmathRefinerの全入口・LM・closure・差分を追跡。直接最終受理ではない。必要なら通常LMへ戻る |
| M079 短いNewtonでwarm start | 良い初期点から減衰LMを長く回す | E/refinement/mpmath_refiner.py:59; E/refinement/mpmath_refiner.py:1981 | 変数&gt;1、行&gt;=変数、hard可行、整数条件なし。120dps、最大12step、元残差1e-80確認 | 新規: NO_WARM_NEWTON。可（案）: LM前のfindroot呼出だけ省く | 正則根付近。根拠: 失敗時は元座標を維持してLMへ | 発見: MpmathRefinerの全入口・LM・closure・差分を追跡。 |
| M080 段階的な桁上げ | 全反復を最初から最高精度で行う費用 | E/refinement/refiner_config.py:9; E/refinement/mpmath_refiner.py:2024 | 50→100→120dps、残差目標1e-20→1e-50→1e-80 | 新規: NO_PRECISION_LADDER。可（案）: schedule_dps=(120,)へ。closureと最終検証は別 | 収束前に多数反復する問題（推測）。根拠: 段階ごとに現在点を引継ぐ | 発見: MpmathRefinerの全入口・LM・closure・差分を追跡。 |
| M081 緩い閾値で次の精度へ昇格 | 丸めで現段階の目標まで下がらない | E/refinement/refiner_config.py:56; E/refinement/mpmath_refiner.py:2040 | promotion=target^0.5 | 新規: NO_RELAXED_PROMOTION。可（案）: stage_promotion_relax_power=1 | 低精度で停滞する問題。根拠: 厳しいtarget未達でも次dpsへ進める | 発見: MpmathRefinerの全入口・LM・closure・差分を追跡。 |
| M082 LMの減衰を適応させる | 特異近傍で大きすぎる更新を抑える | E/refinement/levenberg_marquardt_step.py:23; E/refinement/mpmath_refiner.py:1386 | (JᵀJ+λI)をLU、初期λ1e-6・下限1e-12、成功÷4/失敗×4 | 新規: FIXED_LM_DAMPING。可（案）: λを固定する分岐を追加 | 悪条件・特異近傍。根拠: 成否で減衰を変える | 発見: MpmathRefinerの全入口・LM・closure・差分を追跡。λ=0へ一律変更はLU失敗を増やしNewton法との同等性もない |
| M083 LM反復内のJacobian再利用 | line search失敗後の同一点で差分を再計算する費用 | E/refinement/mpmath_refiner.py:1386 | 現在点が変わった時だけJを再構築 | 新規: NO_LM_JAC_CACHE。可（案）: 毎反復でJを作り直す | 多数のbacktrack失敗（推測）。根拠: jacobian_pointとの同一点比較 | 発見: MpmathRefinerの全入口・LM・closure・差分を追跡。 |
| M084 LMの停止条件 | 改善しない候補に時間を使い続ける | E/refinement/refiner_config.py:22; E/refinement/mpmath_refiner.py:1490 | 1stage80反復、相対改善1e-10、停滞5、line-search失敗12 | 新規: NO_EARLY_STALL_STOP。可（案）: 停滞・連続失敗の打切りだけ省き80反復/締切は保持 | 停滞後に回復する系（推測）。根拠: 改善率と連続回数で終了 | 発見: MpmathRefinerの全入口・LM・closure・差分を追跡。 |
| M085 半分刻みline searchと数学的境界 | LM更新で残差増大・定義域逸脱する | E/refinement/line_search.py:32; E/refinement/mpmath_refiner.py:921 | alphaを半分、最大20試行。残差減少、数学的boundsと必要時hardを確認 | 新規: NO_BACKTRACKING。可（案）: alpha=1の1試行だけにする。判定は維持 | 狭い領域・曲がった零集合。根拠: backtrackingの採否条件 | 発見: MpmathRefinerの全入口・LM・closure・差分を追跡。HPは推定探索箱を境界に使わない。数学的境界は少なくとも530dpsで評価 |
| M086 差分の変数尺度と精度依存幅 | 一律hでは大小の座標で精度が違う | E/refinement/finite_difference_jacobian.py:61 | h=max(1,abs(x))×10^-min(dps//2,30)、中央差分、最大6回半減 | 新規: FIXED_DIFFERENCE_STEP。可（案）: hだけ固定値にする設定を追加 | 大小混在・高精度。根拠: 座標値とdpsで幅を変更 | 発見: MpmathRefinerの全入口・LM・closure・差分を追跡。 |
| M087 疎なJacobianの列まとめ差分 | 各変数で残差を2回ずつ評価する費用 | E/refinement/finite_difference_jacobian.py:15; E/problem/analysis_plan.py:66 | 影響する残差行が重ならない列を同時摂動。cusp時等は個別へ | 新規: NO_GROUPED_DIFFERENCE。可（案）: 列groupをすべて単列にする | 疎な大きい系。根拠: transitive residual dependenciesを使用 | 発見: MpmathRefinerの全入口・LM・closure・差分を追跡。 |
| M088 定義域端の二次片側差分 | 中央差分の片側が評価不能 | E/refinement/finite_difference_jacobian.py:102 | (-3f+4f(h)-f(2h))/(2h)型、左右を選択 | 新規: NO_ONE_SIDED_DOMAIN_DIFFERENCE。可（案）: 中央差分で失敗ならその差分を失敗とする | sqrt境界・構成の限界。根拠: 片側のみ評価可の場合 | 発見: MpmathRefinerの全入口・LM・closure・差分を追跡。 |
| M089 Angleの折れ目で片側勾配を選ぶ | 絶対値状の底で中央差分が0になる | E/refinement/finite_difference_jacobian.py:123; E/refinement/mpmath_refiner.py:1454 | 左右の傾きが反対符号、中央&lt;=100eps×尺度なら強い片側。Angleを含む場合 | 新規: NO_CUSP_ONE_SIDED_DIFFERENCE。可（案）: one_sided_at_cusp=False | 角度0等。根拠: _problem_contains_call(Angle) | 発見: MpmathRefinerの全入口・LM・closure・差分を追跡。最適化用の下降方向の工夫で、通常の微分が存在するとの主張ではない |
| M090 closure用の解析Jacobian | 高精度差分の評価回数と丸め | E/refinement/analytic_jacobian.py:19; E/refinement/analytic_jacobian.py:161; E/refinement/mpmath_refiner.py:1026 | 2～12変数、論理式なし。行演算&lt;=300、微分全体&lt;=1500、CSE。計画1.5秒/cache128 | 既存: NO_ANALYTIC_JAC。可（記録上）: 解析計画を使わず差分へ | 対応Cartesian式のclosure。根拠: findrootにだけ解析Jを渡す | 発見: MpmathRefinerの全入口・LM・closure・差分を追跡。ablation34記録。通常LMのJが解析化されるわけではない。requires_smoothingの連動必須 |
| M091 距離0を座標差へ分解 | 非負の距離は零点で折れる | E/refinement/mpmath_refiner.py:529; E/refinement/mpmath_refiner.py:618 | Distance(点,点)=0をdx,dyの2行へ | 既存: NO_SIGNED_TANGENCY。可（記録上）: _smooth_zero_constraint_residualsを止め元の距離1行へ | 点一致。根拠: 点の型とzero targetを検出 | 発見: MpmathRefinerの全入口・LM・closure・差分を追跡。既存名の範囲は関数全体。今回のNO_RESIDUAL_REWRITEにも含む |
| M092 証明できる接点の一次零条件 | 一般接条件は接点で平らになる | E/refinement/mpmath_refiner.py:628; E/problem/tangency_contacts.py:125 | 直線円は半径と方向の内積、円円は半径の外積÷半径。構成・所属証拠がある時だけ | 既存: NO_SIGNED_TANGENCY。可（記録上）: 同関数を止め元IsTangentへ | 接点が構成から分かる問題。根拠: contactを構造的に証明 | 発見: MpmathRefinerの全入口・LM・closure・差分を追跡。個別寄与には新規NO_CONTACT_REWRITEが必要。既存は群単位 |
| M093 一般の円円接条件を符号付き差へ | 非負述語の重根・折れ目 | E/refinement/mpmath_refiner.py:647; G/geometry/mp/signed_tangency.py:29 | 内接/外接の近い方の距離差。無効半径・同中心では元式へ | 既存: NO_SIGNED_TANGENCY。可（記録上）: 同関数を止め元IsTangentへ | 円円・支持円を使う弧。根拠: Circleへの変換と符号付き枝選択 | 発見: MpmathRefinerの全入口・LM・closure・差分を追跡。最終検証にも別実装がある |
| M094 直線円接条件の符号付き二乗差 | 接条件の非滑らかな絶対値 | E/refinement/mpmath_refiner.py:654 | 正規化直線の符号付き距離²−半径² | 既存: NO_SIGNED_TANGENCY。可（記録上）: 同関数を止め元IsTangentへ | 直線と円の接触。根拠: MPLine/MPCircleの組を判定 | 発見: MpmathRefinerの全入口・LM・closure・差分を追跡。最終検証は同じ二乗式ではなくSignedTangencyを使う |
| M095 距離=半径の接点書き換え | IsTangentで書かれていない接条件 | E/refinement/mpmath_refiner.py:572; E/problem/tangency_contacts.py:217 | Distance(中心,直線)=半径でもcontact証明時は内積行 | 既存: NO_SIGNED_TANGENCY。可（記録上）: 同関数を止め距離−targetへ | 半径との距離等式。根拠: 非零targetも走査 | 発見: MpmathRefinerの全入口・LM・closure・差分を追跡。zero constraintsという関数名だけではこの分岐を見落とす |
| M096 正の半径で割った補助行 | 半径が小さいと元条件が高い重複度になる | E/refinement/mpmath_refiner.py:580; E/refinement/mpmath_refiner.py:683; E/problem/positive_radius_contacts.py:150 | 中心が半径にアフィン、基点が外接円上、内接距離一致など証明時だけ追加。元行維持 | 既存: NO_SIGNED_TANGENCY。可（記録上）: 補助行を省く。群全体OFFは同関数で可 | 微小正半径の接触。根拠: Circleの正半径を使う代数的補助 | 発見: MpmathRefinerの全入口・LM・closure・差分を追跡。個別なら新規NO_RADIUS_AUX_ROWS。零半径を許す変更ではない |
| M097 rankに応じたNewton座標chart | 冗長行・自由度で通常Newtonが特異になる | E/refinement/mpmath_refiner.py:711; E/refinement/mpmath_refiner.py:816 | 行列を行・列で均衡化、完全pivot、rank閾値10^-min(25,max(12,dps//3))。補助反復最大64 | 新規: NO_RANK_NEWTON。可（案）: 通常findroot失敗後のrank-aware fallbackを省く | 冗長拘束・相似自由度。根拠: 独立行列部分を選ぶ | 発見: MpmathRefinerの全入口・LM・closure・差分を追跡。固定した残り座標は計算chartであり追加の数学条件ではない |
| M098 LM後の高精度closure | LMの減衰・停滞で精度が伸びない | E/refinement/mpmath_refiner.py:1674; E/refinement/refiner_config.py:9 | hard可行かつ滑らかな残差&lt;=max(1e-10,promotion)。120/250/350/500dps、各max(80,2dps)step | 新規: NO_POST_LM_CLOSURE。可（案）: _apply_post_lm_closure_polishを省く | 重根・高桁答。根拠: 追加findrootと元残差の確認 | 発見: MpmathRefinerの全入口・LM・closure・差分を追跡。目標1e-80/1e-150/1e-220/1e-320。完了した最後の点を保持 |
| M099 整数・素数条件の局所closure | 整数判定の非負残差は微分しにくい | E/refinement/mpmath_refiner.py:225; E/refinement/mpmath_refiner.py:1353; E/refinement/mpmath_refiner.py:2075 | 近傍整数を固定しinner−integerに替える。整数/素数を再検査、派生候補を保持 | 新規: NO_INTEGER_CLOSURE。可（案）: 局所整数closureを省く。元述語と最終検証は維持 | IsInteger/IsPrime。根拠: top-level述語を抽出して整数目標化 | 発見: MpmathRefinerの全入口・LM・closure・差分を追跡。NO_RESIDUAL_REWRITEの対象外。整数closure経路ではsmooth群を通らない |
| M100 整数closureのhard制限なし再試行 | 制約面に近づく途中でhardを一時的に外れる | E/refinement/mpmath_refiner.py:1477 | hard保全line searchが失敗した整数closureだけ再試行 | 新規: NO_INTEGER_HARD_RETRY。可（案）: 制限なし再試行を省く | 整数条件と狭いguard。根拠: integer_closures条件付き分岐 | 発見: MpmathRefinerの全入口・LM・closure・差分を追跡。受理前のhard検査は省かれない |
| M101 整数代入後の答を有理数で再評価 | 浮動演算で得た整数・有理数の桁を失う | E/refinement/mpmath_refiner.py:407 | 対応する算術式をFractionで評価 | 新規: NO_RATIONAL_ANSWER_CLOSURE。可（案）: 整数代入後も通常HP答だけ使う | 整数制約から有理数の答。根拠: 限定ASTのFraction計算 | 発見: MpmathRefinerの全入口・LM・closure・差分を追跡。後段PSLQ・厳密定数入口が代わる可能性 |

## 最終検証と答の誤差見積り

| ID・名前 | 何の困難のためか | 場所 | 既定値・閾値 | スイッチと最小変更案 | 想定する問題種・根拠 | 発見・注意 |
|---|---|---|---|---|---|---|
| M102 元条件で受理を判定する | 最適化の成功statusは解の正しさを保証しない | E/orchestration/assemble_exact_results.py:25; E/orchestration/assemble_exact_results.py:159; E/evaluation/final_verifier.py:205 | stalled/max_iters/deadline等も再検証対象。domain/hard/正規化残差/有限answerを独立判定 | 単純OFF不可: なし。単純OFF不可: 偽陽性を受理する別仕様になる | 全問題。根拠: refinement_statusに依らずverify_revisionを呼ぶ | 発見: assemble_exact_results→final_verifier→verification_*を追跡。最終数値検証は一般の区間存在証明ではない |
| M103 最終検証での接条件・距離0の平滑化 | 非負述語の差分が零点で不安定 | E/evaluation/verification_numerics.py:199; E/evaluation/verification_numerics.py:207 | IsTangent→SignedTangency、Distance(P,Line(A,B))→符号付き外積/辺長 | 新規: NO_RESIDUAL_REWRITE。可（案）: この2分岐だけOFF、通常式へ。各腕でevaluatorを新規作成 | 接条件・点の直線上条件。根拠: 精密化とは別の共通零式変換 | 発見: assemble_exact_results→final_verifier→verification_*を追跡。既存NO_SIGNED_TANGENCYの記録では覆わない。論理葉にも適用される |
| M104 abs・面積・minの零集合を保つ変換 | 絶対値や最小値の折れ目が検証を難しくする | E/evaluation/verification_numerics.py:168 | 外側のabsを除く、三角形Areaを符号付き面積へ、minは元の比較で選ぶ枝を滑らかにする | 新規: NO_FINAL_OTHER_ZERO_REWRITE。可（案）: 該当分岐だけ元式を返す | 面積0・最小距離0・論理等式。根拠: 任意部分式でなく零条件の外側だけ変換 | 発見: assemble_exact_results→final_verifier→verification_*を追跡。NO_RESIDUAL_REWRITEには含めない。分母の意味は維持 |
| M105 式の共通項を消してから残差尺度を測る | 巨大な共通定数が小さな矛盾を覆い隠す | E/evaluation/verification_numerics.py:246; E/evaluation/verification_numerics.py:293 | symbolic正規化、定数式を厳密判定、加算項の大きさを評価 | 新規: NO_VERIFIER_EQUATION_NORMALIZATION。可（案）: 元のlhs−targetで評価する比較入口を追加 | 大定数の差・恒等式。根拠: normalized_equationsとterm scales | 発見: assemble_exact_results→final_verifier→verification_*を追跡。判定結果も変わりうるため誤差基準を同時に記録 |
| M106 検証時の変数・行・残差の正規化 | 同じ問題の座標単位や式の倍率で判定が変わる | E/evaluation/final_verifier.py:42; E/evaluation/verification_numerics.py:365; E/evaluation/verification_numerics.py:442 | 変数max(箱幅,abs(x),1)、行max(abs(r),abs(J_i)×scale)。残差/最大(項尺度,感度,abs(r))&lt;=1e-30 | 新規: NO_VERIFIER_SCALING。可（案）: 単位scale・未正規化残差で判定する比較分岐を追加 | 単位・倍率の違う系。根拠: 行列補正と受理ノルムの両方に尺度が入る | 発見: assemble_exact_results→final_verifier→verification_*を追跡。閾値を同じ数値にしても同じ厳しさではない。性能と判定変化を分ける |
| M107 同じ座標をpとp+30桁で再評価 | 残差だけでは内部の桁落ちを見積もれない | E/evaluation/verification_sampling.py:8 | error=4abs(high−low)+32eps_p abs(high)、枝が違えばinf | 新規: NO_DUAL_PRECISION_SAMPLE。可（案）: 単一精度の丸め項だけに替える診断用分岐 | 内部相殺・近接枝。根拠: 同一点を2精度で評価 | 発見: assemble_exact_results→final_verifier→verification_*を追跡。受理の信頼性が弱まる比較。正しさ確認用の主構成にはしない |
| M108 検証差分の縮小・h/2比較 | 非滑らかな式の見かけの勾配を採る | E/evaluation/verification_numerics.py:25 | h=変数尺度×10^-max(20,p//3)、最大8回×1/100、hとh/2比較、同じ枝を要求 | 新規: NO_ADAPTIVE_VERIFIER_DIFFERENCE。可（案）: 最初のhでの差分だけにし不確かさを残す | 折れ目・定義域境界。根拠: 縮小し収束性を比較 | 発見: assemble_exact_results→final_verifier→verification_*を追跡。片側可。最適化の強い片側勾配選択とは用途・条件が違う |
| M109 幾何的に同じ枝か照合 | 交点配列の番号だけでは同じ枝といえない | E/evaluation/verification_numerics.py:40 | 候補点の相互最近傍、選択点の移動&lt;枝間隔/4 | 単純OFF不可: なし。単純OFF不可: 別枝の数値を同一関数の差分・誤差として使ってしまう | 近接交点・枝の順序入替。根拠: selected indexだけでなく座標対応を照合 | 発見: assemble_exact_results→final_verifier→verification_*を追跡。 |
| M110 検証Jacobianの依存行だけ評価 | 最終検証の高精度差分が重い | E/evaluation/verification_numerics.py:313 | 同じ変数に依存する行をまとめ、依存0の列は評価省略 | 新規: NO_VERIFIER_DEPENDENCY_PRUNING。可（案）: 全行・全列を評価して同じ差分を組む | 大きな疎系。根拠: active_columnsとequation dependencies | 発見: assemble_exact_results→final_verifier→verification_*を追跡。 |
| M111 検証中の座標補正 | 精密化の残り誤差で本来の根を棄却する | E/evaluation/final_verifier.py:122; E/evaluation/verification_numerics.py:365 | 各精度で最大8補正、全元残差の正規化値が改善し同じ枝なら採用 | 新規: NO_FINAL_CORRECTION。可（案）: 検証補正ループを0回、同じ検査のみ実施 | 停滞した精密化・悪条件。根拠: verified resultに修正valuesを返す | 発見: assemble_exact_results→final_verifier→verification_*を追跡。NO_RESIDUAL_REWRITE後もこの一般補正は残る |
| M112 rankと誤差から座標不確かさを伝播 | 特異自由度を誤差0として扱う | E/evaluation/verification_numerics.py:365; E/evaluation/verification_domains.py:189 | 勾配signal&gt;100noise、ranktol=100×error_bound、未解決軸にも差分幅由来の正のfloor | 新規: NO_UNCERTAINTY_PROPAGATION。可（案）: 診断用に座標誤差を無視する分岐。正式受理の代替にはしない | 自由度・悪条件の答。根拠: inverseと未選択列から誤差を伝播 | 発見: assemble_exact_results→final_verifier→verification_*を追跡。最終答の感度にも伝播。一般的な存在証明ではない |
| M113 guardを誤差込みの三値で判定 | 丸めの0だけで開閉境界を誤認する | E/evaluation/verification_domains.py:218; E/evaluation/verification_domains.py:246 | margin&gt;100errorで確定、境界は構造的zero証拠、それ以外はTrue/False/None | 単純OFF不可: なし。単純OFF不可: 未確定を真にすると受理仕様が変わる。閾値調整なら診断用設定を別途設計 | 極小余裕・直角・閉境界。根拠: compareのNoneとzero_certificate | 発見: assemble_exact_results→final_verifier→verification_*を追跡。 |
| M114 構造的な零条件の証明を再利用 | 正しい閉境界を誤差のため未確定にする | E/evaluation/verification_identities.py:15; E/evaluation/verification_identities.py:44; E/evaluation/final_verifier.py:67 | activeな論理/min枝、symbolic zero signature cache4096。別途有理アフィン点の厳密一致 | 新規: NO_ZERO_CERTIFICATES。可（案）: 証明経路だけ使わず通常の誤差判定へ | 厳密な直角・端点・恒等式。根拠: 構造と有理座標を使った零判定 | 発見: assemble_exact_results→final_verifier→verification_*を追跡。OFFは厳しくなる方向だが未確定増加は実験で確認が必要 |
| M115 連続する2精度での最終確認 | 1精度だけの偶然の小残差を採る | E/evaluation/final_verifier.py:20; E/evaluation/final_verifier.py:229 | 80/120/180/250/350/500dps、2回連続validかつ現在&gt;=180 | 新規: NO_FINAL_PRECISION_CONFIRMATION。可（案）: 最初のvalidを採る診断用分岐 | 丸めに敏感な系。根拠: previous_validを要件にする | 発見: assemble_exact_results→final_verifier→verification_*を追跡。独立した正しさ基準を弱める。主5構成には含めない |
| M116 非定数の答をさらに高精度で確認 | 座標が通っても答の桁が不十分 | E/orchestration/assemble_exact_results.py:232 | 非closed答: p超の250/350/500。1段しか残らなければpを前置。500到達時は追加呼出なし | 新規: NO_ANSWER_CONFIRMATION。可（案）: 追加_verify_revisionだけ省き最初の最終検証を保持 | 座標依存の敏感な答。根拠: answer_closedによる分岐 | 発見: assemble_exact_results→final_verifier→verification_*を追跡。「常に最終検証を2回呼ぶ」ではない。内部の2精度確認とも別 |
| M117 候補検証・座標検証のcache | 整数補完やmerge後に同じ点を再検証する費用 | E/orchestration/assemble_exact_results.py:106; E/evaluation/ir_evaluator.py:59 | 最大256、正確座標・revision・精度schedule等で鍵を分ける | 新規: NO_FINAL_VERIFICATION_CACHE。可（案）: _verify_revisionでcacheを迂回 | 再精密化・複数来歴の同一点。根拠: exact binary座標で再利用 | 発見: assemble_exact_results→final_verifier→verification_*を追跡。スイッチを変えて同じevaluatorを再利用しない |

## 厳密値復元・PSLQ

| ID・名前 | 何の困難のためか | 場所 | 既定値・閾値 | スイッチと最小変更案 | 想定する問題種・根拠 | 発見・注意 |
|---|---|---|---|---|---|---|
| M118 残差tierで次数・係数・反復予算を分ける | 低品質の値に巨大な関係探索を使う | E/exact_assembly/classify_exact_requirement.py:1; E/exact_assembly/identify_answer.py:31 | strict&lt;=1e-70:度8/係数1e8/20000step、standard&lt;=1e-55:6/1e7/15000、他4/1e6/10000 | 新規: FIXED_EXACT_TIER。可（案）: 全候補に同じtierを指定、各軸を独立設定化 | 高次数・大係数の答。根拠: TIER_CONFIGS | 発見: identify_answer→symbolic_operations→exactの下位関数を追跡。下位find_minimal_polynomial単独既定は度8/係数1e15/10000、上位既定と異なる |
| M119 推定誤差からPSLQへ渡す有効桁を制限 | 作業桁と正しい桁数を取り違える | G/runtime/symbolic_operations.py:144 | p=min(入力p,floor(-log10(error/max(1,abs(value))))+10)、p&lt;30・不正誤差は復元しない | 新規: NO_DISCOVERY_PRECISION_CAP。可（案）: 入力pをそのまま渡す診断分岐。最終距離判定は保持 | 悪条件で答の有効桁が少ない系。根拠: answer_uncertaintyを使用 | 発見: identify_answer→symbolic_operations→exactの下位関数を追跡。 |
| M120 PSLQ精度と係数上限を独立指定 | 大係数の関係と誤った近似関係を区別する | G/exact/polynomial_search.py:246; G/exact/polynomial_search.py:316 | precision/max_degree/max_coeff/max_stepsが独立引数。作業桁max(ambient,p+40,80)、下位max(ambient,p+30,60) | 新規: PSLQ_PARAMETERS。可（案）: 下位関数の引数を比較用設定へ公開。新実装不要の関数単体実験可 | 高次数・大係数。根拠: 関数signature | 発見: identify_answer→symbolic_operations→exactの下位関数を追跡。新規は環境スイッチのみ。入力値をfloat化しない。段階別入口は優先資料 |
| M121 PSLQのprecision依存許容差 | 丸めに近い整数関係を過剰探索する | G/exact/polynomial_search.py:282 | p&gt;100:10^(-(p//2))、他10^(-((3p)//10)) | 新規: FIXED_PSLQ_TOLERANCE。可（案）: tolを独立引数へ切出す | 不足精度・近似関係。根拠: precisionでtolを切替 | 発見: identify_answer→symbolic_operations→exactの下位関数を追跡。precision変更は作業桁だけの実験ではない |
| M122 答の10進尺度を変えて整数関係を探す | 極大・極小値の冪で係数尺度が偏る | G/exact/polynomial_search_helpers.py:16; G/exact/polynomial_search.py:169 | 桁kの10^k,10^(k-1),10^(k+1),1を試し、係数を有理数で元へ戻す | 新規: NO_PSLQ_SCALING。可（案）: scale=1だけ試す | 極端な大きさの代数値。根拠: power-of-ten候補と係数の逆変換 | 発見: identify_answer→symbolic_operations→exactの下位関数を追跡。max_coeffは変換後関係の上限で元の最終係数上限とは限らない |
| M123 低次数から探索・原始化・因数の選択 | 高次数の冗長な関係や別根を返す | G/exact/polynomial_search.py:169; G/exact/polynomial_search.py:51; G/exact/polynomial_search.py:124 | 次数昇順、係数gcd/符号正規化、squarefree因子、近い根が一意な因子を選ぶ | 新規: NO_PSLQ_DEGREE_LADDER。可（案）: 最大次数だけ探索する比較分岐。関係検証と因子処理は保持 | 低次数だが上限は大きい答。根拠: degree loop | 発見: identify_answer→symbolic_operations→exactの下位関数を追跡。因子・根同定の削除は誤同定を招くためこのスイッチに含めない |
| M124 多項式関係と根の距離を再確認 | 小さい多項式値だけで誤った根を採る | G/exact/polynomial_search_helpers.py:68; E/exact_assembly/verify_identified_answer.py:41; G/runtime/symbolic_operations.py:277 | helper残差tol:高pは10^(-0.6p)、他10^(-0.4p)。上位は根の距離&lt;=uncertainty+root_error | 単純OFF不可: なし。単純OFF不可: 復元の受理根拠を失う | 重根・近い代数根。根拠: 最終値との差を再評価 | 発見: identify_answer→symbolic_operations→exactの下位関数を追跡。verify_identified_answer単体の実装は多項式残差が有限かとroot距離を検査し、残差&lt;=tolは条件にない。docstringだけで判断しない |
| M125 πを含む関係の別探索 | 純代数PSLQではπ係数の答を表せない | G/exact/affine_pi_search.py:115; G/exact/affine_pi_search.py:299; E/exact_assembly/identify_answer.py:31 | まず(value,π,1)の有理係数関係、次に混合冪。総次数上限4/3/1、tol10^(-(p-20)) | 新規: NO_AFFINE_PI。可（案）: affine-pi探索を省く | 角度・円周等の答。根拠: 代数係数×π+代数定数の記述 | 発見: identify_answer→symbolic_operations→exactの下位関数を追跡。 |
| M126 答のπ・Angle依存による探索順 | π型の答に純代数探索時間を使う | E/problem/analysis_plan.py:55; G/runtime/symbolic_operations.py:246 | 依存先にπ/Angleなら安いrational_only π探索を先行 | 新規: NO_PI_PRIORITY。可（案）: 先行prefixだけ省き通常の後段π探索は残す | 角度の答。根拠: constructionの依存を遡る | 発見: identify_answer→symbolic_operations→exactの下位関数を追跡。πを含む入力でも答で相殺しうるため種類の断定には使わない |
| M127 PSLQ等が未同定ならnsimplifyを試す | 整数関係探索が失敗した値から単純式を拾う | E/exact_assembly/identify_answer.py:116; E/exact_assembly/identify_answer.py:312 | 係数未発見かつπ型未同定時。分母&gt;1e6かつ素因数が2,5のみの単純十進有理化は拒否、誤差tol=10^-max(p-20,1) | 新規: NO_NSIMPLIFY_FALLBACK。可（案）: _sympy_fallback呼出を省く | 単純式だがPSLQで未同定の答（推測）。根拠: 復元末尾の別入口 | 発見: identify_answer→symbolic_operations→exactの下位関数を追跡。提案値はさらにworkerの確認uncertaintyとの距離検査とdescriptor生成を通る |
| M128 閉じた定数式・固定幾何からの候補 | 数値から既知の厳密式を再発見する費用 | G/runtime/symbolic_operations.py:110; E/exact_assembly/constant_geometry.py:31 | closed scalarは厳密評価。変数なし幾何hintはCPU0.25秒/ops200/外1.5秒、値一致を再確認 | 新規: NO_EXACT_EXPRESSION_SHORTCUT。可（案）: closed/hintを渡さず同じHP値から復元 | 定数答・定数幾何。根拠: closed_source/geometry_hint | 発見: identify_answer→symbolic_operations→exactの下位関数を追跡。表現不可な厳密式は現行では未同定。単純数値化で別の値に置換しない |
| M129 確認誤差内の0を特別扱い | 相殺の小残差を極小非零の答と誤認する | G/runtime/symbolic_operations.py:166; E/exact_assembly/identify_answer.py:259 | abs(value)&lt;=確認uncertaintyなら0候補。通常PSLQ側は非零値からの0根を拒否 | 新規: NO_ZERO_WITHIN_ERROR。可（案）: workerの0特例だけ省く | 厳密に0となる答。根拠: 相対有効桁が意味を持たない領域 | 発見: identify_answer→symbolic_operations→exactの下位関数を追跡。これは誤差推定に基づく方針で、記号的に0を証明した意味ではない |
| M130 既知の厳密答を候補ごとに再検証して再利用 | 同じ答を持つ配置ごとにPSLQを繰り返す | G/runtime/symbolic_operations.py:184; E/orchestration/assemble_exact_results.py:261 | 同tierのdescriptor、現在精度で距離確認、一意一致かつ有効桁が足りる時 | 新規: NO_EXACT_VALUE_REUSE。可（案）: reusable_resultsを空にする | 複数配置で同じ答。根拠: registryを使い値を再確認 | 発見: identify_answer→symbolic_operations→exactの下位関数を追跡。座標の最終検証は各候補で別途行う |
| M131 厳密根descriptorと答の重複除去 | decimalが同じでも異なる実根を混同する | G/exact/descriptors.py:45; G/exact/descriptors.py:64; G/runtime/worker.py:108 | 原始整数多項式、実根番号、有理分離区間eps1e-60。canonical_keyで重複除去 | 単純OFF不可: なし。単純OFF不可: decimal近接で代用すると答の意味が変わる | 近接根・同一答の別配置。根拠: 根区間の厳密一意対応を要求 | 発見: identify_answer→symbolic_operations→exactの下位関数を追跡。 |

## 時間配分・追加探索・seed・実行資源

| ID・名前 | 何の困難のためか | 場所 | 既定値・閾値 | スイッチと最小変更案 | 想定する問題種・根拠 | 発見・注意 |
|---|---|---|---|---|---|---|
| M132 探索に残り時間の一部を配分 | 探索で使い切りHP計算ができない | E/orchestration/run_external_pipeline.py:332; E/orchestration/run_external_pipeline.py:379 | 探索に残り時間の55%。standalone標準全体30秒、公開API既定180秒は別 | 新規: SEARCH_TIME_FRACTION。可（案）: 55%を設定化し同じ総締切で比較 | 探索と精密化の負担が偏る系（推測）。根拠: max_time_secを残時間から計算 | 発見: production config→ordered attempts→worker/runtimeを追跡。 |
| M133 最終検証・厳密復元用の時間を残す | 精密化で時間を使い切り答を保存できない | E/contracts/external_pipeline_config.py:66; E/contracts/runtime_budget.py:39; G/runtime/worker.py:79 | refinement締切は最終締切−min(残時間20%,30秒)。workerは保存用2秒を別途差引く | 新規: NO_FINALIZATION_RESERVE。可（案）: refinement_deadlineを全締切へ。保存2秒は独立に保持 | 精密化が重い系。根拠: 予約分は未使用なら後段が使える | 発見: production config→ordered attempts→worker/runtimeを追跡。configの割合に0を直接渡すとvalidationエラー。締切分岐で切替 |
| M134 失敗時の第2attempt | 最初のbackend・seedでは解が得られない | E/orchestration/run_external_pipeline.py:730; E/contracts/baseline_search_policy.py:51 | 通常primary受理なし又は有限枝coverage未完、残時間&gt;0。fallback hybrid・seed5個 | 既存: NO_SECOND_ATTEMPT。可（記録上）: ordered_attemptsをprimaryだけにする既存比較 | primary失敗・未完列挙。根拠: numeric_primary_has_answersとincomplete判定 | 発見: production config→ordered attempts→worker/runtimeを追跡。救済とは別。同seedを含むs..s+4。任意prepassが答を出しても通常primary失敗なら昇格しうる |
| M135 不完全な代数列挙の通常探索での補完 | 任意前処理の一部成功で通常探索を省く | E/orchestration/run_external_pipeline.py:526; E/orchestration/run_external_pipeline.py:644 | 未検証の起源枝があれば同じprimary設定でallow_algebraic=False、検証済み結果はunion | 新規: NO_ALGEBRAIC_NUMERIC_COMPLETION。可（案）: 補完探索を省く実験分岐。coverage未完の表示は保持 | HPで一部枝が未確定。根拠: candidate出自の集合包含で確認 | 発見: production config→ordered attempts→worker/runtimeを追跡。第2attemptとは別の通常primary補完。NO_SECOND_ATTEMPTだけでは消えない可能性を範囲確認 |
| M136 hybrid内のNOMAD→SciPy補助2回 | 異なる探索法やseedで谷を取り直す | E/orchestration/run_search.py:155; E/orchestration/run_search.py:360 | NOMAD後、残時間の半分で同seed+NOMAD良点、残りでseed+seed数。完全同点start除去 | 新規: NO_HYBRID_SUPPLEMENT。可（案）: 補助SciPy2passを省く | 異なる吸引域（推測）。根拠: seedとstart集合を替えた2回 | 発見: production config→ordered attempts→worker/runtimeを追跡。第2attempt全体を止める既存スイッチより細かい。offsetは10000でなくseed数 |
| M137 未完精密化の救済探索 | 少数候補の精密化だけでは目標へ到達しない | E/search/completion/rescue.py:21; E/orchestration/run_external_pipeline.py:444; E/orchestration/run_rescue_search.py:47 | 受理なし又は受理候補すべてtarget_reached以外、残時間&gt;=8秒。MADS最大6箱×80BB | 既存: NO_RESCUE。可（記録上）: run_rescue_search呼出を省く既存比較 | 停滞・不十分な候補。根拠: exact_assembly_needs_completion | 発見: production config→ordered attempts→worker/runtimeを追跡。各箱上位6、最大36候補が幾何除去前。第2attemptの起動とは別 |
| M138 救済箱の分散配置と適応半径 | 同じ谷だけを再探索する | E/search/select_rescue_boxes.py:72; E/contracts/external_pipeline_config.py:35 | 台帳から最遠点最大6、近傍距離×0.5、箱幅比0.02～0.35にclip | 新規: NO_RESCUE_BOX_DIVERSITY。可（案）: score順中心と固定半径を使う | 複数の可行域（推測）。根拠: 候補間隔に応じた局所箱 | 発見: production config→ordered attempts→worker/runtimeを追跡。NO_DIVERSE_SELECTIONはこの箱配置を残す。単独比較なら中心順位と半径を別設定に分けられる |
| M139 整数目標の観測区間を全組探索 | 近い整数へ丸めるだけでは別整数解を逃す | E/search/discrete/integer_targets.py:140; E/search/discrete/integer_targets.py:430 | 受理なし・残時間あり。観測minのfloor～maxのceil、組合せ&lt;=256で全組、最近い観測点からclosure | 新規: NO_DISCRETE_TARGET_COMPLETION。可（案）: run_discrete_target_completionを省く | 整数・素数条件。根拠: 観測値の区間直積を明示列挙 | 発見: production config→ordered attempts→worker/runtimeを追跡。範囲は観測由来で、全整数解の数学的な網羅保証ではない |
| M140 境界点を非整数制約面へ射影して整数範囲を広げる | 観測された整数範囲だけでは狭すぎる | E/search/discrete/integer_targets.py:238; E/search/discrete/integer_targets.py:318 | 中央+隅、最大min(tuple_cap,1+2^min(n,4))点。区間を広げ、256組を超えない時採用 | 新規: NO_INTEGER_RANGE_PROJECTION。可（案）: _augment_integer_target_observationsを省く | 非整数等式面に沿う整数条件。根拠: project_point_to_noninteger_constraint_manifold | 発見: production config→ordered attempts→worker/runtimeを追跡。 |
| M141 乱数を外部seedから決定的に派生 | 実行ごとに候補の違いが混ざる | E/search/nomad_config.py:27; E/search/scipy_multistart_backend.py:184; E/contracts/baseline_search_policy.py:51 | primary=s、fallback=s..s+4、SciPy familyはs×1009+文字列の重み和。Python hashは不使用 | 新規: FIXED_INTERNAL_SEED。可（案）: 全内部seedを0へ固定する診断設定 | 再現性・複数seed効果。根拠: derive_seed_valuesとfamily seed | 発見: production config→ordered attempts→worker/runtimeを追跡。独立性を保証する設計ではない。実験は外部seedを揃える |
| M142 backendごとの時間配分と逐次seed | 早いseedやfamilyが総予算を独占する | E/search/nomad_backend.py:94; E/search/scipy_multistart_backend.py:160; E/orchestration/run_rescue_search.py:94 | NOMADは残時間/残seed。SciPy local:TRF=45:45（param系60:45）、救済は残時間/残箱 | 新規: FIXED_SUBSEARCH_BUDGETS。可（案）: 均等な固定割当へ替え、総締切は保持 | 難しいseed・候補が偏る場合（推測）。根拠: remainingを再計算 | 発見: production config→ordered attempts→worker/runtimeを追跡。MAX_TIMEはNOMAD渡し時ceilかつ最低1秒。全体締切は別にある |
| M143 コア数・BLAS thread・逐次実行 | 過剰なスレッド競合で時間の比較が崩れる | G/engine/runner.py:115; G/engine/runner.py:146; G/problem/models.py:57; G/runtime/symbolic.py:40 | 公開既定cores=1、OMP/OpenBLAS/MKL/NumExpr各1、CPU affinityを設定。seedは逐次 | 単純OFF不可: なし。単純OFF不可: cores設定は既存。探索を真に並列化するのは小スイッチではない。thread制限を変える比較は別の資源実験 | 重い線形代数・記号計算。根拠: runnerの環境設定とbackendのfor loop | 発見: production config→ordered attempts→worker/runtimeを追跡。coresを増やすだけで候補が並列処理されるとは読めない。symbolic子1個は別process |
| M144 再利用する記号計算workerと任意処理の短い締切 | SymPy起動費用・長い任意前処理で全体が止まる | G/runtime/symbolic.py:24; G/runtime/symbolic.py:69 | solveごと遅延起動1子、同期request。optional timeoutは子を閉じ再起動可能、親締切より延長しない | 新規: NO_SYMBOLIC_WORKER_REUSE。可（案）: requestごとworkerを作り直す比較。全体/任意締切と終了処理を維持 | 代数・解析微分・PSLQ併用。根拠: clientの再利用とreset | 発見: production config→ordered attempts→worker/runtimeを追跡。プロセス寿命の変更は小変更でも検証が必要。今回プロセス操作はしない |
| M145 共通締切と完了済み記録の保全 | 時間切れで既に得た正しい答まで消える | G/runtime/deadline.py:25; G/runtime/deadline.py:55; G/runtime/worker.py:210; G/engine/runner.py:157 | 単調時計、内側締切はmin。候補revisionと検証済みexact記録を保持、保存receiptを照合 | 単純OFF不可: なし。単純OFF不可: 総予算と結果の完全性の契約。予算値を変える比較は可 | 時間制限に達する問題。根拠: TimeoutErrorで完了記録を回収 | 発見: production config→ordered attempts→worker/runtimeを追跡。他タスクのprocessを操作する機構ではない。今回はコード読解のみ |
| M146 不要なSciPyの起動を遅らせる | NOMADのみの問題でもSciPy import費用がかかる | E/search/scipy_lazy.py:1 | brentq/least_squares/minimize/minimize_scalarを初回呼出時にimport | 新規: NO_LAZY_SCIPY_IMPORT。可（案）: module先頭でimportして同じ実装へ委譲 | 短時間・代数直通・NOMADのみ。根拠: 遅延delegateの目的と実装 | 発見: production config→ordered attempts→worker/runtimeを追跡。探索アルゴリズムやseedを替えない起動費用の比較 |
| M147 候補診断出力の上限 | 巨大な診断表示・保存に時間を使う | E/contracts/external_pipeline_config.py:41; E/orchestration/run_external_pipeline.py:785 | debug候補32（sanity16）。元のall_recordsの全件保存機能ではない | 新規: FULL_CANDIDATE_DEBUG。可（案）: debug上限を外す比較。台帳dumpは別途必要 | 候補の多い問題。根拠: _build_debug_candidatesにlimit | 発見: production config→ordered attempts→worker/runtimeを追跡。選択前台帳の保存にこの出力を代用しない。ファイル3MB制約では分割保存 |
| M148 HP値を十分な桁で保存 | 計算後にambient精度へ戻すと保存時に桁を失う | G/runtime/worker.py:48 | mpf値はmax(550,保存bit数からの桁+10)で文字列化 | 単純OFF不可: なし。単純OFF不可: 精密化・PSLQ再生の証拠が失われる | 500桁候補の保存。根拠: _mpf_のbit数を使いnstr桁を決める | 発見: production config→ordered attempts→worker/runtimeを追跡。保存容量を削るなら正確二進タプル等の損失のない別形式が必要 |

表のスイッチ名は共通接頭辞`GEOSOLVER_ABLATE_`を省略した。CSVは完全名。既存の非ablation設定など、接頭辞が異なる名前は備考に完全名で書いた。

## 静的確認の結果と限界

凍結src 251ファイルをコミットの`git archive`と再比較し、不一致・余分なファイルは0。hash対象250ファイルで指定のsource_hashに再一致した。CSVは148行、全9列が存在し、重複ID・欠欄なし。表の273個の異なる参照位置（91ファイル）が凍結src内の実在行であることを確認した。詳細は[source-audit.json](source-audit.json)。

実施したのはコード読解と、ファイル比較・ハッシュ・参照位置・CSV整合性の小さな静的スクリプトだけ。solver実行、スイッチ実装、性能測定、既存実験記録の編集、commit/pushはしていない。共有worktreeのsrcは読んでいない。表はコードから見つかった機構の棚卸しで、未実行経路の動作や各機構の性能寄与を保証するものではない。

## 相互作用が強そうな組

- **残差書き換え × 解析微分 × 最終検証補正**：書き換えに依存するJの採用を連動させる必要がある。精密化だけOFFでは最終検証の同種変換が回復しうる。提案する新スイッチは両段の対象変換を止めるが、一般補正は残す。
- **残差書き換え × 代数前処理**：代数側のDistance・接条件の多項式化と180桁の初期値が精密化の困難を小さくする。NO_ALGEBRAICとの組合せで効果が変わる可能性がある。
- **多様な代表選択 × 初期値分散 × 救済箱 × 第2attempt**：代表選択だけOFFでも、新しいseedや箱から別の根が入る。母集団固定の再生比較と全体比較を分ける。
- **生残差順位 × 残差行スケーリング**：NO_DIVERSE_SELECTIONは距離選択だけでなくscoreから生残差への順位尺度変更も含む。両順位値を保存する。
- **正の尺度chart × 代数消去 × rank-aware Newton**：自由度を異なる段階で扱う。chartを止めても数値chartで局所的に収束する場合があるが、代数の有限列挙が成立するとは限らない。
- **探索箱 × 座標距離 × 差分幅 × 検証の変数尺度**：箱推定を替えると探索範囲以外の尺度も変わる。箱の変更を単なる大域探索の変更とみなさない。
- **guard内点sampler × 探索罰則 × 有界TRF**：可行な初期値が十分なら罰則の寄与が見えにくい。初期候補を固定して評価する価値がある。
- **1変数走査 × 接根の谷最小化 × 整数二乗列挙 × 整数closure**：同じ1変数根を別の入口が供給する。NO_ALGEBRAICという名前だけで整数・scalar入口まで消えると仮定しない。
- **warm Newton × LM桁上げ × post-LM closure × 最終座標補正**：前段の停滞を後段が補う。最終成功数だけでなく各段の元残差・答誤差を見る。
- **整数局所closure × 整数目標の範囲拡張・列挙**：最も近い整数への失敗を別整数目標から回復しうる。1入力から複数候補が派生し、最終検証数も変わる。
- **答の誤差見積り × 有効桁制限 × PSLQ尺度・係数上限 × π/定数式経路**：高い作業桁を指定しても正しい桁は増えない。PSLQ単体比較では上位の別入口を通さず、保存した同じ値と独立の参照値を使う。
- **各cache × 再試行 × 時間配分**：cacheのOFFは同じ締切内で処理できる候補数を変える。計算回数・候補数・時間の三つを併記し、純粋な関数の速度差と区別する。
