**指定背景の確認と利用**

- `codex-tasks-1023.md`末尾の方針転換、Q20、追加基準、Q21と`codex-session-01a1171a-summary.md`：自明な現象の再発見、既知の代替手段で終わる提案、solverのついで利用を除く判定に使用した。
- `gpt-pro-consult-16-answer.md`、`gpt-pro-consult-17-answer.md`：局所探索の成功率と完成solverを混同しないこと、既知技術の実装・実験量を新規性に換算しないこと、数値解の存在と全解・答えの保証の区別を採用。
- `report-draft-v10.md`、`supplement-v10.md`：完成solverの既定入口はNOMAD、局所LMは別段、入力の作図で自由変数が減ること、既存の人間難度の対応、GMB/msolveとの目的の差を確認。
- `astra-consult-17/G,H,I,J,K,L/answer.md`：Gの実装依存の境界現象、Hの実自由度と複素次元の区別、Iの方策選択の不成立、Jの依存深さと相関だけの弱さ、Kの代替法批判、Lの通常探索・直接消去双方への優位なし、を確認した。これらの追加追試は行っていない。
- Q6、Q7、Q8、Q9、Q10、Q12は指定先の`answer.md`を確認。箱外／別解／退化を同一視しないこと、既知理論との差、数値到達と証明の区別、事前登録基準を結果に合わせないことを反映した。
- Q3、Q4、Q5、Q11は`astra-consult-17/Q*/answer.md`に無い。依頼文の実際の出力先を辿り、Q3は`difficulty/wall-diagnostic/answer.md`、Q4は`difficulty/multiplicity/answer.md`とQ12のsnapshot、Q11は`difficulty/certify-all/answer.md`を確認した。Q5の`difficulty/full-solver-nohard/`は作業ツリーに無く、成果は未確認。
- `minima/basins-323.csv`、`ghost-1023/human_feat.csv`、`benchmarks/cases.jsonl`、`minima/raw-323`のfirst_hitを読み取り、探索を追加せず再集計した。Q19のsealed、未使用54問の結果は開いていない。

**自動生成88入力の仕組み**

現在の作業ツリーには`benchmarks/generated-88/`が無いが、取得済みGitオブジェクト`23ef40a`には存在した。fetchやcheckoutをせず、`git show`でREADME、freeze、cases、derivationsを読んだ。READMEとfreezeの写し、その他のハッシュ・件数は[generated88-audit.json](generated88-audit.json)に保存した。

これは**11構造族×4パラメータ×2等価表現**であり、ランダム作図300問のような母集団ではない。11族は、対称三次式、双曲線、楕円、放物線と円、平方和の特異解、符号付きノルム、接線と円、直角三角形の内接円、周期的目標、有理式の禁止点、向き付き相似の目標。derivationsには例えば三次方程式の根の置換、楕円の二つの符号、平方和=0などで答え集合を確定する導出がある。88問を独立な問題族と数えてはならない。

READMEは取り込み時点では未求解と記している。本文v10の264/264はそれより後の計測かもしれないが、この参照だけでは独立に再検証できない。元生成スクリプトはREADMEが別のexperiment archiveを指しており、取得済み参照には見つからなかった。**元スクリプトそのものと264/264の生ログは未確認**。今回の300入力は88入力の再利用・追試ではなく、別の事前固定生成器である。
