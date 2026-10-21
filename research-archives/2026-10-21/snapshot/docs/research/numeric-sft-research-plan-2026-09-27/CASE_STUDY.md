# Numeric SFT: relation reuse case study

2026-09-27。既存答案の読解とCPU上の有理数作図だけを行った。新しいモデル生成・GPU学習は行っていない。以下の関係は**評価設計と答案監査にのみ使う**。学習prompt・label・選抜規則として定理や証明を与える案ではない。

## 何が改善したか

主結果は12構図×2 decoding seedの全24答案でbase 11→numeric128 16、正答かつ妥当な主要導出3→6。3事例は全体集計の代用ではない。改善構図はDA06/DA11/DA15/DB08/H02、悪化はH12。H03/H08、DA11の片seed、DB16の片seedなど残る失敗・未完も主分母に残す。導出レビューは正答49件と未抽出2件の51件で、全誤答の数学的failure coverageではない。

根拠：

- `docs/research/transfer-reanalysis-2026-09-26/FOLLOWUP_REPORT.md`
- `qwen/.runtime/transfer_followup_20260926/final-review-aggregate/aggregate.json`
- `qwen/.runtime/transfer_followup_20260926/numeric-extended-score.json` の `source_ledger`（81k差し替えを含む正本の対応）

| 構図 | base→numeric正答 | numeric答案で採用した関係 | 証拠の限界 |
|---|---:|---|---|
| DA15 | 1/2→2/2 | D,Eを中線と垂直二等分線の交点として作ると、F=BD∩CEは直径AOの円上。従ってAF⊥OF、OF²=AO²−AF²=25 | 配置に正しく合う既知性質を引用。証明なし。両答案に数値のきれいさへの依存、捨てた誤計算、未撤回の誤付記がある |
| DB08 | 0/2→2/2 | 指定角から作ったEFに対しPXは円KLXのXでの接線。従ってPX²=PY·PZ=3·12 | 一致する既知lemmaの引用。接線性の証明なし。両答案に誤付記。整数と整合することを接線性の確認とする循環的付記もある |
| H02 | 0/2→1/2 | 円の交点と垂直二等分線を直接計算し、Z1=(−8,47/4), Z2=(−5,19/2)から15/4 | 81kのseed1だけの成功。共有固定点・共通弦から中心線の方向を導く短縮解法は答案にない。seed2は中心軌跡が底辺平行という誤推測で3 |

DA15ではbase seed1も同じ正答5を出した。改善はseed2の1→5であり、性質が完全に新しく獲得された証拠ではない。DB08ではbase両答案がX=Yを選んで3。H02 base seed1は4、seed2は3√313/16。

正本答案（JSONの`final_text`）：

- DA15: `qwen/.runtime/transfer_followup_20260926/numeric-numeric128-32768/numeric-transfer-da15-s1-0.json` と `...-s2-0.json`。
- DB08: `qwen/.runtime/transfer_followup_20260926/numeric-numeric128-32768/numeric-transfer-db08-s1-0.json` と `...-s2-0.json`。
- H02成功: `qwen/.runtime/transfer_followup_20260926/numeric-numeric128-81920/numeric-transfer-h02-s1-0.json`。32kは打ち切りで、81k正本は元prefixと同一ではない。
- H02失敗: `qwen/.runtime/transfer_followup_20260926/numeric-numeric128-32768/numeric-transfer-h02-s2-0.json`。

レビューの対応は`final-numeric-review/private-key.json`。DA15/DB08は`final-numeric-reuse/reused-grades.json`、H02は`final-numeric-reuse/remaining/grader/numeric-math-grades-adjudicated.json`に記録されている（上記runtime rootからの相対パス）。H02 case idは`case_43e2be5ffddc0c437214fb07a4443aed`。

## 学習7構図との数学的接続と因果の区別

学習はH01/H04/H07/H13/H15/DA01/DA05の各8数値pairで、定理や解法は供給されていない。

- **DA01↔DA15**：二接円の第二交点T（DA01）と、垂直二等分線を中線と交差させて得るF（DA15）は同じA-Dumpty点。その点は直径AOの円上。`benchmarks/humpty_configurations_v2/authoring/verify_additional_relations.py`の`Dumpty core`とDA15ブロックは一般座標で同一性と円への所属を確認する。ただしDA01の訓練targetはATであり、DA15のAF⊥OFを直接学習させたわけではない。数学的接続があることと、モデル内部でこの経路を使ったことは別。
- **H01/H04↔H02**：H01で定義する射影点Pは、H02の動く円AUiViの共通固定点。従って中心線はAPすなわちAMと垂直。H02の成功答案はこのPを同定せず、座標で中心を求めた。転移経路として採用したとは言えない。
- **H13↔H02**：新しい円の中心の所属と、弦の垂直二等分線・射影から距離へ移すという共通処理はあるが、同一の配置定理ではない。
- **H04/DA05↔DB08**：接線・割線の方べきという一般関係を共有する。H04ではAT²=TB·TC、DA05ではMD·ME=MB²。DB08固有のPX接線性までこの教材から学んだことを示すprovenanceはない。
- H07/H15にはこの3答案の改善を特定できる証拠がない。Humpty/Dumpty題材群という近さだけで因果経路を追加しない。

