# AP01 数値経験から元の証明への転移：小規模実行計画

2026-09-28。モデル出力を見る前に固定する。先行提案の全3題・4条件ではなく、ユーザーと合意した1題・2条件の予備実験。

- 問題：`benchmarks/humpty_proof_evaluation_v2/problems_only.md` の AP01。選定理由は既存の DA15 の前提DSLを流用できること。学習には外心Oも、証明目標の共円性も追加しない。
- 目的：証明を教師にせず、前提から自動生成した数値教材で**同じ問題の一般証明**が改善するか。未知構図への汎化を測ったとは主張しない。
- 一度の手作業：前提をDSL化し、対応する英語前提文を固定する。その後の形状、query、solverラベル、JSON書き出しはプログラムで生成する。自然言語からの全自動形式化とはしない。
- データ：seed 2026092801、整数三辺5..40の鋭角不等辺三角形を棄却抽出。ソートした三辺の最大辺に対する比が重複する相似形も除外する。前提の半直線とFの厳密な内部条件をsolverに課す。結論をフィルタに使わない。
- 問い合わせ規則：前提の既存点のうち、少なくとも一方が `IntersectLines` で構成された点である全点対（21組）から、各形状で一様に4組を選ぶ。目標点や既知の補題による優先付けはしない。64形状×4問=256組、教師は小数点以下6桁の数値だけ。中間式、座標、証明、定理名は教師に入れない。
- 診断：別の8非相似形状で1問ずつ、学習集合の最初の4形状の最初のqueryを4問。未見8問と既見4問を分ける。問題数が少ない診断であり、数値汎化の精密な推定とはしない。
- モデル：既存の Qwen3.5-9B の固定revision。baseと新規数値SFTを比較する。LoRA r8/alpha16/dropout0、lr5e-6、勾配累積4、128更新（256教材を2巡）。32更新で中断保存し既存の検証済み継続処理で128へ。証明成績によるcheckpoint選択なし、既存adapterの持越しなし。
- 評価：両条件に同じAP01証明promptを8 sampling seedsで与える。数値診断12問も同一prompt/seed。生成は既存実装、temperature .7、top_p .95、top_k20、presence_penalty .2、thinking false、batch4。
- 長さ：32,768 tokens / context40,960。片方でもlength終了したjobは**両条件とも**同じseedで81,920 / 98,304へ延長再生成する。最終的な打切りは別記し、無効な証明と同一視しない。延長前の結果も残す。
- 証明採点：条件名を伏せた全文をレビュー。全域で有効な自己完結した論証だけ完全正答。対象の特殊定理の名前を引用するだけ、数値例、核心の式を根拠なく置くものは不合格。通常の座標展開や基本定理は可。必要に応じ式変形を独立計算で検査する。
- 数値採点：明示した最終回答を抽出し、絶対誤差<=1e-4または相対誤差<=1e-5。曖昧な回答抽出と打切りは別記。デコード全数値から正解を探さない。
- 判断：数値習得と完全証明を別々に評価。数値が改善しなければ「このSFT設定で数値経験を習得できていない」、数値改善のみなら「証明への移行は未実証」。証明が増えても1問題・1学習seed・各8試行の探索的信号とする。追加seed、他問題教材対照、同GPU予算のbase、多問題再現を済ませるまでは原因・汎用性・新規性の確証とはしない。
- 変更が必要になった場合は旧記録を残し、変更理由と時点を追記する。元のsolverと既存研究ファイルを改変しない。

## 固定した証明prompt

Prove the following statement for every nondegenerate configuration satisfying the assumptions. Give a self-contained proof and justify the ordering, branch, and sign conditions that the argument uses. Do not substitute a numerical example for a proof. A named theorem specific to this configuration, or a statement equivalent to the requested conclusion, must be justified rather than merely cited. Write the proof in English.

Let ABC be an acute scalene triangle. Let M, N, and P be the midpoints of BC, CA, and AB, respectively. The perpendicular bisectors of AB and AC meet the ray AM at D and E, respectively. The lines BD and CE meet at F, which lies strictly inside triangle ABC. Prove that A, N, F, and P are concyclic.
