結論1：LMはT0/T1/T2すべて有限差分。Newtonは系全体の解析計画を条件付きで使い、不採用・評価失敗時は差分へ戻る。
結論2：固定12問中11問は解析計画を静的に排除でき、指定の改善4問もT1/T2とも差分。残るHMMT-2008のT1/T2は未確認。
結論3：S1の書き換え無効化も平滑化依存計画の採用を止めるが、この4問の改善を「解析／差分の切替」で説明する根拠はない。

# S6：精密化のヤコビ計算方法の静的監査

[switch-scope.md](switch-scope.md) の「解析ヤコビ行列計画の可否も変える」を、計画生成・採用・実評価に分けて補足する。対象は `/tmp/s3-impl/src` と [S3/switch.patch](../S3/switch.patch)。solver、実験、記号微分コンパイラ、候補点での残差・ヤコビ評価、pickleのロードは実行していない。git commit/pushもしていない。実施したのはテキスト／既存JSONの読解、標準ライブラリによるAST検査・hash照合、監査文書の作成だけである。

原文引用、1始まりの行番号、ファイルSHA-256、12問の入力・保存先頭候補UID・静的判定は [jacobian-audit-evidence.json](jacobian-audit-evidence.json) に保存した。以下の `E:...` は同JSONの `excerpts` キー。ソースの省略名 `J` は `geosolver/engine/standard/refinement/analytic_jacobian.py`、`M` は同ディレクトリの `mpmath_refiner.py` を指す。特記しない限り `/tmp/s3-impl/src` 配下。

4つの実ソース木のhashをファイル読取だけで再計算し、記録値と一致した。

| 呼称 | 実体・source_hash |
|---|---|
| S3 | `/tmp/s3-impl/src`、`sha256:add5afaf829806ca3cbd11fb07b69d956102752e1c6738b0630581a3ceb121eb` |
| S1精密化版 | `/tmp/mechanism-S1-1m9aomj8/final/src`、`sha256:03a44bfbb743b972d95306c63a14c04b78c7d12b96a1ba83d147c56eea7f86a3` |
| BASE0：凍結版60db4b6 | `/tmp/mechanism-S1-1m9aomj8/frozen/src`、`sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5` |
| BASE1：凍結版＋既存ablation patch | `/tmp/switch-check/BASE1/src`、`sha256:e2115f553d6a59d6d85a30413e5719992c09e376d23d3e3e124fd07fd135b8ee` |

BASE1とS1の比較arm名 `BASE` は異なる。既存の呼称は `switches/README.md:5` の「**BASE1（凍結版60db4b6＋指定の既存patch）に対する差分**」と同21–23行のhashによる（`E:baseline_names`）。S3の全実装ファイルは `S3/impl-hashes.json` と一致し、S1の `J`・`M` はS3 patch適用前ソースとバイト一致した（証拠JSON `checks`）。

## (a) モード別・段階別の条件

「計画あり」は実際に解析ヤコビが評価されたことを意味しない。生成、closureでの採用、各点での評価成功を順に通過する必要がある。既に目標を満たす開始点なら、`M:1022–1024` の `certified_start` で計画要求前に戻る。

| 段階・条件 | T0 | T1 | T2（未設定時も同じ） |
|---|---|---|---|
| LM `_run_stage` | 有限差分 | 有限差分 | 有限差分 |
| Newton・通常の平滑化不要計画 | 共通ゲートを通れば解析可 | 同左。ただしDistance=半径ゲートあり | 共通ゲートを通れば解析可 |
| Newton・`requires_smoothing=True` の計画 | 生成できても採用不可→差分 | 書き換え有効・行数一致なら採用可 | 書き換え有効・行数一致なら採用可 |
| Newton・T1用Distance=半径が1行以上 | このT1専用ゲートはない | **系全体の計画生成を拒否**→差分 | このT1専用ゲートはない |
| 計画なし／採用不可 | mpmathの差分。rank選択にも差分 | 同左 | 同左 |
| 計画採用後、ある点で解析評価失敗 | その点の行列全体を差分へ | 同左 | 同左 |

LMでは `M:1463–1476`（`E:s3_lm`）に次の直接呼出しかなく、`derivative_plan` を呼ばない。

```python
1464: current_jacobian = compute_finite_difference_jacobian(
1465:     point=current,
1466:     dps=int(dps),
1467:     residual_fn=residual_fn,
1468:     one_sided_at_cusp=_problem_contains_call(bundle.spec, "Angle"),
```

