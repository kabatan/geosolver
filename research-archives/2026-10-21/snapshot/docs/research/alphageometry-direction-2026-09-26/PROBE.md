# 公開AlphaGeometry2 DDARと既存geometry backendの接続試験

2026-09-26。これは **手動翻訳した小さなCPU接続試験** であり、LLMによる性質発見、学習、転移、未知数学の発見の実験ではない。

## 結論

公開DDARに、このrepoの基本作図機能から得た座標と元の作図条件を渡すことはできた。しかし、**H01の正しい関係 `AM·MP=BM²` は、追加補助点なしの元の6点・6前提からは導出されなかった。垂心の定義を3本すべての高さに展開した7前提版でも、2形状とも未導出だった**。したがって「AlphaGeometry2をつなげば、現在の候補をそのまま幅広く検証できる」とは言えない。

さらに、公開 `check_pred` は導出DB内で既知かを返すAPIであり、導出過程や外部で再検査可能な証明書を返さない。数値座標から点の順序や向きなどを決める処理もある。これは自然言語の任意の証明を検証するAPIでも、座標の枝条件まで文字列前提から証明する独立proof kernelでもない。

## 固定した実行環境と範囲

- 公式リポジトリ: <https://github.com/google-deepmind/alphageometry2>
- 調査commit: `251e7e16f0bba8ac7c83cdea789fccc195d0c0c7`
- ローカル: `qwen/.runtime/alphageometry2-inspect-20260926`
- 既存 `.venv/bin/python` と既存NumPy/SymPyを使用。依存追加、GPU、LLM、学習なし。
- 座標生成には `geosolver.geometry` の `Point, Midpoint, Orthocenter, FootOfPerpendicular, Line` を使用。`solver.solve` は呼んでいない。
- 1workerの上限30秒、全実行の上限300秒。最終4workerの実行全体は約0.995秒。worker内CPU時間の合計は約0.562秒。これはimportや小さなH01の生成を含む限定試験の時間で、一般の候補検査コストや成功率には外挿できない。
- [実行スクリプト](probe.py)、[最終JSON記録](results.json)。JSONに全入力述語・全問い合わせ・座標・コードhashを保存した。

実行:

```bash
.venv/bin/python docs/research/alphageometry-direction-2026-09-26/probe.py
```

## 手動で行った翻訳

H01は、鋭角不等辺三角形ABC、BCの中点M、垂心H、HからAMへの垂足Pという既存配置である。DDARへ強制前提として渡したものは次の6述語だけ。

```text
coll b m c
cong b m m c
perp a h b c
perp b h a c
coll a m p
perp h p a m
```

最初の2つが中点、次の2つがHを2本の高さの交点とする定義、最後の2つが垂足の定義。候補式は前提へ入れていない。数値座標から観測した関係を別の前提として追加する処理もない。別の補助点を人が追加して陰性を救済する試験はしていない。

問い合わせも人が指定した既知の真偽候補であり、モデルや探索器が発見した候補ではない。

```text
eqratio a m b m b m p m   # AM/BM = BM/PM、すなわち AM·PM=BM²
perp c h a b             # 第3の高さ
eqratio a m b m b m p a   # AM·AP=BM² という誤候補
cong a b a c             # AB=AC という誤候補
```

2配置は `A=(1,4), B=(-3,0), C=(3,0)` と `A=(2,5), B=(-4,0), C=(4,0)`。いずれも鋭角不等辺。幾何backendでは正確な有理数で作図し、DDARの入力APIに合わせる段階でfloatへ変換した。別途、反例の判定には元の有理座標を用いた。

## 結果

`False` は **未導出** を意味する。偽を意味しない。

| 試験／候補 | 前提のみの直後 | closure後 | 独立な意味の確認 |
|---|---:|---:|---|
| 公式 `2004_p5` の元goal `AP=CP` | False | True | 公式入力を変更せず使用した動作確認 |
| H01 `AM·MP=BM²`、形状1/2 | False / False | False / False | 真。下記の一般変数による導出がある |
| H01 `CH⊥AB`、形状1/2 | False / False | False / False | 真。2本の高さの交点は第3の高さにも乗る |
| H01 `AM·AP=BM²`、形状1/2 | False / False | False / False | 偽。有理座標で反例あり |
| H01 `AB=AC`、形状1/2 | False / False | False / False | 偽。有理座標で反例あり |
| 形状1と同じ座標、全前提なし、上記4候補 | 全False | 全False | 数値上の一致だけでこの4候補が自動受理されないことの限定確認 |
| 追加の定義展開感度チェック: 高さを3本とも前提にしたH01 `AM·MP=BM²`、形状1/2 | False / False | False / False | 目的式の前提混入なし。元の6前提版とは別条件 |

