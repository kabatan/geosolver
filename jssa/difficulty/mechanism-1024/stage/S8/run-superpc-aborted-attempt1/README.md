# 中断・結果に数えない：attempt 1

2026-10-24T07:21Z開始の旧試行。ユーザーの明示指示により試行全体を中断扱いで保存し、新規試行とは一切合算しない。削除・採点・再利用なし。旧rawは `/tmp/mechanism-S8-superpc-raw-m2abkwva` にそのまま保持。

現存証拠は start 19件、end 11件、rawディレクトリ19個（申告の30枠とは不一致）。end全11件はcompleted/exit 0、wall 2.995〜4.557秒。resource_violationsは全22件がenvironmentであり、GEOSOLVER_MEMORY_LIMIT_BYTESおよびGEOSOLVER_SYMBOLIC_PARENTをsolver自身が子へ追加することに起因する監視側の誤検出。8スイッチ・内部thread設定・CPU固定の差異ではない。保存されたresultはsolver status=solvedを含み、短時間だけを事故の証拠にはできない。ログ末尾には optional Linux address-space limit の警告があるが、quota/no spaceの記録は見つからない。

従って「全30枠がquota/資源超過で数秒終了」は現存ログからは立証できない。ユーザー報告では/tmp quota超過でdriver停止。試行全体が未完・監視不備であることと、ユーザーが最初からのやり直しを明示承認したことを理由に、全体を環境/ハーネス中断として扱う。solverの失敗・費用180秒として数えない。個別の資源超過や誤答を主張しない。

詳細、環境差分、末尾抜粋、全旧raw hashはincident-audit.json。元receipts/progress/measurement-freezeは変更していない。新試行開始後は再試行・別seed・問題追加除外をしない。