`row_dependencies` は差分の列の同時評価に使う依存情報で、解析微分計画ではない。自前差分は `finite_difference_jacobian.py:92–93,120–138` で `step=max(1,abs(x))*10**(-min(max(dps//2,1),30))` の中心差分を基本とし、境界では片側差分、指定されたcuspでは非零の方向傾斜を使う（`E:s3_fd`）。残差式はモードによって変わるため、「すべて差分」は同じ数値行列という意味ではない。

Newtonの計画生成の共通ゲートは `J:170–185`（`E:s3_plan`）。

```python
171: if ablated("NO_ANALYTIC_JAC"):
172:     return None
173: if bundle is None or not 2 <= len(bundle.var_names) <= 12 or bundle.spec.logical_plans:
174:     return None
```

入力は変数名、construction、**全constraintsとその右辺targets**。ここでtargetsは問題の答え式ではない。`J:148–167` は記号workerに `timeout_seconds=1.5` で要求し、任意計画のタイムアウト・所定の例外を `None` にする。compileでは未対応呼出・キーワード引数・比較等のAST、ゼロ距離の行展開、表現の演算数300超、導関数合計1500超等も系全体の拒否理由になる（`J:53–145`、`E:s3_compile`）。

T1の追加ゲートは `J:32–36`。接点証明の有無に関係なく `distance_radius_sources` が非空なら止める。

```python
32: # Frozen plans do not differentiate the T1 Distance=radius replacement.
33: if mode == "T1" and distance_radius_sources(
34:     construction, tuple(zip(constraints, targets, strict=True))
35: ):
36:     return None
```

IsTangent=0の微分対象はT2なら証明可能な接点式、なければ直線・円の二乗式。T1なら接点式を試さず二乗式を作る（`J:83–113`）。この経路が通れば `requires_smoothing=True`。T1/T2とも円・円の任意の接残差を常に記号微分できるわけではなく、接点式がない場合のfallbackは `geometry.line` と `geometry.circle` を要求する。T0はT2と同じ既定payloadを使って生成を試みるが、平滑化依存計画の**採用**を止める。`J:183–185` の原文は `if tangency_mode() == "T1": key = (*key, "T1")`。従って「T0はderivative_planを一切呼ばない」は誤りである。

closureの追加ゲートは `M:1033–1051`（`E:s3_adoption`）。独自residual_fnやinteger closureは解析計画の対象にしない。native residualでも行数不一致なら不採用。平滑化依存時には次をすべて要求する。

```python
1042: plan["requires_smoothing"]
1043: and not (
1044:     isinstance(residual_fn, partial)
1045:     and residual_fn.keywords.get("smooth_zero_constraints")
1046:     and not ablated("NO_RESIDUAL_REWRITE")
1047:     and tangency_mode() != "T0"
1048: )
```

warm Newtonもpost-LM closureもこの `_run_findroot_closure` に入る。warmの入口は変数数>1、残差数>=変数数、候補のhard feasibility、整数条件なし、期限内を要求する（`M:2000–2027`、`E:s3_warm`）。post-LMはfeasibilityとclosure開始閾値等で選ぶ（`M:1733–1789`、`E:s3_polish`）。本監査は段階に到達した回数や候補の実軌跡を確認したものではない。

採用した計画でも `J:211–233` はOnSegmentの内部条件、非零条件、値の有限性、評価例外で `None` を返す（`E:s3_evaluate`）。Newtonの原文は次のとおり（`M:1112–1119`、`E:s3_newton`）。

```python
1112: values = analytic_values(list(args))
1113: if values is not None:
1114:     return mp.matrix(values)
1115: from mpmath.calculus.optimization import jacobian
1117: return jacobian(mp, residuals, mp.matrix(args))
1119: options = {"J": closure_jacobian} if plan is not None else {}
```

計画がなければ `J` 引数を渡さず、ローカル依存ライブラリ `mpmath/calculus/optimization.py:639–644` が `ctx.jacobian` を選ぶ。同579–599行の原文は `h = ctx.sqrt(ctx.eps)`、`Jj = (ctx.matrix(f(*xj)) - fx) / h` で、**前進有限差分**である（`E:mpmath_default_J`, `E:mpmath_jacobian`）。ベクトル出力なら同935–946行でMDNewtonになるため、呼出側の `solver="mnewton"` という文字列だけから別の解析微分経路を推定しない。

rank-aware fallbackはまず解析行列を試し、なければ自前有限差分でランクと部分系を選ぶ（`M:856–868`）。部分系のNewtonも解析行列の該当行列要素かmpmath差分を使う（885–893行）。ただしactive変数1個なら902–914行で割線法を使い、反復用の解析Jを渡さない（`E:s3_rank`）。元から1変数の場合も `M:1059–1097` で1残差なら割線法、複数残差なら解析JなしのベクトルNewtonである。

