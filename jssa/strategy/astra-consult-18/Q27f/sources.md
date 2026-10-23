# 文献確認とデータ出典

確認日：2026-10-23。以下は今回実際に検索し、一次資料本文または明記した範囲を確認したもの。文献の理論が今回のデータを説明したという意味ではない。

| 一次資料 | 確認箇所 | 使えること／使えないこと |
|---|---|---|
| Jonathan D. Hauenstein, Frank Sottile, [alphaCertified: certifying solutions to polynomial systems](https://franksottile.github.io/research/pdf/alphaCertified.pdf) | 著者公開原稿の表紙、導入、§1 Theorem 2・4。原稿表紙は7 September 2011 | 正方多項式系のNewton反復について、α<(13−3√17)/4なら近似零点、根までの距離≤2β。α<0.03なら半径1/(20γ)内で同じ根へ収束する十分条件。今回のLM/Powell/NOMADや不等式付きDSL全体の成功率を与える定理ではない。今回αは計算していない。刊行版の巻号は採用していない |
| Pablo A. Parrilo, [Semidefinite programming relaxations for semialgebraic problems](https://web.mit.edu/~a_a_a/Public/Publications/refs_for_seb_blog/Parrilo_MathProg.pdf) | 著者原稿、§4 Theorem 4.6、§5冒頭 | 等式・不等式・非零条件の実不可能性と代数的証明書、次数を制限した探索。有限予算で証明できる割合や、この323問の必要次数は与えない。書誌の刊行巻号は今回未確認なので記載しない |
| Jonathan D. Hauenstein, Charles W. Wampler, [Isosingular Sets and Deflation](https://academicweb.nd.edu/~cwample1/Preprints/hwIsosingular.pdf) | 著者公開原稿、表紙・要旨・導入。原稿日付June 23, 2011 | 微分によるdeflation、特異構造による分類が既存の理論であること。今回の38問の余剰成分の同定、実次元の証明、計算時間の予測としては使わない |
| msolve開発者、[How to solve multivariate polynomial systems with msolve?](https://msolve.proj.lip6.fr/downloads/msolve-tutorial.pdf) | §1、§3、§7 | 複素解集合の次元、有限複素解系からの実根計算、saturation/colon idealsを区別している。現在の文書であり、既存実験のmsolve 0.9.4の全機能を保証する資料ではない |

局所／大域の区別、零成功の二項上限、余分な成分を含む二次式の反例は、本回答中の初等的な導出で足りる。これらを上記文献の新定理や本研究の新規成果とは呼ばない。必要な深い理論の存在、必要な証明次数、solver固有の普遍的な規則はいずれも**未確認**。

## 数値の一次保存物

- `../../../difficulty/minima/raw-323/*.json`、`raw-323-seed1/*.json`：各323ファイル。全110,239終点を再集計した。ソースの`counts`とrecordsから数え直した分類は全件一致。
- `../../astra-consult-17/H/sources/comparison-cases.csv`：323問のmsolve分類と完成solverの3seed成績。出典は同ディレクトリ`provenance.json`。保存CSV末尾の改行を1個除いたGit blob SHA-1は、記録された`2270f6bb7b6596e23c7ad0e9bfa37c0c5026d7b8`と一致する。元ブランチへfetch・checkoutしていない。
- `../../../results/mechanism-attribution/attribution.csv`、`../../../results/stage-profile-20261023/per-case.csv`：各969実行。問題×seedの重複なし。両者の正答ラベルと、比較CSVの問題別正答数が一致。
- `../../../difficulty/certify-all/per-case.csv`：開発323問＋2026年20問。完成solver返答原票を使っていない点は同所`summary.json`・`answer.md`に明示されている。
- `../../astra-consult-17/H/classification.csv`：正次元分類68問の形状・局所次元の診断。Hの`G`は局所的な形の変形の確認であり、全実成分で求値が一定という証明ではない。Q10のJMO-2014-PRE-09の反例も参照した。

計算で読んだファイルのサイズとSHA-256は[sources.json](sources.json)。再集計コードは[analyze.py](analyze.py)、固定予測は[preregistration.md](preregistration.md)、固定時刻・ハッシュは[registration-lock.json](registration-lock.json)。

## 横断探索の範囲と欠測

| データ群 | 今回の扱い |
|---|---|
| minima/basins-323、raw-323、raw-323-seed1 | 表の定義と全原票を確認し、個票を再集計 |
| ghost-1023、ghost-exact、ghost-intervention、ghost-pairs-match、false-attractors | 既存の集計・診断定義・介入の採否を確認。全点の幾何再評価はしない |
| multiplicity、wall-diagnostic、wall-292、nomad-wall、role-reassign | 既存の効果・適用範囲・欠測・完成solverへの移行結果を確認。軌道ログを全走査したわけではない |
| holdout-1023、near-start-1023、zg-1023、common-start、new2026-predict、transform-check、start-feasibility-1023 | ファイル所在を一覧化し、主な表・登録・既報の採否をスクリーニング。holdout43問と2026年20問の表も読み込んだ |
| full-solver-redraw / cloud | ローカルはsmokeと未実行の説明。cloudには現在146問の表があり、plain417/438、redraw418/438。150問全体の完走結果とは呼ばない。11/146問しかLM到達がない。Iの古い「表がない」という記述を現在の状態に流用しない |
| benchmarks/extra-variables | manifestの15原問・60入力を確認。`basins-extra60.csv`・`raw-extra60`は現checkoutにない。元60入力のdose-response全原票は未確認。代わりに別の43問の表を読んだことを、60入力の追試とは呼ばない |
| benchmarks/gmb_comparison、results/gmb-success-definition | 比較範囲と成功定義、4条件の保存集計を確認。IMO39の比較であり323問の同一集合ではない |
| astra-consult-17 / 18 | 指定のanswer.md群を確認。Q20/Q21の12本の棄却理由を点検。Q23の3回答は参照時点では暫定稿だった |

「全データから探索」は、利用可能なデータ群を横断して候補を選び、主要な対照を全数再集計したという意味である。数GBの全ログの全行を精読したという意味ではない。封印tar、unseen-1983のsolver結果は参照しなかった。
