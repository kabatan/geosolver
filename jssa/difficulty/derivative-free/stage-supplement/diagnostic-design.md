# 補遺の固定設計（未実装・未実行）

凍結版`60db4b679b04167175c51c479c87c22fa663fda0`を使い、srcと`benchmarks/research_runner.py`は編集しない。別タスクで作る薄いラッパーだけが探索器の差替え、時刻記録、保存を担当する。今はsolverのimport、数値smoke、候補の再評価もしていない。

## 対象・始点・3探索器

[selection.csv](selection.csv)の順でQ32の21問を全数使用。対照はQ27d censusからd=1…7ごとに、対象外・m≥dの中でmin(p0,p1)が最大、同率はSHA256(ID)昇順の1問。旧Q32と完全一致した。成績を見て補遺用に選び直さない。[全28 ID](selected-problems.txt)。

seedは32001/32002/32003、各8始点。最初の16点はQ32の物理座標をそのまま再利用し、3番目のseedだけID・seed・点番号・座標番号のSHA-256から53bit一様数を作った。[starts.json](starts.json)に全672点を保存。新しい予測は既知のQ32結果に条件付く。旧2seedを未知の検証標本と呼ばず、32003の結果も単独表示する。

| arm | 探索 | 目的／残差 |
|---|---|---|
| N | 凍結NomadConfigのDiscoMADS、PyNomad | 元の残差二乗＋hard不許容なら有限1e6、評価不能はcallback失敗 |
| L | SciPy `least_squares(method='lm',jac='2-point')` | 凍結`_evaluate_augmented_residual_vector` |
| Lnp | 同じLM | `[F,0,1000*I(hard不許容)]`。有限点で二乗和がNの目的に一致 |

物理箱・変数順は保存入力と同じ。Nの箱拡張なし。L/LnpはQ32と同じく箱外を探索できるが、単体採点・共通投入候補からは箱外を除く。m+2<変数数なら零行を足しLMを維持する。Powellへ切り替えない。有限差分、失敗評価も元残差呼出し1回として数え、**各始点1,200評価または6秒の早い方**、早期収束の残予算で再開しない。LMのftol/xtol/gtolは各1e−14。NはMAX_EVALも1,200。単位座標化、行尺度、平滑化なし。評価不能のLnpはQ32同様1e10の残差ベクトルで、その件数を別計上する。

乱数は始点とは分ける。各点のN内部seedは`(seed*1009+k) mod (2**31-1)`。N/L/Lnpの点順はk=0…7で共通。3 armの実行順は問題順iとseed番号sに対する循環`(i+s)%3`、同じ問題は同じCPUを使う。

各評価を保存し、native返却点も別に保存する。候補選択のscoreは全arm共通のN側有限scoreとし、最適化用scoreとは別欄に置く。有限・箱内の記録へ、凍結`build_guard_feasible_ledger`（prefix=64、compact=20）を同じ順序で適用。許容prefixが空なら凍結`deduplicate_search_candidates`（keep=20、distance=1e−4、min_per_seed=3）を有限・箱内記録へ適用する。入力同値点を勝手に丸めない。候補選別に参照答えを使わない。この共通候補化は診断上の介入で、元backendの返却規則の忠実再現とは区別する。

## 2つの比較を混ぜない

**D：共通後段。** 28問×3seed×3arm＝252バッチ。8始点の探索（最大48秒）から同じ規則で得た最大20候補を保存してから、凍結`run_refinement`→`assemble_exact_results(input_precision_dps=120)`へ送る。後段に新しい120秒を等しく与える（精密化96秒、同定・検証終了まで120秒）。設定・解析Jacobian・残差書換え・検証・同定は同一。第2探索、rescue、代数的前処理、離散追加探索はこの比較には入れない。候補品質と処理順だけの比較であり、Dを完成solverの成績と呼ばない。1バッチ全体は180秒で打切る。

**F：完成構成。** 同じ252バッチ、既存CLI相当の180秒・1コア。凍結production baselineで、**第1試行の最初の数値`run_search`だけ**を上のN/L/Lnpへ置換する。前処理・initial probeの時間も総予算に含める。前処理で終わった場合は探索を強制しない。第2探索、rescue、離散completion、refiner、検証、同定、試行選択の方針とコードは全arm同じ凍結版を呼ぶ。第2探索のNOMADやSciPyまでLMに置き換えない。前段に使った時間は180秒から実際に差し引かれ、Fでは後段の時計をリセットしない。

Fは「指定した第1探索＋凍結版の残り」の診断完成構成。元の200評価・probe選択開始の完成版そのものではなく、既存63/63の再現を約束しない。Dの記録をFに無料注入せず、Fでも実際に探索して計時する。**Fの順位逆転に使う単体成績はF自身の探索列から計算**し、Dの実測値と差し替えない。全3arm×3seedで第1数値探索へ到達した問題のみ主逆転判定が可能。前処理で終わった問題は`not_exposed`として全体正答率の分母には残し、逆転の分母と別に表示する。

Fの残り総予算が探索上限より短ければ総予算を優先する。第1数値探索へ到達後の未開始・未完了始点はSの24点分母に残し、保存済み最良許容点がなければ0とする。前処理で探索不要だった場合や保存契約失敗とは区別する。後者はNAで、判定可能問題数と理由を必ず示す。

## フックと記録

