# HMMT 2013年2月 Geometry 第9問：公式資料の再確認

確認日：2026-08-30。対象：`HMMT-2013-FEB-GEO-09`。

現行件数の追記：この削除の後、[別の重複6登録を除去](../dedup-20260830/README.md)したため、現在は323登録・323自然問題。以下の329件はこの問題を削除した時点の記録である。

## 追記：現行評価セットからの削除

同日のユーザー指示により、現行の `benchmarks/cases.jsonl` の当該登録と
`benchmarks/dsl/HMMT-2013-FEB-GEO-09.json` を削除した。
削除直前の登録を[removed-cases.jsonl](removed-cases.jsonl)へそのまま保全したため、
埋込DSL・公表答え・出典・隔離理由は復元できる。過去の実験artifactと修復台帳は変更していない。

現行セットは **329登録・329 DSL・参照確認済み329件・重複除去後323問題**。
修復生成器の通常実行・stagingからも除外し、再実行で復活しないことを試験する。
過去の矛盾の診断は保存したDSLを読み、現行の評価対象とは区別する。
削除後は関連49テスト、Ruff、修復生成器の整合検査、329件のvalidateが通過した。
削除前後のhash比較で、残る329登録・329 DSLに変更がないことを確認した。
以下は削除前の調査記録であり、330件という件数や隔離状態の記述は当時の状態を表す。

## 結論と今回の変更

通常角（0度から180度）として読むと、現在公開されている原題の条件には解がない。
DSLの転記を直せば公表答え `sqrt(39)` を持つ問題へ復元できる、という状況ではない。
公式の意図を特定できる訂正版は今回の調査では見つからなかった。

このため、DSL・公表答えは変更せず `truth_status=quarantined` を維持した。
今回更新したのは出典の再確認記録、修復台帳、参照保留の説明、および独立な矛盾計算の回帰試験である。
solver本体、過去の評価artifact、他の329登録は変更していない。
**実行可能330件・正誤評価に利用可能329件のままであり、330件への復帰は未完了。**

## 公式資料の確認