## 固定12問：保存先頭候補に対する静的判定

表の「無」は**採用できる解析計画なし**、「差分」はヤコビ計算に進んだ場合の方法。「未確認」は生成の成功・1.5秒制限・候補点での評価成功を実行しないと確定できないことを表す。計画は座標をキーにせずbundleから作るので、構文拒否は先頭候補だけでなく同じbundleの他候補にも当てはまる。実際に先頭候補でNewton／LMが呼ばれたとは断定しない。

入力原文の場所は `/tmp/mechanism-S3-3vgkcgwz/runs/<問題ID>/input.json`、表のLはその行番号。`E:input_<問題ID>` に引用を保存し、`cases[].first_candidate` に保存候補index 0のUID・座標・変数名・出典hashを保存した。候補順は既存 `initial.json` と事前固定manifestの先頭UIDを照合した。

| 問題 | 変数数 | T0 | T1 | T2 | 静的根拠・入力原文引用 |
|---|---:|---|---|---|---|
| AIME-2015-II-15 | 1 | 無・差分/割線 | 無・差分/割線 | 無・差分/割線 | L4 `"theta"`。変数数ゲートで生成なし |
| AIME-2018-II-14 | 4 | 無・差分 | 無・差分 | 無・差分 | L54 `"left": "Collinear(A, Q, C)"`。未対応呼出 |
| HMMT-2008-FEB-GEO-09 | 2 | 生成未確認／採用無・差分 | 未確認（解析可候補／差分） | 未確認（解析可候補／差分） | L62 `"left": "IsTangent(Line(A, B), incircle)"`。生成できれば平滑化依存。T0は採用不可 |
| HMMT-2009-FEB-GEO-10 | 4 | 無・差分 | 無・差分 | 無・差分 | L46 `"left": "Area(P, C, D)"`。未対応呼出 |
| HMMT-2010-FEB-GEO-09 | 2 | 無・差分 | 無・差分 | 無・差分 | L75 `"left": "Angle(I, D, E)"`。未対応呼出 |
| HMMT-2020-FEB-GEO-09 | 1 | 無・差分/割線 | 無・差分/割線 | 無・差分/割線 | L4 `"p"`。変数数ゲートで生成なし |
| HMMT-2022-FEB-GEO-10 | 2 | 無・差分 | 無・差分 | 無・差分 | L55 `"left": "OnCircle(A, omega)"`。未対応呼出 |
| HMMT-2023-FEB-GEO-07 | 5 | 無・差分 | 無・差分 | 無・差分 | L54 `"left": "OnCircle(A, Gamma)"`。未対応呼出 |
| JMO-2013-PRE-05 | 3 | 無・差分 | 無・差分 | 無・差分 | L14 `"left": "Collinear(P, R, X)"`。未対応呼出 |
| JMO-2024-PRE-06 | 7 | 無・差分 | 無・差分 | 無・差分 | L67 `"left": "Collinear(B, E, C)"`。未対応呼出 |
| aime-2001-2-7 | 4 | 無・差分 | 無・差分 | 無・差分 | L95 `"left": "Perpendicular(st_line, pr_line)"`。未対応呼出 |
| aime-2002-2-14 | 3 | 無・差分 | 無・差分 | 無・差分 | L83 `OnSegment(contact_am, A, M)` → L39 `"expression": "ContactPoint(omega, am_line)"`。依存先の未対応呼出 |

拒否の根拠は `J:37–70`（`E:s3_compile`）のホワイトリストと次の走査である。

```python
55: sources = list((*constraints, *targets))
60: if isinstance(node, ast.Name) and node.id in definitions and node.id not in visited:
61:     visited.add(node.id)
62:     sources.append(definitions[node.id])
65:     or node.func.id not in supported
68:     return None
```

`Collinear`、`Area`、`Angle`、`OnCircle`、`Perpendicular`、`ContactPoint` はこのsupported集合にない。幾何ライブラリ一般の対応範囲や `CartesianPolynomials` 自体の機能が広くても、この先行ゲートを越えない。接点式への変換より**前**に全入力を検査するため、T2で接点行が簡単になってもこれらの拒否は消えない。

公開入力からbundleへの変換も追跡した。`problem/adapter.py:77–81` は等式をその式名のままconstraintsへ、不等式をguardsへ入れる（`E:adapter`）。`compiler.py:61–87` のマクロ展開はRatioとTangentAtPointで、上記の拒否根拠は変えない。`load_problem_bundle.py:49–54` のloweringはconstructionのTangent/Intersect契約の変更、incidence／logical行の追加であり、上記の元等式・ContactPoint依存を取り除かない（`E:compiler`, `E:bundle`, `E:construction_lower`, `E:incidence_lower`, `E:logical_lower`）。