真候補 `AM·MP=BM²` は、`A=(u,v), B=(-b,0), C=(b,0)` とおくと

```text
H = (u, (b²-u²)/v)
A·H = b²
P = b²/(u²+v²) A
AM·MP = b² = BM²
```

と導ける。これは本試験の人による独立な正しさの説明で、DDARが返した証明ではない。同様に `(H-C)·(B-A)=0` なので第3の高さも真である。

誤候補の厳密な残差:

- `AM²·AP²−BM⁴`: 形状1で `−17`、形状2で `−87`。
- `AB²−AC²`: 形状1で `12`、形状2で `32`。

したがって「DDARがFalseだから偽」とは判定していない。真の未導出と、独立反例のある偽候補を分けて記録している。

### 垂心の定義の展開に関する追加感度チェック

元の試験後、公平なカバー範囲の判断のため、Hが垂心であるという意味を `perp c h a b` まで展開した7前提版を別途確認した。この追加は既知の基本定義の展開であって、目的式を入力することではない。この条件では第3の高さそのものを問い合わせず、`eqratio a m b m b m p m` だけを問い合わせた。新しい補助点は追加していない。

両形状ともclosure後Falseだった。[追加スクリプト](probe_sensitivity.py)、[追加結果](results-sensitivity.json)。元の `results.json` は変更せず、追加結果には元記録のSHA256も保存した。追加2workerは1件30秒上限、全体0.117秒、worker内CPU計0.027秒。これは翻訳の感度確認であり、ML発見や未知性の証拠ではない。

```bash
.venv/bin/python docs/research/alphageometry-direction-2026-09-26/probe_sensitivity.py
```

## 公開APIと数値依存の確認

固定commitのソース:

- `ddar.py:131` の `force_pred` は述語を **前提として追加** する。候補をここへ渡すと検証にはならない。
- `ddar.py:259` の `check_pred` はDBで既知かを返す。今回の述語はboolで、返却値に証明traceはない。`acompute` だけは値またはNoneを返す別形式。
- `elimination.py:16` はモジュール説明を `Elimination of variables, without proof.` としている。`ElimCore` は制約消去と変数代入を保存するが、元前提と適用定理を結ぶ証明書を出力する仕組みはこの公開版では見当たらない。
- `ddar.py:92` で数値上ほぼ同じ点の組を除く。`ddar.py:382` で数値orientationを用いる。
- `ddar.py:415` 付近でSSAの場合の辺長大小を数値比較して適用を選ぶ。
- `ddar.py:745` 付近で共線点を数値座標に沿って並べ、その順序で加法的距離関係を追加する。
- `numericals.py:20` の `ATOM=1e-12` を使うfloat実装。箇所により残差の二乗と比較するため、全判定の誤差幅が一律1e-12という意味ではない。
- `elimination.py:330,409,501` 付近では追加する等式の数値整合をassertする。

この実装は数値の一致を無制限に定理へ昇格するものではない一方、枝や非退化条件をすべて明示した文字列前提だけで処理しているわけでもない。今回のTrueを、そのまま任意の入力に対する形式的健全性の保証とは扱わない。

## 実行中の修正記録と未実施事項

初回は点のy座標へPython int `0` を渡したため、repoのMidpoint内部で `0.0` になり、有理数の残差記録という意図に反した。初回を `initial_nonexact_archive/` に保存し、SymPyの正確なゼロに変更、全座標が有理数であるassertを加えて全4試験を再実行した。最終結果は本ディレクトリ直下の `results.json`。DDARのTrue/False結果は初回から変わっていない。

H14は翻訳・試験していない。このH01の未導出からH14の可否は推測しない。モデル候補を自動で述語へ変換する器、検証結果から教材を作る器、証明trace出力、探索のための新しい補助点生成も実装していない。

研究上の含意は、**数値backend＋DDARのAPI接続は可能だが、研究が欲しい候補の検証範囲と証拠の出力は未解決**、という限定されたものになる。DDARの導出済み命題だけを成功にすると、既存エンジンの導出範囲へ研究の目標を寄せる可能性もある。人間に未知の関係まで含めた発見能力を測る設計とは分けて扱う必要がある。
