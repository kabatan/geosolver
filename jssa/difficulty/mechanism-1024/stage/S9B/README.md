# S9 部分B：結果を見る前に固定する問題の性質

事前登録16の「実行前に固定するもの 2」。事前登録15の106問（開発外34問＋S4.6の機構72問）について、入力DSLの性質と指定された既存の局所探索記録だけを表にした。S8のrun、構成別の成否・時間、N・C1・N+1の結果は開いていない。S8内で読んだファイルは、問題一覧の取得に許可された `stage/S8/assignment.json` のみ。使用項目は `problems[].case_id, cohort, dsl_path, input_sha256`。機械割当やハッシュ順位は性質に使わない。commit/pushは行っていないため、事前登録本文のpush要件を達成したとは扱わない。

ここでのパスは、特記しない限りリポジトリのルートからの相対パス。S8以外の過去の局所探索の当たり率はユーザーが指定した入力資料であり、今回評価するS8の結果とは区別する。

## 成果物と再現

- `properties.csv`：106行、問題IDの辞書順。問題×性質と出典列。
- `build_properties.py`：DSLの読み込み・構文コンパイル・既存CSVの結合・整合検査。探索、精密化、求解、S8の採点は呼ばない。
- `inputs.json`：許可された準備物から取得した106問とDSLパス・SHA256だけの一覧。
- `condition-details.json`：各問の元条件、変数名、コンパイル後のguard・作図、壁チェックID・種類・参照シンボル。集計値を個々の条件まで追跡できる。
- `p-provenance.json`：既存pのファイル、ヘッダーを1行目とする行番号、列名、用途、取得できる場合は当たり数・出発数。
- `source-hashes.json`：DSL全106ファイル、一覧・定義文書・過去のp表・計算スクリプト・使用した製品PythonモジュールのSHA256、依存版。コンパイルの主要11ファイルは凍結commit `60db4b679b04167175c51c479c87c22fa663fda0` とバイト一致を検査する。現在の作業ツリーの別実装へ黙って切り替えない。
- `validation.json`：件数・欠測・既存記録との照合。`artifact-hashes.json`：成果物8ファイルのSHA256（自己参照は除く）。

実行例（今回利用できた既存環境。新しい環境の導入はしていない）：

```bash
PYTHONDONTWRITEBYTECODE=1 /tmp/q40b-env/bin/python -B jssa/difficulty/mechanism-1024/stage/S9B/build_properties.py
PYTHONDONTWRITEBYTECODE=1 /tmp/q40b-env/bin/python -B jssa/difficulty/mechanism-1024/stage/S9B/build_properties.py --check
```

Pythonとpydantic、mpmath、numpy、sympyが必要。実際の版は `source-hashes.json` に固定。計算は1プロセス、内部数値スレッドも1、最大並列4以内。新しい局所探索や完成solverの実行は0回。Python監査フックは、許可された一覧以外のS8ファイルのopenとS8のディレクトリ列挙を拒否する。`--check` は表を再計算して全成果物のバイト・ハッシュを照合する読み取り専用モード。元ファイルまたは実行環境が変われば不一致として停止する。

## 性質の定義

| 主列 | 定義 |
|---|---|
| `n_search_variables` | 凍結版と同じ `GeometryProblem.engine_document()` → `load_problem_bundle()` で得た `len(bundle.var_names)`。作図された点の座標数や等式の本数ではなく、探索に渡る自由スカラー変数数。数学的に固定された変数の除去も反映する。補助列 `n_dsl_variables` は元の `variables` 長。この106問では両者は一致する。 |
| `n_constraints` | 元DSLの `conditions` の項目数。等式、非等号の関係式、predicateを各1件と数える。作図・target・追加された残差行は分母に入れない。 |
| `n_inequality_guards` | 元DSLの `conditions` のうち `operator` が `!=, <, <=, >, >=` の項目＋`predicate` 項目の数。`n_relation_inequalities + n_predicate_guards`。本登録の「不等式（ガード）」を広義のguardとして固定する。 |
| `inequality_guard_fraction` | `n_inequality_guards / n_constraints`。0〜1の比率。百分率にするなら100倍。 |
| `n_wall_conditions` | 凍結版のコンパイル後の `len(bundle.hard_feasibility_checks)`。一定hard罰則の可否に関わる、静的に列挙されたチェックの数。下記の解釈・限界を参照。 |
| `p` | S5.1のseed 0の既存 `p`。この性質だけはDSLから新たに計算した量ではなく、指定された過去の測定値を使用する。予測B2に使用する主値。seedを混ぜず、最大値や都合のよい測定を選ばない。 |

