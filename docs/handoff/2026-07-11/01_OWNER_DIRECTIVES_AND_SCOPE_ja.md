# オーナー方針と scope

この文書は、これまでの対話でオーナーが明示した方針、とくに過去 plan への修正要求を失わないための正本である。後続の algorithm card、設計変更、release 判定は、必ず下表の ID を参照する。

## 変更しない判断基準

| ID | オーナーが明示した方針 | 実装・実験への拘束 | 典型的なドリフト |
|---|---|---|---|
| OD-01 | 性能を最優先する。研究価値は持たせてもよいが従である。 | primary は fixed-budget all-target 成功、安全性、oracle work、end-to-end time。論文上きれいでも遅い機構は採用しない。 | 証明や infrastructure の完成を性能実験より先にする。 |
| OD-02 | 幾何を連立方程式化すると変数が非常に多くなり、RUR/Gröbner 等の全面 exact solver は現実的な main route になりにくい。 | RUR/Gröbner は小さい capability-specific backend、truth 作成、局所 certificate、比較 control に限定する。 | 全 DSL を polynomial system へ落としてから解く設計へ戻る。 |
| OD-03 | 制限時間内に「できるだけ高い確率で」すべての正しい答えを得ることを中心目標にする。 | anytime budget curve、distinct-target recall、production `P_full_validated` / exact-eligible `P_full_exact` を測る。有限探索終了は `unknown`/`budget_exhausted`。 | 一解の高速発見、平均 residual、best seed だけを最適化する。 |
| OD-04 | 現在の数理最適化 base solver を生かして改善する。単なる既存 algorithm の寄せ集めにしない。 | 現 LM-QR、proposal/search/archive、validation を control とし、機構を一つずつ差し替える。survivor は一つの coherent production path へ統合する。 | 新 library の wrapper 集、別 solver loop、問題ごとの algorithm switch の山を作る。 |
| OD-05 | algorithm を最初に固定せず、先行研究と実験を使い、適宜相談しながら決める。 | roadmap は仮説 queue と decision gate を固定し、最終 algorithm 名は固定しない。大きな irreversible choice は比較結果とともにオーナーへ提示する。 | plan 作成時の好みを既定路線として実装する。 |
| OD-06 | black-box `f` により、座標多項式化しにくい幾何対象を簡単に追加できることが solver の強みである。 | open-world plugin ABI、typed construction graph、C0/C1/C2 capabilities、plugin-private object、guard/branch semantics を維持する。candidate は oracle callback のみを要求する。 | polynomial lowering、既知 primitive の closed set、AD 必須、特定 geometry DSL への hard-code。 |
| OD-07 | 多くの未知の幾何問題へ汎用的・安定的に適用できる solver 完成まで進めたい。 | parameterized family、未知 composition、未知 family、未知 plugin の段階 holdout を持つ。case/family ID routing を禁止する。 | 代表 9 case や既知 50 問への過適合を完成と呼ぶ。 |
| OD-08 | 複数解があっても、安定してすべての答えを求めたい。 | distinct target と configuration を分け、close-root、target collision、duplicate work を必須 counterexample にする。independent full-support 保険 lane を starvation させない。 | 既知解近傍を hard suppress し、近い別解を消す。 |
| OD-09 | 正しい値を求めたい。exact solver の全面利用は困難でも、誤答は避ける。 | discovery、canonical replay、numerical validation、validated/exact assurance を分離する。候補不明は棄却でなく `unknown`。正確性を residual 一個から推論しない。 | 小 residual、library success、BigFloat point replay を根の存在や exactness と同一視する。 |
| OD-10 | 実装バグを直し、機能性が高く、冗長性を排し、保守性に優れた洗練された構造にする。 | 既存 seam で研究し、勝った機構だけ production に統合する。使わない knob、route、dependency、重複 validator を削除する。 | experiment ごとに恒久的な branch、config、event type、solver copy を足す。 |
| OD-11 | branch が多すぎる状態をやめ、`main` 一本を正本にしたい。 | long-lived branch は `main` のみ。短命 isolation branch を使った場合は commit を小さく統合し、tag/decision を残して branch を削除する。 | 過去 branch を復活、archive tag を wholesale merge、未統合 branch を蓄積。 |
| OD-12 | 言語変更、refactor、bug fix、algorithm 改善、その他の改善を比較対象にできるが、根拠を持って選ぶ。 | Julia compiler/profile 後に language rewrite を判断する。refactor は measured change の周囲だけ。 | Rust rewrite や全体再設計を測定前に開始する。 |
| OD-13 | solver 完成まで使える詳細 plan とし、途中で計画の良い要素が消えないようにする。 | 本文書の ID、milestone exit、experiment decision、completion matrix を commit ごとに追跡する。plan 更新では削除理由を明示する。 | 新 plan が前 plan の重要要件を黙って削除する。 |
| OD-14 | subagent と Git を積極的に使い、token/time 効率を上げる。環境構築も必要なら実施してよい。 | literature、implementation、independent review を並行化する。ただし同じ file の同時編集を避け、clean commit 単位で統合する。 | subagent 管理のためだけの恒久 infrastructure を作る。 |
| OD-15 | 整合性 infrastructure を大規模化し、本質の solver algorithm 実装・実験ができなくなるのは本末転倒である。 | algorithm experiment に必要な最小 control だけ追加する。formal host isolation は finalist の promotion 時まで延期する。 | 新 schema、authority、receipt、sandbox protocol を通常の候補比較ごとに増築する。 |
| OD-16 | 先行研究を広く調べ、実験で現在実装の bug と algorithm 改善を検討する。 | 新 algorithm family は一次資料の仮定と破綻条件を記録し、現 baseline と同予算で比較する。 | 出典なしの直観、blog benchmark、既存 method 名だけで採用する。 |
| OD-17 | Theory 検討は今回の数値 solver 改善では無視してよい。 | 添付 v2 の exact/theory 部分は main roadmap に入れない。数値 compiler/lifted view 等も実測で必要になった場合だけ候補にする。 | target algebra theory を completion の依存関係に戻す。 |

