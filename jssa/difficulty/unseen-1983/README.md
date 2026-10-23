# Q2補充 v3: AIME 1983〜1999（54候補・公式冊子未照合）

## 結論

**AIME 36問を追加し、保存済みHMMT February 18問と合わせて54問の候補DSLを作成した。**
原文→入力の対応カード、原文・入力hash、全255スロットの採否・理由を固定した。
24〜30問という希望数には達したが、「書けるもの全部」という指示を優先し、
30問で打ち切ったり、難度・成功率で間引いたりしていない。

AIMEの資料は **Hugging Faceの二次資料で、公式冊子との照合は未了**。
答え36件は入力・採否固定後に `official_answers.jsonl` へ
`secondary_answer` として転記し、全件を **「二次資料・未照合」** と明記した。
AIMEの `official_answer` は全件 `null`。ファイル名が公式照合を意味するものではない。
既存HMMT18問の入力・カード・答え行は保持した。

**solver・局所探索・数値的な配置生成・式の数値評価は一度も実行していない。**
最終の54問・2,239式はJSONモデル／DSL構文・ASTの静的検査に合格した。
既存343問（benchmarks 323問＋new2026 20問）、HMMT18問との静的照合の一致は0件。
公式冊子照合、幾何条件の独立した意味監査、実行可能性・目標値の一意性の検証は未了で、
`ready_for_main_validation` は `false` のままとした。

## 根拠

### 資料と先に固定した規則

提供資料は [source-evidence/aime-1983-1999/README.md](source-evidence/aime-1983-1999/README.md) と
同ディレクトリの `aime-1983-1999.jsonl`。224行、対象は1983〜1999年。
資料SHA-256は `5b29347ce7c807ab1ce23951577ca8530c2c10b18e52c9da8099e3e443779012`。
取得担当の記録では `gneubig/aime-1983-2024` のdatasets-server rows APIから取得し、
AoPS wikiへの直接アクセスは403だった。今回、ネットワーク取得・再照合は行っていない。

[authoring-rules.md](authoring-rules.md) をQuestion閲覧・DSL作成前に固定し、
そのhashと資料hashを `revisions/v3-selection-freeze.json` に記録した。
v2の作成原則1〜10を維持し、AIMEの次の判定を追加した。規則全文とhashはmanifestにもある。

- 年1983〜1999、各番号1〜15の昇順で全255スロットを監査する。
- 平面内の点・線・円・多角形・円錐曲線の配置や長さ・角度・面積・座標を主対象とするものを平面幾何とする。
  図形名だけの組合せ問題と、本質的な立体問題は対象外。判定の境界例もmanifestに注記した。
- 原文の有限配置を構成・等式・不等式・guardへ直接翻訳でき、原問の単一求値目標を保持できるものを全件採用する。
  既約分数の出力は整数分子分母とBezout証人で保持し、値を事前計算しない。
- 全配置での最適化、配置数・確率、未知回数の反復、軌跡・和集合・陰関数の領域面積、
  欠落図の必須情報、直接表せない平方因子なしの標準形条件は、具体的理由を固定して除外する。
- Answer・解説・solver結果・人間の難度・変数数・予想成功率を採否やDSLに使わない。

分類・生成コードはID／年／番号／Questionだけを使用する。
JSONの構文読込みは資料全体をパースするが、Answer欄へのアクセスは
入力hash固定・静的検査後の別スクリプト `seal_answers.py` にだけ分離した。
Question内のasyは接続・ラベル・内外・順序だけを参照し、描画用の座標を入力にしない。
1983-14のasyに含まれる補助円の数値も入力には使用していない。

### 255スロットの扱い

| 状態 | 件数 | 内容 |
|---|---:|---|
| DSL作成 | 36 | 平面幾何の直接求値として原目標を保持 |
| 幾何でない／対象外 | 159 | 代数・整数・数列・組合せ等138、立体等21 |
| 平面幾何だがDSL非対応 | 29 | 下記の具体的な不足・非対応理由 |
| データ欠落 | 31 | 提供224行に該当年・番号の行がなく、分野も未判定 |
| 合計 | 255 | 全17年×15番号 |

