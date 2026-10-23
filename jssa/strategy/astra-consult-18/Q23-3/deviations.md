# 実装・集計上の記録

- preregistration.md・pilot.py・manifest.jsonをfreezeでハッシュ固定してから、runを一度だけ実行した。144処理を228.846秒で完了。最適化の追加実行はない。
- 1処理（AIME-2014-II-03, k=7, endpoint/native）は時間上限にかかった。first_chart側では採用されたが、chartラッパーは両方とも0回呼ばれており、介入効果と解釈しない。
- pilot.pyの集計はH2対象を「main_idsに属するnative終点」としたため、同じ問題のH3だけの2候補を分母に足して50と表示した。予定された対応比較は48件。元summary.jsonとコードを保持し、verify.pyでmanifestのH1/H2対象を使って48へ訂正した。判定と0件という件数は不変。探索・選定・閾値は変更していない。
- 独立検算の最初の実行は、HPモード内のmp.mpf(float)を禁止するソースの型ガードで停止した。verify.pyだけを修正し、float.as_integer_ratio()による有理数として入力して再評価した。局所探索は呼んでいない。H3の26入力すべてが80桁の再評価でも事前条件を満たした。
- pilotのinitial欄はrepr(float)からの十進表現で記録した。refinerへはFloatCandidateのfloatを渡すため、独立検算では実際のbinary floatの値を有理数として再評価した。H3の分類は全26件で一致した。
- 公式解は問題の選定・事後採点に用いた既知の開発実験である。refinerとassemblerへは渡していない。独立した未知問題検証・数学的証明・完成solverの全値回収性能の測定ではない。
