# Q29cの対象・数え方・再現

Q29節の全文を最初に読んだ上で、担当3の静的監査のみを行った。未使用26問は `prereg/target-26.txt` で固定。54候補全体を分母にしない。Q19の正誤は採点済み `assessment.jsonl` の `in_target=true` の130行をそのまま使用する。失敗10問とは0/5の8問と、AIME-1997-04の1/5、AIME-1991-14の4/5。成功16問は全5回正解。

開発群は `benchmarks/cases.jsonl` の323問。JSONL全体と各独立DSLのbytesが凍結commit `60db4b679b04167175c51c479c87c22fa663fda0` と一致し、JSONL内DSLと独立ファイルのJSONも一致することを検査した。未使用26問は解答転記前の `revisions/v3-input-freeze.json` のDSL hashと全件一致する。修正前入力はGitの台帳・beforeスナップショットから読み取った。作業用コピーのDSL変更、solver呼出し、配置生成、封印tarや展開後runの読み取りは行わない。

## 自由変数と作図点

- `n_vars`（d）：公開DSLの `variables` 配列の要素数。制約を課した後の数学的自由度やJacobian rankではない。
- `k_constructed_points`（k）：名前付きの点を返す作図呼出しの数。Midpoint、Intersect、FootOfPerpendicular、Circumcenter、Incenter、Centroid、Orthocenter、Reflect、Rotate、ContactPoint、IncircleContactPoint、Centerを数える。PointOnSegment/Line/Circleは、その位置パラメータがDSLの自由変数に依存しない場合に限り数える。点数であり、2倍して「消去変数数」とはしない。
- `k_four_ops`：上のうちMidpoint、直線同士のIntersect、FootOfPerpendicular、Circumcenterだけ。既存の `expand_k.py` の4種類の作図に対応する感度分析。ただし同スクリプトの正規表現による展開可能性検査そのものではない。
- `k_active`：条件・求値から参照される作図だけを数えたk。依存関係を再帰的に追う。
- `n_point_formula`：Pointの座標に単なる定数・名前以外の式がある点数。kで拾わない表現の補助指標で、消去された点の実数とは解釈しない。

**「歴史的に何点を消したか」は現DSLだけから復元できない。** kは比較可能な保守的な代理値である。`Point(既知の式,既知の式)` として代入された点、座標ゲージによる削減、スカラー式に埋まった定理・対称性は拾わない。逆に固定点の多数の補間は数える。AIME-1991-02の668点がその例。主解析は26問のまま、同1問を除いた値も感度分析として保存した。座標式を含めた完全な消去数だとは主張しない。

## 不等式と枝条件

- `n_inequality_rows`：conditionsのoperatorが `>, <, >=, <=, !=` の行数。
- `n_inequality_atoms`（I）：上記にpredicate内の比較原子を加える。`a<b<c` は2、`Bound(t,(lo,hi))` は2と数える。Orの各肢は重複を畳まず構文の出現数として数える。
- `n_guard_rows`（G）：conditionsのうち、operatorが `=` でない行。全predicateを含む。論理等式を含むpredicateも入るため「全てが幾何的な枝選択」とは限らない。
- `n_selectors`（S）：Intersectの `exclude/near/far/n`、Arcの `including/excluding`、Excircleのvertex、IncircleContactPointのside等の**明示的**選択を持つ呼出し数。1呼出しを1とし、キーワード2個でも2にはしない。対応する位置引数も調べる。
- `n_or`：Or呼出し・Pythonのorノード数。可能な解の枝数・DAG展開後の分岐数ではない。
- `n_integer_calls`：IsInteger呼出し数。整数条件は等式残差として書かれるためIやGには入らない。

IとGは重なる。未使用26問はpredicateがなく全て明示比較で、I=Gになる。OnSegment等の関数内部の順序条件や、sqrt・接円等の暗黙の定義域、solverが追加するhard条件はIに展開しない。S=0でも暗黙の枝がないわけではない。名前・数式を `ast.parse` で読むだけで、evalや幾何演算は使わない。

## 修正の定義

`repair_tag` は現JSONLの来歴欄。台帳のbeforeスナップショットと現在DSLをJSON比較し、新規17・変更36・不変46に分類した。台帳の旧新hashと、現DSLのcanonical hashも照合した。タグの99を「99問のDSLが変更された」とは数えない。

`any_documented_dsl_change` の84問は、上の変更・新規53、現repoの既存ID間Git差分3、移行元のDSL本体差分33の和集合。移行元では `variables/construction/constraints/guards/answer` を比較し、source資料・メタデータ・post_processだけの変更や初回追加は修正と数えない。求値の変更は含める。いずれか1回の変更が分かる分類であり、全履歴の変更回数ではない。

`compression_followup39` は古い自由度圧縮の追試39登録のうち現行に残る38問。これを84問に加えた広めの証拠群は112問。追試リストだけでは全例の変更差分を確定できないので、84問と区別する。Falseを「一度も直されていない」と読み替えない。圧縮前DSLが保存されていないため、真の未修正対照群は作れない。

## pと統計

`jssa/difficulty/minima/basins-323.csv` のpは、`probe_basins.py` がsolver自身の探索箱から一様乱数で開始した単一局所探索のhit数／実施数。hitは残差・guard/hard条件・参照答のいずれかとの一致を満たすこと。複数答の集合完全一致や完成solverの最終証明成功とは別。solver本体は凍結版、seed=0、最大200開始点だが問題単位の時間上限がある。

開発群の `minima/raw-323/<ID>.json` からhit数と分母を再集計し、CSV全323行に一致することを検査した。封印された未使用群の生データではない。292問・55,097開始点、うち254問は200開始点、38問は3～198開始点で打切り。31問は変数0で試行なし。31問をp=1と補完しない。平均pは問題ごと等重みとし、試行を単純にプールしない。

差の区間は問題単位に群内で再標本化するpercentile bootstrap 10,000回、seed=2903。各問題内pの推定誤差・適応的打切りの影響を完全にモデル化した区間ではない。主解析は有限の開発群の記述で、母集団への確率標本ではない。

補助的にMann–Whitneyの漸近検定・順位効果をCSVへ保存した。多重比較補正なしの探索的値で、結論の確認検定には使わない。同値ばかりの群は検定値を空欄にする。`repair-adjusted-sensitivity.json` はpを目的変数に、修正フラグ、変数数カテゴリ、大会カテゴリを入れたOLSのHC3標準誤差。n=292、因果効果ではない。変数数自体が修正の結果にもなり得るため「調整すれば因果が分かる」とは扱わない。

整数条件のある未使用8問とない18問の1/40対84/90も事後の関連。整数条件を外した再実験・時間延長・正しい配置からの再開は本担当では実施していない。

## 再現

```bash
/home/kabatan/work/solver/.venv/bin/python \
  jssa/difficulty/unseen-1983/failure-audit/c/analyze.py
```

NumPy 2.5.1、SciPy 1.18.0、Python 3.12環境で実行した。別環境ではNumPy/SciPyのあるPythonを使う。移行元Gitは既存の `/home/kabatan/work/solver-experiment`、固定commit `7b6691be8d8a15a7a95816b532cad06cc2819112`。必要なら環境変数 `Q29C_UPSTREAM` で同オブジェクトを持つrepoを指定する。外部repoへの書込みはしない。

証拠文書・台帳の小さいコピーを `evidence/` に保存した。全入力のhashと固定commit、再集計時のassertion結果を `input-manifest.json` に保存。各出力は5,000,000 bytes未満の制限をかけて書く。原資料・採点ファイルは変更しない。
