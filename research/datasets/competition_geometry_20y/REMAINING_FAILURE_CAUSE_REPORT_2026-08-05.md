# 残存不正解ケースの原因監査（2026-08-05）

## 結論

source-faithful DSL 修正後に完了している「以前の失敗35件」の再測定
（seed 7、180秒 hard timeout、1 job、CPU 0）では、厳密解集合一致 **1/35**、
不一致 **34/35** だった。これは最新22件の修正を含む全302件の fresh runではなく、
失敗集合に対する最新の完了済み再測定と、最新v2 focused runを突き合わせた結果である。
一致した `HMMT-2021-FEB-GEO-05` は、`C` の内部条件を signed cross に直した後に
`49/400` だけを返しており、残存失敗から除外する。

34件の主因は DSL の未修正ではなく、次の solver 側の問題である。

| 分類 | 件数 | 判定 |
|---|---:|---|
| exactification 失敗（decimal-only） | 10 | 正解近傍だが exact 式を同定できず、数値文字列へ fallback |
| 開条件・退化境界枝の受理 | 12 | `>0`、`OnSegment`、凸性などの境界を数値的に通過 |
| 既修正DSLの境界枝/探索汚染 | 5 files | 修正後DSLでも solver が境界枝を受理・または timeout |
| 実行可能なのに no_solution | 3 | 独立 witness があり、探索/精密化の失敗 |
| timeout | 3（HMMT-2007 は上記と重複） | 180秒内に Phase C へ到達しない |
| 正解 basin 未到達（decimalのみ） | 1 | 独立 witness はあるが正解枝を取得できない |

`HMMT-2007-FEB-GEO-04` は、同じ source-faithful DSLで一度は `{17,7}`（`7` は
`u=0`/`v=0` 境界）を返し、別の再実行では180秒 timeoutになった。これは
DSLの意味差ではなく、境界枝を含む探索の不安定さとして扱う。

## 判定の証拠

- **E1（raw実行）**: [`benchmark_results_180s_1core_failed35_after_dsl_fixes.json`](benchmark_results_180s_1core_failed35_after_dsl_fixes.json)。35行すべてが `truth_status=verified` で、`phasec.answer_values`、status、rejection tagsを保存している。
- **E2（DSL整合性）**: [`DSL_DEFICIENCY_AUDIT_2026-08-05.md`](DSL_DEFICIENCY_AUDIT_2026-08-05.md) と `verify_dsl_integrity.py` は、302 DSL、source hash、truth ledger、IR parse、変数上限を `errors=0` で検査する。
- **E3（独立計算）**: [`REMAINING35_INDEPENDENT_WITNESSES.json`](REMAINING35_INDEPENDENT_WITNESSES.json) と [`verify_failure_case_independent.py`](verify_failure_case_independent.py) は solver を呼ばずに、実行可能な no_solution 例と DSL の代数矛盾を再現する。
- **E4（`Area` の意味）**: frozen runtime の [`basic.py`](/home/kabatan/work/solver-experiment-runtime/geosolver/src/geosolver/geometry/operations/basic.py:194) は polygon area を `Abs(s)/2`（同ファイル225行）で返すため、`Area>0` は内外・向きを表さない。
- **E5（exactification）**: frozen runtime の [`run_phasec_assembly.py`](/home/kabatan/work/solver-experiment-runtime/geosolver/src/geosolver/_internal/pipeline/orchestration/run_phasec_assembly.py:135) は `selected_exact_value` がない候補を同ファイル143行の `str(candidate.answer_hp)` に fallback する。

## ケース別の完全な帰属

### 1. decimal-only exactification failure（solver、10件）

raw値は正解に数値的に一致するが、`phasec.answer_values` に exact 式がなく、
厳密集合比較では不正解である。`AIME-2009-I-05` は `71.999...`、
`AIME-2015-II-11` は `3.599...`、`AIME-2016-I-06` は `3.333...`、
`AIME-2022-II-11` は `179.999...` だけを返す。同型は次の8件にも現れる。

