# 数値SFT追試の実装可能性監査

現状は、固定済みの7構図×8例に対する正対応／shuffle対照のCPU preflightまで完了。7構図の追加非相似例を座標から作る部品はあるが、64例を学習用に出す設定、同じGeoSolverを教師として呼ぶ経路、12 holdout全件の非相似builderはない。したがって次はmatch/shuffleを複数学習seedで再現し、その結果が残れば2〜3構図に限定して新しいgivensと別queryを監査するのが現実的。

## 既存データと非相似数値

第三案の [`numeric_cases.py`](../program-self-training-2026-09-26/numeric_cases.py) は `H01,H04,H07,H13,H14,H15,DA01,DA05` の8構図に座標sampler、構成点builder、分岐・非退化検査、givens/答えを点から測る関数を持つ。正規化した辺比などのsignatureを保存し、一構図内で既存例と相似な候補を除外する。実学習データ [`train-numeric.json`](../../../qwen/.runtime/program_self_training_20260926/selection/train-numeric.json) はH14を除く7構図×8例＝56行で、各構図の4 visible＋4 repairを使う。

このため、**座標oracleなら**現行7構図すべてで非相似givensをさらに生成できる。静的benchmark variantsだけを見るとDA01/DA05は相似variantのみだが、generatorのDA01は辺長と角度を、DA05は三角形形状を変えている。7×64も原理上可能。ただし現在のsplitは `visible=4, repair=4, selection=24, final=24` に固定され、public学習出力は一構図8例である。64例/構図にするには訓練数を設定可能にし、private selection/finalを独立seed・独立shapeで確保し、validator・public export・dataset hash/tokenization receiptも更新する必要がある。

重要な制約として、このgeneratorは正解をGeoSolverから得ていない。各問題を座標上に構成し、対象の長さ・面積を直接測るCPU oracleでラベルを作る。既存資料もこの第三案をsolver生成データとは扱っていない（[`DATA_AUDIT.md`](../program-self-training-2026-09-26/DATA_AUDIT.md)、benchmark [`README.md`](../../../benchmarks/humpty_configurations_v2/README.md)）。「同じsolver数値教師」を通す実験なら、新問題をsolver入力へ変換して未変更solverを呼ぶadapterが必要で、その出力を座標oracleで独立照合する。現在その接続は見当たらず、solver DSLへの各構図の符号化可能性も未検証。既存56行を座標oracle由来のまま、新しいsolver由来ラベルと混ぜると教師経路が交絡するため、比較する全armで同一labelerを使うこと。

benchmark [`training_variants.jsonl`](../../../benchmarks/humpty_configurations_v2/training_variants.jsonl) は37構図に各v0〜v3を持つが、非相似 `shape` と分類された構図は9つ（H01/H02/H03/H04/H07/H13/H14/H15/HX01）。12 holdoutのうちshape variantがあるのはH02/H03の2つだけで、残る10（H08/DA03/DA06/DA15/H12/DA07/DA11/DB01/DB08/DB16）はv1〜v3が相似倍率変更のみ。これは未知のgivensへの改善を見る材料にはなるが、非相似汎化やきれいな値への暗記排除とは呼べない。さらに `shape` は生成分類であって、variant全組の相互非相似性を保証しないと [`DATA_AUDIT.md`](../answer-opd-pilot-2026-09-26/DATA_AUDIT.md) が注意している。

12 holdoutは [`prepare_transfer_eval.py`](../transfer-reanalysis-2026-09-26/prepare_transfer_eval.py) がv0のgivensを選び、各構図一つの問題を2推論seedで作ったもの。H02/H03の静的shape値を使う選択肢はあるが、独立した新しい確認集合として強く主張するには、それらだけを再利用せず、新しいparameter seed・重複signature監査・凍結前のlabel監査が必要。全12構図のbuilderを今すぐ作る必要はない。case監査で選ぶ2〜3構図を先に実装し、残りを相似variantで補って非相似セットと数えないのが最小案。

## query・構図・分割の追加差分

現在のgeneratorは一構図につき一つの英語numeric prompt（`NUMERIC_EN`）と一つの測定target（`_values_from_points`）を前提にしている。別queryを追加するには、query文、点を使った答え測定、solverへの入力、分岐と一意性の監査、private keyを同時に追加する必要がある。既存promptへ補助関係や答えを足さず、問題の数値条件だけを変える初段と、別の求値queryを試す次段を分ける。

既存transferの単位はconfiguration IDであり、theorem-family heldoutではない。catalogueの粗い `legacy_structural_group` metadataでは、学習H15と評価H08、学習DA01/DA05と評価DA03/DA06のgroup名が重複する。これはmetadata重複の記録で、数学的に同一の定理系列と断定する根拠ではない。2026-09-25の [`EXPERIMENT_LOG.md`](../qwen35-external-teacher-2026-09-25/EXPERIMENT_LOG.md) はH08をH07からのtangent-circle/reflection近接転移、H15を別のthree-reflection midpoint lemmaによる独立探索例として区別している。関係再利用を調べるならfamily重複を許容し、結論を「関連構図内の数値転移」に限る。真のtheorem-family heldoutを主張する研究では、variantをまとめて、原典・実式・構成graphを専門レビューしたfamily単位でsplitを事前固定し、train/testの重複を監査する。既存group名だけで独立した定理族とは判定しない。

