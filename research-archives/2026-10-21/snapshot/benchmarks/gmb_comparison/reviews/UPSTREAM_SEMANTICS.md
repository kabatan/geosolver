# 公式GMB実装の意味・表現範囲に関する独立監査

監査者: `independent_review`。対象commit:
`f070afe18ed874b3a31db519ea6f593f40a1be00`。
実施内容はソースの読み取りと式の数学的確認のみ。36問の探索・精密化、
保存済みGMB出力の再採点は行っていない。

## 比較で区別する三層

1. IMO原文の幾何的仮定。
2. 公開GMBLが名義上指定している仮定・作図・枝。
3. 実装のパラメータ化、soft loss、許容誤差、追加の退化回避。

3の違いをすべてGeoSolver DSLへ移すのは適切でない。一方、1と2の不一致を
GeoSolver側だけで修正し、既存のGMB計測と同じ入力条件だったと主張することも
できない。独立判定器は数学的な条件を検査し、実装固有の制限は別途記録する。

## 確認した挙動

| ID | 実装箇所 (`src/optimizer.py` unless stated) | 確認内容 | 比較への影響 |
|---|---|---|---|
| GMB-S01 | `sample_triangle_on_unit_circ`, 428-446 | 一般triangleは3点を単位円上に置く。角パラメータは学習可能で、すべての非退化三角形は相似変換後この形にできる。 | 単位円固定自体は形の制限ではない。ただし相異なる点・非共線性はこれだけで保証されない。 |
| GMB-S02 | `sample_triangle`, 448-486 | acute-triではB=(-2,0), C=(2,0)、Axは[-1.2,1.2]から初期化され`trainable=False`、Ay=1.1+3 sigmoid(z)。 | 図形の形に制限があり、Axは一つの初期化からの最適化中には動かない。またA=(0,1.5)はこの表現内だが角Aは鈍角なので、名称だけでは鋭角性を保証しない。 |
| GMB-S03 | 同上 | right-triではAxが非学習変数で、Ay=sqrt(4-Ax^2)。指定頂点への入替え後、三角形全体の形が最適化中に固定される。 | 2012P5、2016P1のGeoSolver側へ同じ乱数形を与える比較とは異なる。これはsolver固有の探索制約として記録し、原文の自由度を削る理由にしない。 |
| GMB-S04 | `sample_polygon`, 385-426 | n角形の各パラメータ角は((n-2)/n)π±π/3の開区間。後続辺長は最初の辺長の(1/2,3/2)倍。閉路と角和は重み付きsoft loss。 | 一般の凸多角形すべてを表さない。四角形なら角範囲は(30°,150°)、六角形なら(60°,180°)。2007P2は3点polygonで、専用triangleとは異なる。 |
| GMB-S05 | `parameterize_on_seg`, 629-636 | A+sigmoid(z)(B-A)。 | 数学的には開線分。端点は有限パラメータで得られない。 |
| GMB-S06 | `between_gap`, 1103-1110; assertion `on-seg`, 909 | assertionのon-segはA+0.2(B-A)とB+0.2(A-B)の間を要求する差分を含む。 | 同じon-seg表記でもparamとの範囲が違う。名義上の線分所属を採点する際に0.2制限を原文条件へ追加しない。 |
| GMB-S07 | `onray_gap`, 1112-1118; `parameterize_on_ray`, 652-658 | paramはA+exp(z)(B-A)。assertは始点をA+0.2(B-A)までずらすsoft条件。 | paramは開半直線、assertはさらに0.2の余裕を求める。原文の点順に必要な条件とは分ける。 |
| GMB-S08 | `parameterize_in_poly`, 731-738 | softmaxの正係数による凸結合。 | 非退化凸多角形なら内部を表せる。非凸多角形では単に凸包内部なので、多角形自体の仮定が重要。 |
| GMB-S09 | `parameterize_on_minor_arc`, 677-702; `tf_optimizer.py:46-49` | 弧の割合zは初期値を[0.1,0.9)にするだけ。sigmoid・クリップ・最適化時のboundsがない。 | 2017P4では最適化後のzが弧外へ出る可能性があり、初期化範囲を弧のhard conditionと見なせない。 |
| GMB-S10 | `process_rs`, 1535-1570 | rs-arbitraryは乱数選択でも多枝探索でもなく、内部式のP2を返す。 | GeoSolverの座標辞書順n=2とは同じ意味ではない。原文が枝を指定するなら原文の意味で選ぶ。対称な一対なら両点を保持し名称交換の不変性を確認する。 |
| GMB-S11 | `pt_neq`, 1532; `process_rs`, 1538-1540 | rs-neqはP1が指定点から1e-6超ならP1、そうでなければP2。P2の非一致や候補数は検査しない。 | 非該当点・接点・近接枝を一意な第二交点と同一視しない。GeoSolver側は幾何的な第二交点を扱う。 |
| GMB-S12 | `process_rs`, 1541-1552 | closer-to-p/lは距離<=でP1を選びtieもP1。 | 原文に一意な近い方の指定がある場合、tieは許容しない独立判定が必要。 |
| GMB-S13 | assertion `same-side`, 946-951; `same_side`, 1135-1136 | assertionはmax(0,-crossprod)で、境界上でも残差0。selectorのsame_sideはcrossprod>0。 | 同じ名の述語でもhard branchとsoft assertionで境界挙動が違う。2010P2の弧・同側条件は原文のstrict性を確認する。 |
| GMB-S14 | assertion `i-bisector`, 881-884; `eqangle6_diff`, 1254-1260 | 角の外積・内積によるmodπ残差だけなので、内角と外角の二等分線をこの式だけでは区別しない。 | 2016P1の2つのassertでは、他の等長条件が内角・正向きrayを含意することを独立に証明済み（`EQUIVALENCE_ARGUMENTS.md`）。一般的な演算の曖昧さだけを根拠に本問の仮定欠落としない。 |
| GMB-S15 | assertion `gt` / `lt`, 856-869 | strict不等式を絶対量0.1の余裕へ置換している。 | 長さなら相似変換でも不変でなく、角なら0.1radの追加制限。GeoSolver側へ任意の0.1を移さない。 |
| GMB-S16 | `inter_pp_c`, 1158-1189 | 判別式<=0で非交差用fallback点を生成する。負判別式は交点ではない点になり得る。 | 出力の「交点」という名称だけで正当性を認めず、所属と存在条件を独立検査する。接線の場合も出力を再検査する。 |
| GMB-S17 | `inter_ll`, 1138-1156 | 交点式の分母が1e-4未満ならsign(denom)*1e-4へ置き換える。 | ほぼ平行な線で数学的交点と異なる座標を返し得る。所属残差と非平行を独立検査する。 |
| GMB-S18 | `points_far_enough_away`, 1570以降; `tf_optimizer.py:190` | 名前付き点の全組にmin_dist=0.1を要求し、さらに全点の相異なるよう促すlossを付加。 | 問題が要求していない点の相違までhard gateになる。原文にない全点相違をGeoSolver側へ追加しない。 |

## その他の注意

- GMBの角度`uangle`は余弦定理とacosによる無向角[0,π]。`eq-angle`は
  有向角modπに相当する別物。置換時に混同しない。
- `mkvar(lo,hi)`は通常は**初期化範囲だけ**であり、探索boundsではない。
  sigmoid、tanh、expが合成されている場合に初めて像の範囲が制限される。
- GMBの`get_model()`による受理と原文の全仮定成立は同じ意味ではない。
  この監査は保存済みモデルの正誤判定ではなく、その判定条件を作る前の実装確認である。
- `trainable=False`の値も、別の初期化の生成時には新たな乱数になる。
  「3 seed全体を通じて同じ三角形だった」という意味ではない。

## 監査したsource hash

```
8bad274ae726c1c703c2e7508280e2fa6f5b137e2d2a4918316507a1616399b8  src/optimizer.py
f2fa81d2cd37302a8df03b6a8dbfcc22879a2101a02f913585be94f3b0b7235e  src/tf_optimizer.py
e590444573c03378dec66ee493e23b24857c9d738bc960eb82f99bf5b526fed1  src/instruction_reader.py
```