数え方は条件の項目単位。例えば `Bound(t,(0,1))` は1件、複合 `Or(And(...),...)` も1件で、内部の比較演算子の数に展開しない。predicate内の論理等式も、製品adapterがguardに送るためguardに含める。一方、`OnSegment(...)=0` 等の残差関数を使う等式は等式1件。重複や恒真の可能性がある元条件も入力どおり数え、数値的に発火可能かは調べない。

コンパイル時には作図契約からguardが追加され、重複文字列が除かれ、論理等式・点の所属条件から残差が補われることがある。`n_compiled_guards` と `n_compiled_equalities` はそれらを反映した補助列で、元DSLの主列・割合とは混用しない。元guard数とコンパイル後guard数が異なる問題は15問。B1の不等式数は **`n_inequality_guards`** に固定する。

## S5.6の「壁」と条件数の解釈

探索した記録：事前登録16の参照箇所、`jssa/draft/supplement-v14.md` のS5.6・S5.1・S4.1、S5.6から参照される `jssa/strategy/astra-consult-17/G/census.py`、S5.1の `jssa/difficulty/start_feasibility.py`、製品のhard-feasibilityコンパイラ・評価器・局所探索backend。

S5.6（`supplement-v14.md`、見出し「境界での『壁』」）には、条件を破る側への移動で等式残差が減っても一定hard罰則により一歩が拒まれる、という機構の説明がある。ただし、**入力から「壁の条件数」を数える正式な定義は書かれていない**。そこでS5.1のhard feasibilityと、Gの `census.py` の `n_checks = len(bundle.hard_feasibility_checks)`、既存S5.1表の `n_checks` に合わせ、静的チェック数として操作的に定義した。この解釈をS5.6原文の明示定義とは称さない。

`compile_problem_hard_feasibility.py` が生成する種類は次の5つ。`properties.csv` の `n_wall_<種類>` に内訳を保存し、合計が `n_wall_conditions` と一致する。

| 種類 | コンパイル規則 |
|---|---|
| `guard` | コンパイル後の `spec.guards` の各項目に1件。明示不等式・論理述語・作図由来のguardを含む。 |
| `line_distinct` | 作図の最上位が `Line` / `LineThrough` で、先頭2引数が名前参照の場合に1件。 |
| `triangle_nondegenerate` | 最上位が `Circumcircle` / `TriangleCenter` / `Incircle` / `Incenter` で、先頭3引数が名前参照の場合に1件。 |
| `intersection_exclude_distinct` | 最上位が `Intersect` で `exclude` が名前参照の場合に1件。 |
| `intersection_selection_trace` | 最上位が `Intersect` で `near` / `far` が名前参照の場合に、それぞれ1件。 |

作図契約の証明によって `exclude` が `far` とguardに書き換わる場合があるので、元の式を単に正規表現で数えず、凍結版のコンパイル後のチェックを使う。入れ子のLineなどを勝手に別チェックへ展開しない。同じ幾何条件に複数のチェックが対応してもチェックID単位で数える。この72問の計算値は既存S5.1の `n_checks` と全件一致した。

局所探索backendの `_evaluate_hard_feasibility_penalty` はhard feasibility不成立または例外で `1e3` を返し、`_evaluate_augmented_residual_vector` が10倍して最後の1成分に加える。複数チェックを破っても一定罰則の成分数は1であり、「壁チェック数×1e4」ではない。破れに比例する滑らかなguard罰則はこの数に足さない。

S5.1には作図が評価できることも含まれる。評価失敗・非有限入力などの全体ゲートは実装の実行状態によるもので、入力から独立した各境界の数を列挙できない。`n_wall_conditions` は静的に列挙された5種類の数とし、全体ゲートを恣意的に1件加算しない。`wall_evaluation_status_gate` 列にその存在を明記し、元作図の数も `n_constructions` に残す。したがって、この数は実際に一歩を拒んだ回数、独立な境界数、発火し得る条件だけの数、探索空間の難しさを厳密に数えた量ではない。実際の発火や拒否は今回測定していない。

## pの出典と欠測