[主催者の2013年2月アーカイブ](https://www.hmmt.org/www/archive/162)からリンクされた次の資料を再取得した。

- [公式問題PDF](https://hmmt-archive.s3.amazonaws.com/tournaments/2013/feb/geo/problems.pdf)：PDFの2ページ、第9問。
- [公式解説PDF](https://hmmt-archive.s3.amazonaws.com/tournaments/2013/feb/geo/solutions.pdf)：PDFの3-4ページ、第9問。

PDFの該当ページを画像としても確認した。両資料とも角の和は300度であり、根号・分数も現在のDSLと一致する。
第9問専用の図や、通常角と異なる角度規約の注記はない。公表答えは `sqrt(39)`。
主催者アーカイブと関連語による検索から、訂正内容を裏付ける公開資料は見つからなかった。
これは「訂正が一度も発表されていない」と証明したものではない。

再取得したPDFのSHA-256は、保存済みの[source-manifest.json](source-manifest.json)と一致した。
保存場所は `/home/kabatan/work/solver-research-assets/corpus97-sources/`。

| 資料 | SHA-256 |
|---|---|
| `hmmt-2013-geo-problems.pdf` | `5082c8fdbe20b3f009e7a663eec9553659c18dfb0c4367e1c07840efed9297a2` |
| `hmmt-2013-geo-solutions.pdf` | `0516792add40a5e8ccacde82d5f8a9ad2398f42171677aa88716d961733fb1b2` |

## 通常角による条件が矛盾することの独立な証明

以下は公式解説を無条件に採用した結論ではなく、その補助点が存在できるかを追加検証したものである。
solverの探索成否や数値誤差には依存しない。

### 1. 条件から必要な補助点の位置・距離を導く

解があると仮定し、`α=∠DAE`、`β=∠CBD` とおく。条件より `α+β=45°=∠BAD`。
角BAD内で `∠PAB=α`、`AP=AE·AB/AD` となる点Pを取る。

二辺とその間の角から `APB~AED`。さらに積の条件から

\[
\frac{AP}{AD}=\frac{AE\cdot AB}{AD^2}=\frac{BC}{BD},
\qquad \angle PAD=\beta=\angle CBD
\]

なので `PAD~CBD` も成り立つ。したがって

\[
PB=DE\frac{AB}{AD}=5,\qquad
PD=CD\frac{AD}{BD}=7,\qquad
\angle BPA+\angle APD=300^\circ.
\]

ここで `AD/BD=3/√5` は三角形ABDへの余弦定理から得られる。
Pは角BAD内にあり、最後の角の和が180度を超えるため、三角形ABD内になければならない。
境界を許す解釈まで含めても、閉じた三角形ABD内であることが必要になる。
よって `∠BPD=60°`。三角形BPDへの余弦定理から

\[
BD^2=5^2+7^2-2\cdot5\cdot7\cos60^\circ=39.
\]

これは必要条件であって、元の配置の存在を保証するものではない。

### 2. その補助点は三角形内に入らない

三角形ABDで `AB/AD=2√2/3`、`BD/AD=√5/3` だから

\[
\cos\angle DBA
=\frac{AB^2+BD^2-AD^2}{2AB\cdot BD}
=\frac1{\sqrt{10}}.
\]

一方、必要な辺長 `PB=5, PD=7, BD=√39` より

\[
\cos\angle DBP
=\frac{39+25-49}{2\sqrt{39}\cdot5}
=\frac3{2\sqrt{39}}.
\]

どちらの余弦も正であり、その二乗の差は

\[
\frac1{10}-\frac9{156}=\frac{11}{260}>0.
\]

従って `∠DBP > ∠DBA`。概数では `76.1021° > 71.5651°` である。
しかしPが閉じた三角形ABD内なら `∠DBP ≤ ∠DBA` でなければならず、矛盾する。
したがって必要なPも元の通常角の配置も存在しない。

この議論は `SimplePolygon` による追加の排除には依存しない。
既存の[AUDIT_26.md](AUDIT_26.md)の二円の全交点・重心座標による反証とも一致する。

## DSLの扱いと復帰条件

現在のDSLの正規化JSON hashは、今回の前後で
`e7e6730e68e0ee2db70bdf96d169d4e8f9aa0273d53e63fae5de153b272deafc` のまま。
300度を60度へ変える、長さを入れ替える、都合のよい外角を選ぶ、といった変更は
公式原題の意味保存修復とはいえないため行わない。

正誤評価への復帰には、訂正版・出題者の説明などにより修正内容を特定し、修正後の条件と
参照解集合を独立に確認する必要がある。連絡が必要になっても、承認なく主催者へ送信しない。
こちらで問題を改題する場合は別IDの派生問題として明記し、元の自然問題の修復と混同しない。
単に解が見つからなかった実行を「空の参照集合に一致した正解」として数えることもしない。

## 再現

[audit26_mathematics.py](audit26_mathematics.py)の `hmmt_2013_angle_obstruction` が上記の有理数・根号計算を行う。
既存の `hmmt_2013_published_configuration` は二円の両交点が内部点でないことを独立に確認する。
回帰試験は両計算、300度の条件の保持、DSL hash、公表答えと隔離状態の保持を検査する。

```sh
.venv/bin/python -m benchmarks.repairs.corpus97.audit26_mathematics
.venv/bin/python -m pytest tests/test_corpus97_repairs.py -q
.venv/bin/python -m benchmarks.repairs.corpus97.apply_repairs --check
.venv/bin/python benchmarks/research_runner.py validate
```

通常角での矛盾は上の数学的証明による。テスト通過や追加の180秒探索を存在・不存在の証明とは扱わない。

今回の確認結果：

- `test_corpus97_repairs.py` と `test_research_runner.py` の48テストが通過。
- 変更したPython 4ファイルのRuff lint・format checkが通過。
- 修復生成器の `--check` で97登録・埋込DSL・個別DSL・台帳の一致を確認。
- runnerのvalidateは `valid=true`、330登録・330 DSL・329参照確認済み、問題報告0件。
- 更新前後のhash比較で全330 DSLファイルが不変。他329登録も不変で、対象1登録の参照説明のみを更新した。
- solverの変更や新たな性能評価は行っていない。