## 目的関数の優先順位

候補の選択は次の辞書式順序で行う。

1. **安全性:** accepted false target、invalid semantics、truth leak、budget 違反を許さない。
2. **全 target 回収:** product では declared budget 内の `P_full_validated` / exact-eligible `P_full_exact`、local lab では明示した assessor proxy と distinct-target recall を最大化する。
3. **anytime 性能:** 小さい prefix から成功し、未解決 case を含む fixed-budget work を下げる。
4. **一般性:** 未知 parameter/composition/family/plugin でも性能を維持する。
5. **簡潔性:** 同等性能なら code path、knob、dependency、special routing が少ないものを選ぶ。
6. **研究価値:** 上記を損なわない範囲で、新規な mechanism や分析を選ぶ。

単一 scalar score に safety と recall と speed を混ぜない。安全性を平均性能で相殺してはならない。

## exactness の解釈

OD-02、OD-03、OD-09 は矛盾させない。

- discovery の main route は数値最適化である。
- numerical candidate は canonical oracle で独立 replay する。
- capability があれば validated box / local root certificate を追加できる。
- algebraic identity が得られる限定問題では `ExactAnswer` を作れる。
- 一般 black-box plugin で algebraic exactness や有限時間 all-root proof を要求しない。
- assurance capability がない場合も solver を使えるが、保証 level と `unknown` を正直に返す。

したがって「正しい答えを目指す」は、全面 RUR を意味しない。誤った target を黙って exact と呼ばないこと、可能な assurance を独立に付けること、未発見 target の有限非存在を主張しないことを意味する。

## DSL compatibility gate

すべての algorithm candidate は以下を満たす。

- `f(x)`、bounds、scales、公開 capability 以外を必要としない。
- plugin-private type や operation 名を routing feature にしない。
- C0 black-box は有限差分 route で動ける。
- C1/C2/C3V は optional acceleration / assurance であり、DSL の必須条件にしない。
- domain、guard、branch、selector は penalty の一部ではなく canonical semantics として残す。
- production acceptance は変形 residual でなく undeformed canonical problem に対して行う。
- `ProblemSpecV1` と Python `ProblemBuilder` の表現可能範囲を狭めない。

未知 plugin smoke を通らない candidate は、analytic benchmark で速くても general champion ではない。

## 計画変更の手順

plan を変更するときは、decision record に次を一段落ずつ書く。

1. どの OD-ID を維持するか。
2. 変更を要求した実測 failure は何か。
3. 置き換える仮説と、残す control は何か。
4. 削除または延期する要素は何か。その良さをどこへ保存したか。
5. オーナー判断が必要な不可逆変更か。

次はオーナー相談を必須とする。

- public result semantics、DSL/plugin ABI、target distinctness の意味を変える。
- main language を変える、または大規模 rewrite を始める。
- independent full-support insurance lane を削る。
- exact solver を main route にする。
- completion envelope や safety gate を緩める。
- 既存 negative result の reopen gate を満たさず同じ mechanism を再実行する。