## 小さなCPU作図で用意できる診断

### DA15：非相似、新target、適用条件の破壊を1つの小作図で

非相似の正例：A=(0,4), B=(−2,0), C=(4,0)。三辺AB=2√5, AC=4√2, BC=6は互いに異なり、各頂点の内積は正なので鋭角scalene。O=(1,1)、AO=√10。元評価の13/12比ではなく、下記を直接測る：

- M=(1,0)（中点）。D=(5/7,8/7)、E=(4/5,4/5)、F=(4/17,16/17)。
- AO²=10、AF²=160/17、OF²=10/17。
- 元target OFの新条件はAO=√10, AF=4√(10/17)、答え√(10/17)。丸い5-12-13への適合を外せる。
- 新targetは「WをFから直線AOへの垂足としFWを求めよ」。同じAO,AFで答え **4√10/17**。関係AF⊥OFと、直角三角形の高さを組み合わせる必要がある。OFの公式を再出力するだけでは通らない。

適用条件だけを変える負例：同じABC、MをBCの内分点BM:MC=13:11へ変更し、D,Eの定義を維持する。完全三辺AB=2√5, AC=4√2, BC=6を問題文に与えてOFを問うので、2距離だけによる不定性は生じない。正例にも同じ三辺を与えてpromptの情報量を対応させる。

- M=(5/4,0)、D=(25/27,28/27)、E=(20/21,20/21)、F=(228/281,280/281)。D,Eは半直線AM上、Fは三角形内部。
- AO²=10、AF²=2720/281、OF²=10/281。
- AF²+OF²−AO²=**−80/281**なので元Rは成立しない。
- 元Rを誤用するとOF²=AO²−AF²=90/281、答えは正解√(10/281)の**3倍**。虚数になって即座に気づく負例ではない。

異なる作図で同じRを使う補助評価：同じABCにDA01の二接円を構成し、第二交点TについてOTを問う。T=(4/17,16/17)、OT=√(10/17)。円の中心は(−5/3,7/3)と(8/3,8/3)で、Tが両円上にあることを有理数で検算した。**DA01は訓練構図なので、これは未学習targetへの再利用診断であり、未学習構図率には算入しない**。異なる作図から同じ特殊点を認識できるかを測る。

### H02：既存generatorで非相似条件を作れる

`benchmarks/humpty_configurations_v2/authoring/gen_variants.py`の`gen_H02`はw/ax/ay/i1/i2から元円の交点と中心を構成している。A=(3,9), B=(−7,0), C=(7,0), BD1=4, BD2=9ならBC=14, AM=3√10, AK=9, BK=10>KC=4で、各頂点は鋭角。原問題との三辺比も異なる。

- 元target Z1Z2は **5√10/3**。generatorで正本交点を生成して確定する候補であり、ここでは新H02交点を実行生成していない。
- 新targetは「Z2から、Z1を通りBCと平行な直線への距離」。答え候補 **5/3**。中心差のBC成分5と、中心線⊥AMを使う。元答案の座標経路で成功することも認める。
- 異なる小作図による共通弦関係の診断は、H01のA,B,C,H,M,Pに円APBと円APCを追加し、中心ZB,ZCの距離を問う。上記A=(0,4),B=(−2,0),C=(4,0)ではH=(0,2),P=(8/17,36/17), ZB=(−2,5/2), ZC=(4,4)、ZBZC=**3√17/2**、中心差はAMと垂直。これは一般の共通弦→中心線の再利用を測るが、H02の隠れた固定点を発見した証拠にはしない。

### DB08：元の角指定作図を小さく移植して非相似化できる

`benchmarks/humpty_configurations_v2/authoring/verify_db_revision.py`の`check_general_relations`にA=(0,h), B=(−1,0), C=(c,0), c>1, h²>cの角指定からE,Fを構成する処理がある。元評価の(c,h)=(4,3)に対し、(3,4)は非相似。Fractionで元角指定の方向ベクトルと線交点、円束からσの中心を計算した：