HMMT-2008だけは等式から参照するconstructionを辿っても、呼出が `Distance`, `Point`, `IsTangent`, `Line`, `Circle`, `sqrt` に収まる。答え式だけが使うP/Qの `Intersect` はこの計画のrootsではないため、それを理由に拒否してはいけない。Distance等式3行は点間距離であり、T1のDistance=半径ゲートには該当しない。T1/T2は解析計画生成の候補になるが、compile、演算数検査、時間制限、各点のnonzero条件を通過したという観測はない。**計画有・解析使用済みとは記載しない。**

## (b) T2の解析計画は接点行だけか

**系全体の計画であり、解析可能な行だけを解析、残りを差分にする混合方式ではない。** `J:75,123–140`（`E:s3_compile`）の原文は次のとおり。

```python
75: for source, target in zip(constraints, targets, strict=True):
123: expression = geometry.scalar(geometry.parse(source)) - rhs
127: rows.append(expression)
128: derivatives = [sp.diff(row, variable) for row in rows for variable in variables]
138: "rows": len(rows),
140: "derivatives": [str(expr) for expr in reduced],
```

IsTangent行では特別な式をrowsに入れ、他の行も同じrowsに入れて全変数で微分する。未対応の行や依存constructionが1つでもあれば `return None` で**全計画を破棄**する。行列を作れた後も `evaluate_jacobian` の条件不成立・非有限値で行列全体が `None` となり、closureが全行列を差分評価する。rank-awareの部分系は作成済み行列の行・列を選ぶだけで、混合計画ではない。

書き換えでDistance=0が2行に展開されたり、正半径の補助式が追加されたりすると、`M:1040` の行数一致ゲートでも全計画を捨てる。`M:697–700` の原文は `# Keep every original row as well as the auxiliary equations.`、`rewritten.extend(...)`（`E:s3_smooth_tangency`）。従って「T2で接点を使うなら必ず解析ヤコビ」は成立しない。

## (c) S1の書き換えあり／なしとBASE1

**一般にはS1にも、書き換えの有無に伴う解析計画の採用差があった。ただし計画の生成要求自体を変えるスイッチではない。** S1の `J:162–174` は `NO_ANALYTIC_JAC` を読み、`NO_RESIDUAL_REWRITE` は読まない。両armは同じbundleを同じ計画キーにする（独立プロセスなのでキャッシュ共有を意味しない）。

S1の `M:1031–1039` は次の採用条件を持つ（パスは冒頭表のS1精密化版、`E:s1_adoption`）。

```python
1031: plan["requires_smoothing"]
1032: and not (
1033:     isinstance(residual_fn, partial)
1034:     and residual_fn.keywords.get("smooth_zero_constraints")
1035:     and not ablated("NO_RESIDUAL_REWRITE")
1036: )
1039: plan = None
```

同 `M:1356` の `if smooth_zero_constraints and not ablated("NO_RESIDUAL_REWRITE"):` は残差書き換えも止める（`E:s1_residual`）。`runtime/ablation.py:17–18` の原文は `return os.environ.get(f"GEOSOLVER_ABLATE_{name}") == "1"`。環境変数が単に存在するだけでなく、値が `1` のときに無効化する（`E:s1_ablation`）。

| S1の計画 | 書き換えあり（未設定） | 書き換えなし（`=1`） |
|---|---|---|
| 生成不可の系 | 両方とも計画なし→差分 | 同左 |
| 生成可・`requires_smoothing=False` | 他ゲートを通れば解析可 | 同じく解析可。全解析計画を止めるわけではない |
| 生成可・`requires_smoothing=True` | smooth指定・行数一致なら採用可 | **生成できても不採用**→差分 |

固定12問では、上表の11問はS1でも同じ変数数／未対応呼出で拒否される。S1のsupported集合も `J:29–44` で同じである（`E:s1_compile`）。HMMT-2008だけは書き換えありの生成・採用が未確認、書き換えなしは平滑化依存のため採用なし。従って、S1でも指定改善4問について解析／差分の切替は認められない。

S1 driverは `stage/S1/driver.py:40–45` で既存ablation変数を取り除き、refineには `final/src`、verifyには `frozen/src` を選び、書き換えなしのrefineだけに `GEOSOLVER_ABLATE_NO_RESIDUAL_REWRITE="1"` を渡す（`E:s1_driver`）。両精密化armが凍結版を直接使っていたわけではない。