「データ欠落31」と「画像の必須情報がない入手済み問題」を区別した。
本文のある除外行にも原文hashを付け、DSLのない行の入力hashは `null` とした。
全行の本文は `statements.jsonl`、具体的な判定と理由は [manifest.json](manifest.json) にある。
HMMTの過去の監査428行と除外理由も保存版から保持した。

| DSL非対応の理由 | 件数 | 例 |
|---|---:|---|
| 欠落図・数値 | 5 | 1985-06は四つの面積がPNGにしかない。1987-06、1999-04は接続・ラベルが不足 |
| 配置・整数・個数の最適化 | 6 | 1990-03の最大辺数、1992-13の最大三角形面積 |
| 未知回数の反復／反射個数 | 2 | 1992-11の最小復帰回数、1994-14の反射数（図も欠落） |
| 配置数・確率 | 5 | 1989-02、1996-07、1997-02の個数、1995-03、1999-10の確率 |
| 陰関数・軌跡・和集合・写像領域の面積 | 7 | 1987-04、1992-10、1994-15、1995-01、1998-03、1999-06、1999-08 |
| 平方因子なしの標準形を保持できない | 3 | 1991-11、1995-14、1998-12。量そのものへ目標を差し替えない |
| 全弦に対する一意性条件 | 1 | 1983-15。唯一性を解法で有限配置へ置き換えない |

欠落スロットは次の31件。原文・答えを記憶で補っていない。

| 年 | 欠落番号 |
|---|---|
| 1984 | 15 |
| 1986 | 4 |
| 1987 | 13 |
| 1988 | 1, 4, 6, 11, 12 |
| 1989 | 3, 6, 10, 12, 14, 15 |
| 1990 | 4, 8, 12 |
| 1991 | 3, 6, 7, 15 |
| 1993 | 3 |
| 1994 | 3, 4, 5, 6, 7, 13 |
| 1995 | 7 |
| 1996 | 1 |
| 1997 | 13 |

### 作成したAIME 36問

IDは `AIME-年-ゼロ埋め2桁番号`。資料中のID・行番号もmanifestに残した。
各問の全構成・全条件・guard・目標の対応と座標固定の根拠は
[cards.md](cards.md) と `cards/<id>.md` にある。

| 年 | 採用番号 |
|---|---|
| 1983 | 4, 12, 14 |
| 1984 | 3, 6 |
| 1985 | 9, 11 |
| 1986 | 9, 15 |
| 1987 | 9 |
| 1988 | 7, 14 |
| 1989 | なし（入手済み9行を監査、他6スロット欠落） |
| 1990 | 7 |
| 1991 | 2, 12, 14 |
| 1992 | 9, 14 |
| 1993 | 2, 12, 13, 15 |
| 1994 | 2, 8, 10 |
| 1995 | 4, 9 |
| 1996 | 13, 15 |
| 1997 | 4, 7 |
| 1998 | 6 |
| 1999 | 2, 9, 12, 14 |

変数0の1991-02（335本の線分和）や1993-02（有限40日移動）も含む。
ここでの点は等分・移動の定義をDSL式として展開したものであり、
数値配置の探索・生成・評価で得た座標ではない。
1993-12も確率を求める問題ではなく、6回の実現ラベルと始点を未知変数で表した。
1999-02は切断片の合同対応を全てdisjunctionで残し、解いた切断線を入力へ追加していない。

### 静的検査と重複検査の範囲

[validation.json](validation.json) は54問・2,239式でエラー0。
JSONモデル、AST、関数名・引数・定義前参照、全条件のカード対応、
原文・DSL・生成コード・規則・保存版のSHA-256を検査した。
`validate()` の実行やDSL式のコンパイル後実行は行わず、
AST専用の `_expression_issues` を使用した。`geosolver.engine` がimportされていないことも確認した。

[duplicate-audit.json](duplicate-audit.json) の比較は次の通りで、すべて一致0件。