`HMMT-2006-FEB-GEO-03`, `HMMT-2006-FEB-GEO-04`, `HMMT-2008-FEB-GEO-03`,
`HMMT-2010-FEB-GEO-01`, `HMMT-2013-FEB-GEO-05`, `HMMT-2023-FEB-GEO-01`。

この10件は方程式の解がないのではない。raw値が target の近傍にあり、E5の
fallback経路を通っているため、原因は PSLQ/SymPy exactification またはその前段の
精密化であり、DSL定義ではない。

### 2. strict boundary / degenerate branch（solver、12件）

raw Phase C と、DSLが要求する開条件の反例が一致する。

| case | rawに現れた余分枝 | source-faithfulな除外理由 |
|---|---|---|
| `AIME-2011-II-02` | `450` + `810` | `t=0`/`u=0` 相当の endpoint。sourceは “lies on side” とだけ書くため、endpointを厳密に除外するかは truth ledger の仕様確認が必要 |
| `AIME-2014-II-08` | target + `0` | 円半径 `e=0` 境界。DSLは `e>0` |
| `AIME-2018-I-04` | target + `10` | D/Eが endpoint に収束。sourceは strictly between |
| `AIME-2020-I-01` | target + `60` 近傍 | interior点の境界/無効数値枝 |
| `HMMT-2006-FEB-GEO-10` | `r≈0` | 円の `r>0` 境界 |
| `HMMT-2010-FEB-GEO-09` | `{70,160,180}` | `180` は凸四角形の一直線退化 |
| `HMMT-2014-FEB-GEO-09` | `{0,92/61}` | 第4円の `r4=0` 境界 |
| `HMMT-2014-FEB-GEO-10` | target近傍 + `2*sqrt(65)` 近傍 | `r1,t→0` の二重退化 |
| `HMMT-2018-FEB-GEO-05` | `{0,8*sqrt(2)/9}` | 面積0の退化枝。convex guard後の最新v2でも再現 |
| `HMMT-2023-FEB-GEO-02` | `{0,2*sqrt(13)}` | `u=0`、A=B endpoint |
| `HMMT-2023-FEB-GEO-04` | `{1,sqrt(5)}` | `q=p`。sourceの `AP<AQ` とDSLの `q>p` に反する |
| `HMMT-2024-FEB-GEO-03` | `{246,42}` | `h=0` の直径枝。source/DSLの非直径条件に反する |

`HMMT-2018-FEB-GEO-05` の最新版v2 rawは `0` と `8*sqrt(2)/9` であり、
新たに加えた `AssumeConvex([M,A,R,E])` で直るDSL欠落ではなく、面積の極小値を
solverが厳密な `>0` として通した証拠である。

### 3. 既に修正したDSL条件に残る solver 問題（5 files）

次のケースは、過去に見つかったDSLの条件欠落/過制約をすでに修正済みである。
修正後にも残った不一致は、DSL不備として再計上しない。

- `HMMT-2007-FEB-GEO-04`: tangent **ray**、円が三角形外側、`u,v>0` をDSLに追加済み。`{17,7}` の `7` は開条件境界、別 run では timeout。solverの境界受理と探索時間問題。
- `HMMT-2013-FEB-GEO-04`: `B!=O1` を追加済み。rawの `1` はその非退化条件の数値境界。solverが `B=O1` を通した。
- `HMMT-2024-FEB-GEO-10`: P inside を unsigned `Area` から signed side-of-edge 条件へ修正済み。targetに加え、ほぼ一直線の decimal枝が残る。solverの near-degenerate filtering 不足。
- `JMO-2019-MATHNET-08yk` / `JMO-2019-PRE-08`: 問題文にない `cx>0` を削除済み。両aliasが同じ `9*CRootOf(128*x**3-80*x**2+7*x-1,0)`（`AB=AC` 境界）へ進み、問題文の `AB>AC` を数値的に通している。solverの strict-inequality boundary failure。

### 4. 実行可能なのに no_solution（solver、3件）

独立 witness が存在するため、DSLの不可能性ではない。