| 用途 | ファイル・列 | 定義・対象 |
|---|---|---|
| 主値 `p` | `jssa/difficulty/start-feasibility-1023/per-problem.csv` の `p`、キー `id` | S5.1、seed 0。`(hit_feas + hit_infeas) / starts`。`starts = n_feas + n_infeas`。機構72問に存在し、開発外34問には存在しない。分子・分母も保存。 |
| S4.1系の元局所探索記録との照合 | `jssa/difficulty/minima/basins-323.csv` の `p`、分母 `n_starts` | 同じseed 0の元局所探索集計。対象72問のp・分母が主値と完全一致。S4.1参照先にある完成solverの構成比較をpとして使わない。 |
| 補助 `p_seed1` | `jssa/difficulty/start-feasibility-1023/per-problem-seed1.csv` の `p`、キー `id` | S5.1、seed 1。72問に存在。主値と平均しない。 |
| 補助 `p_symmetry_original` | `jssa/difficulty/symmetry-break/per-problem.csv` の `p_original`、キー `id` | 無介入originalの局所探索。対象中9問。別プロトコルなので主値の置換・混合には使わない。`p_break_plus/minus` や構成別の完成solverの時間は性質として抽出しない。 |

主値の生成コードは `jssa/difficulty/start_feasibility.py`。`minima/raw-323` の保存された出発点を使うseed 0の再集計で、新しい局所探索ではない。本作業ではそのrawファイルも開かず、指定の集計表を利用し、分子・分母からpを再照合した。S4.1の参照から元の局所探索まで追う補助資料は `supplement-v14.md` S4.1とS5.1、および `probe_basins.py`。`symmetry-break` の別プロトコルは `local_stage2.py` に記載される。

元の局所探索は箱から一様に選ぶ出発点で、原則LM、等式の数が変数数より少なければPowell。`probe_basins.py` では残差 `<= 1e-8`、guard/hard feasibility通過、求める値がいずれかの参照値と `1e-6 * max(1, abs(ref))` 以内なら `hit`。pは**いずれか1つの正解値を持つ有効配置に当たる割合**で、答え集合全体を回収する成功率ではない。実行予算で出発数が200に届かない場合も、保存された実分母を使う。

IDの曖昧な正規化・類似問題への転用はしない。機構72問について `benchmarks/cases.jsonl` の同一IDにある埋め込みDSL、参照先DSLファイルと対象入力の一致、変数数を照合した。生ファイルは `input_sha256` でも一覧と一致を検査する。

`NA` は文字列で欠測を明示し、0へ置換しない。今回、pは72件あり34件NA。開発外34問は新たに測定せず `p_na_reason=no_existing_record`。p=0は観測された当たり0回でありNAとは異なる。探索変数0の5問も表から除外せず、pを1または0と推定しない。制約0なら割合をNAとする（今回は5問）。出典・当たり数・分母に値がない場合もNA。pがある行の `p_na_reason=NA` は理由欄が非該当という意味。

## 後で行うB1〜B3の比較の固定

**この表には結果群、成功フラグ、N・C1・N+1の成否、時間、効果量、群別中央値を作らない。** 以下は将来S8結果と結び付ける際の定義のみ。

事前登録15のseed 601〜603について、独立参照の**答え集合全体**と完全一致したseedが3回中2回以上なら、その問題・構成を成功とする。N+1はC1と同じ構成なので重複観測にしない。

- 増える群 G：Nで不成功かつN+1（=C1）で成功。
- 増えない群 H：106問のうちG以外で、両構成の成否が確定している全問題。両方成功・両方不成功・Nのみ成功を含む。
- 結果欠測を不成功に置換しない。いずれかの成否が未確定ならG/Hに仮割当せず、件数と理由を報告する。欠測のまま全106問についての結論は確定しない。

| 予測 | 比較に用いる性質・判定 |
|---|---|
| B1 | `median_G(n_inequality_guards) > median_H(n_inequality_guards)`。厳密な大小で、等値は成立しない。 |
| B2 | 主値 `p` がNAでない問題のみを各群で使い、`median_G(p) < median_H(p)`。群ごとの元件数・有効件数・NA件数とコホート内訳も報告する。seed 1やsymmetryの値で補完しない。 |
| B3 | `abs(median_G(n_search_variables) - median_H(n_search_variables)) <= 1`。事前登録の中央値差という基準であり、他の分類器や検定の性能を意味しない。 |

中央値は問題を等重みとし、偶数件なら中央2値の算術平均。G/Hのどちらかが空、またはB2のどちらかの有効件数が0なら該当予測は判定不能。多いseed数で問題を重くしない。pの34件NAはすべて開発外群なので、B2の完全ケース比較が評価する範囲は機構72問に限られる。欠測を理由に別の問題を追加しない。

予測B4/B5の時間比較、部分Aの候補・特異値・精密化は本成果物の対象外。
