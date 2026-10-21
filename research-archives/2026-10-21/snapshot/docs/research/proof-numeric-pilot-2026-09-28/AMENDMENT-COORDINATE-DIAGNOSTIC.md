# 事後の解法指定診断（主比較から分離）

2026-09-28。主実験の16証明は全件自然終了済み。匿名の最初の8件について独立レビューが全件を不完全と判定し、核心の共円性を固有補題・未証明の角等式などで飛ばす傾向を認めた時点で追加する。まだ条件対応を開示せず、数値診断も進行中。これは結果を見た後の補助診断であり、最初から固定した主仮説の追試と同列には集計しない。

目的は「このモデルに証明能力がない」「数値SFTが不可能」と早計に断定しないため、汎用的な解析幾何の解法指定への反応を確認すること。追加学習、教師の変更、正解の交点公式や証明の提示は行わない。

元のproof promptに以下のみ追加し、base/SFT各2回、seed 2026092850, 2026092851で比較する。生成器・sampling設定・batch4・32k上限と共通81k延長は主比較と同じ。途中に証明を生成して採否を選ばない。

> Use an analytic proof: choose coordinates or vectors, derive the defining equations for D, E, and F from the premises, and verify a circle equation or a concyclicity determinant. Carry out the algebra rather than citing a configuration-specific theorem. Do not use numerical examples.

この指定でbaseも解けるなら、元の評価での失敗には解法選択の問題が含まれる。SFTの効果を示したことにはならない。2回ずつの診断のみで頻度を精密推定せず、主実験16本と混ぜず報告する。追加4答案も匿名で採点する。