- `AIME-2018-II-12`: `C=(1.6,11.2)`, `D=(-8,14)` で辺残差0、面積等式残差0、凸 turn `[112,84,112,140]`、面積112。runは全候補 `residual_too_large`。
- `AIME-2020-II-15`: 独立点で `BT=CT≈16`、`XY²≈717`、与式の和≈1143、acute dot productsがすべて正。runは `no_solution`。
- `AIME-2021-I-13`: `d=672`, `r=1000`、外接条件と中心角120°を満たす witness。runは `answer_missing`/`residual_non_finite`。

### 5. timeout（solver、3件。HMMT-2007は §3 と重複）

- `AIME-2020-II-13`: 180.106秒、Phase Cなし。5変数の接線 pentagon 探索が予算内に終わらない。
- `JMO-2013-PRE-08`: 旧 run の mpmath `findroot/LU` TypeError は runtime 修正後に消えたが、現 run は180秒 timeout。closure失敗後の探索切替が未解決。
- `JMO-2015-PRE-11`: 180.106秒、Phase Cなし。artifactからは探索・arc-midpoint評価・精密化のどこが支配的かまでは分離できない。

### 6. 正解 basin 未到達（solver、1件）

`HMMT-2015-FEB-GEO-04` は raw が `0.4953925...` から `0.7296142...` の decimalのみで、
正解 `37/76` を返さない。しかし独立 witness
`A=(-3/4,3sqrt(15)/4), B=(0,0), C=(2,0), D=(49/16,7sqrt(15)/16)` は
辺長 `3,2,2,4`、cyclic、面積比 `37/76` を厳密に満たす。従って DSL不可能性ではなく、
初期値探索・精密化・exactificationのいずれかで正解 basinを拾えていない。現artifactだけで
その内部段階を一つに断定することはできない。

## DSL不備との切り分け

最新監査で `verify_dsl_integrity.py` は `errors=0`、全302 JSONがIR parse済み、変数数は
0--7である。`HMMT-2021-FEB-GEO-05` の旧外側枝 `1/400` は signed cross 修正後に消え、
`AIME-2019-I-06`、`AIME-2022-II-07`、`HMMT-2022-FEB-GEO-05`、JMO-2019両alias、
JMO-2022両aliasなど、以前にDSL原因と確定したケースは修正後に厳密一致している。

残る定義上の注意は二つだけである。

1. `AIME-2011-II-02` の “lies on side” と `HMMT-2023-FEB-GEO-02` の “lie on segment” は、
   endpointを明示的に除外していない。現在の exact truth は競技問題の非退化解釈を採用しているため、
   endpoint枝を不正解とした。これは solver bug と truth/DSL仕様の境界なので、任意の epsilon を
   DSLへ足して解決してはいけない。
2. その他の残存枝は、問題文に記載された開条件・内外条件をJSONに反映した後にも出ている。
   したがって、post-processで落とすのではなく、solverの strict guard margin、候補受理、
   branch enumeration、exactification、timeout処理を修正対象とする。

## 限界

timeout 3件と `HMMT-2015-FEB-GEO-04` について、現在のartifactだけで内部の一つの
substageまで完全に特定することはできない。断定できるのは「180秒内に厳密解集合を返せなかった」
ことと、独立 witness の有無である。これは不明点を solver/DSL のどちらかへ誤帰属しないために
明示している。

なお、最新22件のDSL修正後に **全302件を再度180秒で回した fresh global run はまだ実施していない**。
したがって上の34件は、最新修正後の完全再測定結果と偽っていない。修正対象の verified rows は
[`benchmark_results_180s_1core_dsl_deficiency_repairs_2026-08-05.json`](benchmark_results_180s_1core_dsl_deficiency_repairs_2026-08-05.json)
と [`..._v2.json`](benchmark_results_180s_1core_dsl_deficiency_repairs_2026-08-05_v2.json) で別途確認し、
HMMT-2018-FEB-GEO-05だけが target + 余分な0、他のverified rowsは厳密一致である。