## seed・shuffle・data scale

[`NEXT_EXPERIMENT_CPU_CHECK.json`](../transfer-reanalysis-2026-09-26/NEXT_EXPERIMENT_CPU_CHECK.json) が通したのはseed `2026092801` のmatch/shuffle各一arm。trainer CPU checkと両32/128 preflightはpassしたが、実GPUで作る32-update checkpointからのadapter/optimizer再開検査は未実施。shuffleは同じsource内で56 target全てを別値にし、target multisetを保つ。unique target tokensは両方1,056、128-update/512提示のplanned target tokensは9,655対9,656（1 token差）で、厳密なtotal-token matchではない。

追加学習seedはconfigを複製すれば変えられ、既存trainerの32-update＋continuationで128更新を作れる。3 seed×2 arm＝6 adapterは実装上の小変更で済むが、各seedでmatch/shuffleを対にし、全6 config・dataset・checkpoint hashを凍結して実GPUのresume receiptを確認する。既存receiptの32更新約58秒＋32→128 continuation約151秒/armを使うと、6 adapterの学習自体は約21分の見積り。seed違いの学習再現は、同じ12構図での2推論seedとは別の単位として報告する。

7×8対7×64のscale比較は、その次に正対応データだけで一軸変更として実施できる。総提示数を固定する128更新なら、56例は平均約9.1巡、448例は約1.1巡となる。これは「unique non-similar conditionsを増やし、更新予算を保つ」比較であり、例当たり反復回数も変わることを明記する。全例当たりの反復回数を合わせるため更新数を8倍にすると、data sizeと最適化computeが同時に変わる。どちらを測るかを先に選び、学習更新数・提示例数・assistant target tokensを別々に記録する。

## blind評価と費用

[`generate_batch.py`](../transfer-reanalysis-2026-09-26/generate_batch.py) は任意のjob JSONとadapterを受け、answer keyをモデルに渡さない。新しい12構図×2推論seedなら24 job形式を保てる。2〜3構図だけの段階では件数・source IDの前提が合わないため、小さな汎用scorer/joinerを用意する。既存 [`score_numeric.py`](../transfer-reanalysis-2026-09-26/score_numeric.py) は24 job・12 source・2 seedに固定、[`run_evaluations.py`](../transfer-reanalysis-2026-09-26/run_evaluations.py) は4条件を固定しており、複数training seedにもそのまま使えない。数値の主採点は自動exact-answer parserを使い、答案を匿名にしてから条件名を伏せた導出確認を副指標で行える。既存 [`prepare_blind_numeric.py`](../transfer-reanalysis-2026-09-26/prepare_blind_numeric.py) は条件対応をprivate keyへ分ける一方、grader packetには `construction_id` を含めるため、armは隠れるが構図IDは隠れない。

評価生成が学習よりはるかに重い。直近receiptでは4条件×24 jobの32k生成と、7 capped job×4条件の81k再生成、合計124生成jobに13,806秒（約3時間50分）を要した。同じ速度で300出力を単純換算しても約9.3 GPU時間で、長い回答・cap再生成の分散はさらに乗る。300+ outputを安価な確認と呼べない。既存draftの2-arm 3-seed評価見積りは約7.5〜10.5 GPU時間（2-armで2.5〜3.5時間という一seed見積りを3倍した概算）。新しい12数値条件をbase＋3 matched＋3 shuffledで24 job/condition評価する段階は、同じdraftの3条件見積りを条件数に合わせて約6〜8時間程度へ伸ばす。これは出力長に左右される未実測の予算枠であり、上限到達時の追加費用を含めて余裕を置く。

## 未実測の作業量見立てと最小順序

以下はコード差分の範囲からの人日見積りで、未実測。solver入力への変換が既に可能かで大きく変わる。

- まず現在の56例について3-seed match/shuffleを凍結・実行する準備は約0.5〜1人日。GPU生成評価の待ち時間とreviewは別。
- 既存7構図で64非相似例/構図を出すcounts/split/export/hash対応は約1〜2人日。全比較armのラベルを同じsolverに通すadapterと独立label auditは、対応DSLの有無を調べた後で別見積り。新しいsolver能力を作る作業とは切り分ける。
- 2〜3 holdout構図にsampler・builder・branch/domain検査・solver照合・別queryを追加するのは約3〜6人日。座標式は既存 `geo_primitives.py` を再利用できるが、各問の構成と分岐は個別実装が必要。12全構図を同水準で新規非相似化するのは概ね2〜4週間の作業見立て。
- 8〜12の新しい構図まで作るのは、構図の数学的採用・solver表現・非退化証明とsolver/oracle照合が加わるためstretch。今回の小さな汎化確認の必須条件にしない。

したがって直近の最小作業は、(1)既存56例・同一trainerで3-seed match/shuffle、(2)改善が残る場合に2〜3構図の新非相似 givens と一つの別queryをbuilder化し、solver正解と直接構成oracleを照合、(3)問題・seed・answer keyを生成前にfreezeし、base/各seedのmatched/shuffleを同条件で盲検評価、の順。次に成立条件を少し変えたケースで関係の再利用範囲を調べ、その後で7×8対7×64または同じ総例数で構図数を増やす比較へ進む。人間はsplit metadataと採点基準を決めても、モデル入力へ法則や証明は加えない。