探索差替えは`orchestration.run_external_pipeline`内の`run_search`参照を、試行contextを持つラッパーで差し替える。`_execute_ordered_search_attempt`でprimary/fallbackを追跡し、primary内の1回だけ発火したreceiptを必須とする。Dの別driverは公開された候補・後段契約を直接呼び、solverの数式や検証を複製しない。Fは既存CLI/workerにラッパーを載せ、最終resultの生成経路を残す。nativeメソッドやhybridと単体LMを取り違えない。

候補保存は`run_refinement`と`refine_added_candidates`の入口、さらに`MpmathRefiner.refine_candidates`入口で漏れを照合する。後者だけでは発見時刻が分からないので、評価完了時の記録も採る。`_refine_single_candidate`、`assemble_exact_results`、`verify_final_candidate`、`identify_answer`、試行選択を包み、戻り値・順序・例外を変えずに記録する。参照のimport先にパッチが届くことを後で検査する。

各候補について、run/arm/attempt/phase/backend/seed/start/eval、`CandidateKey.uid`、親UID、revision、floatのhex座標、元残差・guard・hard・目的値、候補選別の採否と順位、wall/CPU/評価回数を保存する。整数candidate_idだけでは結合しない。closure由来の子は親まで追い、途中の改訂を上書きしない。

| 記録 | 意味 |
|---|---|
| `t_eval_end` | その座標を評価して候補記録へ入れた時刻。重複座標でもUID単位で記録 |
| `t_enqueue` | 精密化直前に候補tupleへ入った時刻。探索終了時刻と発見時刻を区別 |
| `t_refine_start/end` | 実際の候補処理開始／終了。未処理はNA＋理由 |
| `t_verify/end`, `t_exact/end` | 検証・同定の開始／終了。再検証は別event |
| `accepted`, `selected_attempt`, `public_answer_used` | 検証採用、試行採用、最終答え供給を別々に記録 |

全時刻は同一worker内の`monotonic_ns`差、CPUは`process_time_ns`差。子プロセスのCPUは別に積算し、workerのCPUと二重加算しない。ログ書込み時間も記録して実wallから勝手に引かない。探索終了後の待ち`start−enqueue`、探索中の滞留`enqueue−eval_end`、先行候補の処理CPU、自身の処理CPUを分ける。段階別タイマーの単純和で発見時刻を作らない。

**発見の事後ラベル。** 全FとDを完了・保存・hash固定した後だけ、Fの第1数値探索が投入した最大20候補を各1回、共通の凍結後段で独立再生する（精密化8秒＋検証・同定4秒）。最大5,040再生。これは診断shadowで、Fへ返さない。答えを読めるのは再生後の採点側だけ。既存採点と同じcanonical exact keyによって正しい参照値を供給した候補の`min(t_eval_end)`を`discovery_good_value`、`min(t_enqueue)`を`enqueue_good_value`とする。多答問題は各値を分け、全参照値を覆えた時刻は値別最初時刻のmaxとする。singletonの一致を答え集合全体の正答と呼ばない。

再生12秒で未完了なら`censored`、再生予算内で棄却なら`rejected_within_budget`。主実行で正答を供給した候補はその実行での陽性証拠も別欄で保持する。未投入・間引かれた全評価点の精密化可能性は調べないので、発見時刻は**実際に投入された候補集合の範囲**の指標。shadow陰性を「正答へ進めない候補」と断定しない。打切りがある問題では最初の発見時刻は部分同定とする。

## 成功・順位の事前定義

- 単体S：各始点の「元残差最小の有限・箱内・guard/hard許容点」をQ32規則（元残差≤1e−8、参照rのいずれかと`abs(value-r)≤1e−6*max(1,abs(r))`）で診断採点。各問題24点。native返却点を同じ規則で採点したS_native、残差≤1e−4だけの粗到達を必ず併記する。これらは公式正答ではない。
- 完成C：**凍結`research_runner.assess_campaign`をそのまま使う**。正常終了とcanonical答え集合全体の完全一致。余分・欠落・timeout・実行契約違反は既存判定のまま。Dにも同じ採点を用い、D/Fの表を分ける。
- 主「率逆転」：同一問題・同一pair(A,B)でS_A−S_B≥3/24＝12.5pt、3seedすべての単体差≥0でうち2seed以上正、FのC_B−C_A≥1/3、かつAだけ正答したseedがないこと。少数seedによる**記述的判定**で、統計的有意性の宣言ではない。Bだけ正答が2seed以上なら強い再現、1seedなら弱い再現と併記。N/L、N/Lnp、L/Lnpの全pair・両方向を事前対象とし、1問は1回だけ数える。
- 副「速度逆転」：同じSの優位条件で、両armがFで3/3正答、単体劣位armのpaired F wall比の中央値≤0.8、3seedすべて比<1。このときだけ速度逆転とする。率逆転へ合算しない。保存完了までのwallを使い、精密化・採否の時刻も別に示す。
- nativeで単体の符号が消える／反転する場合は「候補返却規則依存」。S_nativeでも同じ閾値を満たすものを別の頑健数とする。主基準を事後にnativeへ替えない。
- 問題等重みで対象21と対照7を別集計。既知Q32と新seedの結果も分ける。欠測を分母から黙って落とさない。95%区間を付けるなら固定seed32299の問題単位10,000回bootstrapとし、選択された開発問題の記述的区間と明記する。

Fで差が消えDだけ逆転、または採点点・予算・開始点の違いだけなら、完成solverでの逆転の支持にはしない。後段の精密化で単体差が消えるだけでも主命題の成功とはしない。複数問題・32003で整合しても、深い理論やsolver固有性は別の根拠が必要である。