- 54候補対benchmarks 323問、54候補対new2026 20問。
- 新規AIME36問対保持HMMT18問、候補54問内の相互重複。
- 大小文字・番号・I/IIを正規化したID。
- IDを除いたDSLの一致、および変数名・構成名の一貫した改名／条件順を無視したAST指紋。
- asyを除いた本文の正規化一致（本文が入っている行だけ）。

既存323問のうち `problem_statement` を持つのは28問、new2026のcasesには0問。
したがって本文一致だけで343問の意味上の非重複を主張していない。
別名・翻訳・相似変換・別の定式化まで含めた数学的同値性は、この静的照合では証明できない。
solver結果・答えとの一致を重複判定の根拠にしていない。

### 版の保存と答えの分離

旧版は [revisions/v2-before-aime/README.md](revisions/v2-before-aime/README.md) 以下へ、
README・規則・manifest・生成／検査スクリプト・原文・DSL・カード・答え・検査記録の
48ファイルを変更前のbytesで保存した。`snapshot-sha256.json` で全ファイルを固定した。
既存 `revisions/v1-*` も変更していない。

v3初稿も `revisions/v3-draft-before-text-review/` に保存した。
答え転記前の本文再確認で1996-13の「線分ADがBCを二等分する」に必要な
`t >= 1` を追加したためである。旧新hashと理由は `revisions/changes-v3.json` に記録した。
この修正はsolver結果に基づくものではない。

最終入力・採否のhashを `revisions/v3-input-freeze.json` に保存し、静的検査の後にだけ
答えを転記した。[answer-provenance.json](answer-provenance.json) に、
答え転記前後でmanifest・DSL・原文・カード・規則・生成コードのhashが不変だった記録を残した。
HMMTの保存公式解答転記4件、公式未入手14件の従来状態も保持した。
これらの記録はローカルの工程・hash記録で、外部の時刻証明ではない。

### 成果物と再実行

| ファイル | 内容 |
|---|---|
| `dsl/`, `cases.jsonl` | AIME36＋HMMT18の答えを含まない入力 |
| `statements.jsonl` | AIME224＋過去HMMT428の本文・出所・hash |
| `cards.md`, `cards/` | 原文→全構成・条件・guard・目標の対応 |
| `manifest.json` | AIME255＋HMMT428の台帳、事前規則・hash・採否・理由 |
| `official_answers.jsonl` | AIME36件の二次資料答えと旧HMMT18行。入力とは分離 |
| `answer-provenance.json` | 答え転記と入力不変の記録 |
| `duplicate-audit.json`, `validation.json` | 静的重複・JSON／AST検査結果 |
| `build_cases.py`, `aime_definitions.py`, `aime_decisions.py` | Questionだけによる分類・入力生成 |
| `verify_static.py`, `seal_answers.py` | 静的検査、入力固定後の答え転記 |
| `revisions/` | v1、v2全保存、v3初稿、規則／入力固定記録、変更理由 |

`input_sha256` はDSLファイルの末尾LF込みUTF-8 bytes、
`statement_sha256` はQuestion文字列のUTF-8 bytesに対するSHA-256。
単なるJSONのキー順変更でも入力hashは変わる。

指定Pythonで、次の順に再生成・検査・分離転記できる。
旧HMMTは保存版から保持するため、旧版で参照したrepo外の資料を再読込する必要はない。

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/kabatan/work/solver/.venv/bin/python jssa/difficulty/unseen-1983/build_cases.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/kabatan/work/solver/.venv/bin/python jssa/difficulty/unseen-1983/verify_static.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/kabatan/work/solver/.venv/bin/python jssa/difficulty/unseen-1983/seal_answers.py
```

書込みは `jssa/difficulty/unseen-1983/` 内だけ。
Python環境変更、pip install、ネットワーク、git fetch、commit、pushは行っていない。
不足31スロットと必須図のある問題の補完、公式冊子照合、独立の意味監査が今後の課題である。
今回の候補入力をsolverの結果で選び直したり、答えに合わせて改変したりしていない。
