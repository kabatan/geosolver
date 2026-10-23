# Q7 検索範囲と未確認事項

調査日：2026-10-23。成果は[answer.md](answer.md)、書誌・本文確認箇所は[sources.md](sources.md)。目的はQ1の新規性を判定するための対象を絞った一次資料調査であり、全データベースを網羅するsystematic reviewではない。

## 調査対象と方法

最初に追加5・Q7、Gの報告、Q1の計画を読んで暫定判断と縮小基準をanswer.mdへ保存した。次に一般的な制約処理から幾何固有の扱いまでを検索し、論文本文、著者公開稿、出版社・機関の書誌、公式ソフトウェア文書へ進んだ。検索結果の断片だけで技術的な結論を採用せず、読めた箇所を文献一覧に記した。

主な検索語は以下の組合せである（表記を整理して記載）。

| 範囲 | 主な検索語 | 採用した一次資料 |
|---|---|---|
| 制約を守る／一時的に緩める | `Audet Dennis progressive barrier mesh adaptive direct search`、`extreme barrier feasible infeasible starts` | R1、R2 |
| 拒否・段差・LM | `Levenberg-Marquardt discontinuous penalty`、`constant residual Levenberg`、`Ceres inequality constraints premature convergence` | R3、R4、R4b |
| 制約付き・非滑らかな最小二乗 | `constrained nonlinear least squares Levenberg convex constraints`、`nonsmooth regularized least squares Levenberg Marquardt` | R5、R6 |
| CAD幾何制約 | `geometric constraint solving inequality numerical`、`geometric constraint solving basin of attraction`、`geometric constraint disconnected`、`geometric constraint solving discontinuous penalty`、`geometric constraint homotopy degenerate` | R7、U1 |
| 動的幾何・枝・特異点 | `dynamic geometry complex detours`、`Generation real algebraic loci complex detours` | R8、R9 |
| 競技幾何の自動作図 | `Automatically Building Diagrams Olympiad` | R10 |
| 数値代数幾何・実解・不等式 | `numerical algebraic geometry inequalities real solutions complex homotopy`、`validating completeness real solution set inequalities` | R11、R12 |

周辺の候補についても書誌・アクセス可否を調べたが、本文や一次書誌を確認できない候補を、主張の根拠に増やしていない。確認できなかったページへのアクセス制限を回避する操作や、依存関係のインストールはしていない。

## 重要な未確認事項

- R1：2007年著者稿の本文は読めた。2009年出版版の書誌と対応は確認したが、決定的な動機の文章の逐語的一致は**未確認**。
- R3：公式サイトのHTML取得が安定しなかったため、同じ公式プロジェクトのversion 2.2.0のソースを確認資料とした。
- R4：公開MINPACKコードを読んだ。今回のSciPy nativeバイナリと対応Cソースの逐行同一性は**未確認**。Gが記録していない内部`fnorm`・`ratio`まで観測済みとはしていない。
- R7：出版社本文へのアクセスに制限があり、著者の大学サイトのPDFを読んだ。書誌は所属機関の記録と照合した。
- R6：arXivの版指定本文を確認。最終雑誌版の書誌は本調査では**未確認**。
- U1、U2：書誌は確認、必要な本文は**未確認**。詳細な先行結果を補っていない。
- 同じ競技幾何領域でB/N型介入・native試行・停止対照・未知入力予測を全て組み合わせた既報は、今回の検索では確認できなかった。**不存在や世界初の証明ではない。**

## 内部資料の扱い

- [Gの報告](../G/answer.md)：14問の介入、292問の旧終点調査、定数行・停止・差分の対照、AIMEのguard集合と入力予測の結果を読んだ。外部文献は本担当でも一次資料を確認した。本担当によるsolverの再実験ではない。
- [Q1事前登録](../../../difficulty/wall-292/preregistration.md)：B/N/G2、55,097開始点、P1–P5、M1、G2のfallbackと非滑らかさ、開発集合であることを確認した。
- [Q1のanswer.md](../../../difficulty/wall-292/answer.md)：読取時点の暫定報告を計画の背景として使った。本調査はQ1の進行中の結果を追跡・検証したものではない。
- [凍結実装](../../../../src/geosolver/engine/standard/search/scipy_multistart_backend.py)：hard行、倍率10、許容側margin項、非有限時の全行置換を読み、簡略化した数式との違いを明記した。

## 作業範囲

本担当の書込みはこのQ7ディレクトリ内のMarkdownのみ。solver実験、既存コードや他担当ファイルの変更、commit・pushは行っていない。図・PDF・大きなデータファイルの生成はしていない。