BASE1本体にはこの書き換えスイッチの分岐がまだない。`BASE1/M:1354` は `if smooth_zero_constraints:`、採用ゲート `M:1030–1037` にもablation条件がなく、`BASE1/runtime/ablation.py:5–12` の一覧にも `NO_RESIDUAL_REWRITE` はない（`E:base1_residual`, `E:base1_adoption`, `E:base1_ablation`）。同名変数をBASE1へ渡しても書き換え・計画採用は切り替わらない。凍結BASE0の対応行も同じである（`E:base0_adoption`, `E:base0_residual`）。

追加patchの原文は `switches/new-switches.patch:171–184` にあり、`+ and not ablated("NO_RESIDUAL_REWRITE")` を採用ゲートと残差ゲートの両方へ追加している（`E:s1_switch_patch`）。S3 patchはさらにT0の採用拒否とT1用Distance拒否等を追加した（`S3/switch.patch:39–43,73–77,131–135`、`E:s3_patch`）。

## (d) 改善4問の解釈と最小の追加実験案（実行しない）

既存 `S3/run/answer.md:7–37` はAIME 2018・JMO 2013・JMO 2024のT2での大改善、aime 2002のT1/T2で同程度の改善を報告している（`E:saved_result`）。これを新たに測定したものではない。

| 対象 | T1とT2の解析／差分が違う可能性に対する静的判断 |
|---|---|
| AIME-2018-II-14 | 両方ともCollinearで全計画を拒否。解析／差分の切替はない |
| JMO-2013-PRE-05 | 両方ともCollinearで全計画を拒否。解析／差分の切替はない |
| JMO-2024-PRE-06 | 両方ともCollinearで全計画を拒否。OnCircle等も拒否要因。解析／差分の切替はない |
| aime-2002-2-14 | 両方ともOnSegmentから辿るContactPointで全計画を拒否。解析／差分の切替はない |
| HMMT-2023-FEB-GEO-07（追記：T1 161→T2 485の大改善） | 先頭候補の静的判定（L54 `OnCircle(A, Gamma)` の未対応呼出）でT0/T1/T2とも計画なし・差分。解析／差分の切替はない。ただし静的判定は先頭候補の問題入力に対するもので、動的ログは未取得 |

この4問について「T1が差分、T2が解析なので大改善した」という説明はコードと合わない。T2が使う接点式／T1が使う非接点式の違いは、**同じ差分方式でも微分対象・条件数・零点付近の傾斜を変える**。ただしコード読解だけで改善量の因果や全候補の時間打切りの影響まで確定はできない。

**一般の入力では計画採用が変わる条件があるため、S3の差の一部が「接点式の効果」ではなく「ヤコビの計算法の違い」による可能性がある。** 例は、他に拒否要因がない系でT1のDistance=半径ゲートだけが発動する場合や、T1/T2で式の複雑さ・対応幾何・演算数上限の成否が変わる場合である。これは**今回の改善4問で成立したという主張ではない**。固定12問の未確認枠はHMMT-2008であり、T1/T2のどちらかが実際に解析を使ったか、動的fallback率が違ったかは未確認。

追加実験を行うなら、次が最小である。以下は提案だけで、コード変更・実行とも行っていない。

1. 同じ保存候補、精度・反復上限・予算・原残差の認証条件を固定し、T1/T2の**両方に**既存の `GEOSOLVER_ABLATE_NO_ANALYTIC_JAC=1` を設定して比較する。T2だけ差分強制を加えた既存T2との比較なら、T2内のヤコビ方式の寄与を検査できる。T1/T2両方を差分に固定した比較なら、方式の切替を除いた残差式の差を測れる。改善4問は既に静的に計画なしなので、この介入は計画選択に関して冗長な確認である。
2. 未確認のHMMT-2008を含め、計画要求・生成結果・採用拒否理由・解析評価成功／失敗・自前差分／mpmath差分の回数、段階、候補UIDを記録する。これにより「計画あり」と「実際に解析使用」を区別する。先頭候補だけでなく採用候補・打切りを含む主張なら全処理候補を対象にする。
3. 解析側からも切り分ける必要がある場合は、T1の**実際の残差系全体**と一致する解析計画を実装し、同一T1残差で解析強制／差分強制を比較する。T1のDistance拒否やsupportedゲートを外すだけでは正しい微分にならない。改善4問には未対応construction・行があるため、既存スイッチだけでT1解析強制はできない。T2の接点式の導関数をT1へ流用する比較も無効である。

計画生成・採用・実評価のログを伴わず、残差ベクトルの一致や `analytic_jacobian` のimportだけから使用方式を断定しない。本監査の未確認は未確認のまま残した。