- A=(0,4), B=(−1,0), C=(3,0), O=(1,13/8), P=(−19/2,0), X=(13/34,26/17)。
- E=(−19/34,30/17), F=(45/34,38/17), U=(−169/256,529/64)。
- PX²=100、UX²=3045025/65536、PU²=9598625/65536、(U−X)·(P−X)=0。
- PY=(5√383945−1745)/256、YZ=1745/128、元target PX=**10**。PY/YZ比も原3/9から変わる。全図形を先に構成して測った値で、PY,YZだけを勝手に上書きしていない。
- 新targetは三角形PUXの面積。接線性から面積=PX·UX/2。元条件PY=3,YZ=9なら **27/2**、上記新条件なら **8725/256**。UX=YZ/2だけを使うradius queryは接線性を試さないので避ける。
- 別構図の候補は既存heldout DA03（隠れたAK接線→AK²=KB·KC）。DB08固有の接線性とは別の前提で同じ一般方べきを使う。DA03元条件はbaseもnumericも2/2であり、この構図を追加してもそれだけでは新しい転移信号にならない。非相似条件の生成・直接検算を済ませるまでは具体的新labelとして凍結しない。

いずれも候補の少数診断を全体の改善率へ混ぜない。主評価は先に固定した全対象で集計し、この診断は①非相似でも成功、②新targetでも成功、③条件を崩すと誤用しない、の対応成功・失敗を全件提示する。3点全てを満たしても、内部の法則獲得や人間未知の数学を直接実証したとは言わない。

## DA15の再現可能なFraction検算

以下をsystem `python3`で実行できる。外部library・GPU不要。隠れたRを点やlabelの生成に使わず、元定義から線交点を求め、最後に残差を測る。

```python
from fractions import Fraction as Q

def pt(x, y): return (Q(x), Q(y))
def add(a, b): return tuple(x+y for x, y in zip(a, b))
def sub(a, b): return tuple(x-y for x, y in zip(a, b))
def mul(t, a): return tuple(t*x for x in a)
def dot(a, b): return sum(x*y for x, y in zip(a, b))
def cross(a, b): return a[0]*b[1]-a[1]*b[0]
def rot(a): return (-a[1], a[0])
def norm2(a): return dot(a, a)
def line(a, b, c, d):
    v, w = sub(b, a), sub(d, c)
    return add(a, mul(cross(sub(c, a), w)/cross(v, w), v))
def center(a, b, c):
    u, v = sub(b, a), sub(c, a)
    r = (norm2(b)-norm2(a))/2
    t = (norm2(c)-norm2(a))/2
    det = cross(u, v)
    return ((r*v[1]-u[1]*t)/det, (u[0]*t-r*v[0])/det)

A, B, C = pt(0,4), pt(-2,0), pt(4,0)
assert all(dot(sub(v,u), sub(w,u)) > 0
           for u,v,w in [(A,B,C),(B,C,A),(C,A,B)])
assert len({norm2(sub(A,B)),norm2(sub(A,C)),norm2(sub(B,C))}) == 3
O = center(A,B,C)
assert O == pt(1,1)
for t, expected in [(Q(1,2), pt(Q(4,17),Q(16,17))),
                    (Q(13,24), pt(Q(228,281),Q(280,281)))]:
    M = add(B, mul(t, sub(C,B)))
    mid_ab, mid_ac = mul(Q(1,2), add(A,B)), mul(Q(1,2), add(A,C))
    D = line(A,M,mid_ab,add(mid_ab,rot(sub(B,A))))
    E = line(A,M,mid_ac,add(mid_ac,rot(sub(C,A))))
    F = line(B,D,C,E)
    assert F == expected
    assert dot(sub(D,A),sub(M,A)) > 0
    assert dot(sub(E,A),sub(M,A)) > 0
    assert norm2(sub(D,A)) == norm2(sub(D,B))
    assert norm2(sub(E,A)) == norm2(sub(E,C))
    assert all(cross(sub(v,u),sub(F,u)) > 0
               for u,v in [(A,B),(B,C),(C,A)])
    ao, af, of = [norm2(sub(u,v)) for u,v in [(A,O),(A,F),(O,F)]]
    print('BM/BC=', t, 'M,D,E,F=', M,D,E,F)
    print('AO2,AF2,OF2,residual=',ao,af,of,af+of-ao)
    if t == Q(1,2):
        assert (ao,af,of,af+of-ao) == (Q(10),Q(160,17),Q(10,17),Q(0))
    else:
        assert (ao,af,of,af+of-ao) == (Q(10),Q(2720,281),Q(10,281),Q(-80,281))
        assert (ao-af)/of == 9
```
