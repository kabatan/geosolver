# 106問とPC割り当ての固定

開発外34問は、stage/S1より前の `jssa/difficulty/capability-1024/preregistration-6.md` の「unseen-2/a（AIME 17問）とb（HMMT 17問）の固定済みDSL（Q30と同一）」に対応する。両群のcases.jsonlからIDとdsl_pathだけを列挙した。stage/S3の残差比較用12問を34問の代わりには使っていない。34問の既存一覧を特定できたため、代替選定はない。現在の各DSLと元一覧のsha256をassignment.jsonに保存した。

機構72問は `mechanism-1024/problem-set/problem-set.json` の hard48、fast_algebraic8、fast_search8、multivalued8をそのまま使用。72問すべての入力hashは7bのpre-run-hashes.jsonに記録されたhashと一致した。開発外34問とのID重複は0、合計106問。元の問題群の選定を再実行したり、結果を見て入れ替えたりしていない。

割り当てキーは `sha256(case_id.encode('utf-8'))`、prefix・末尾改行なし。16進文字列の昇順（同値ならcase_id順）で0始まり順位を付け、偶数順位=superPC、奇数順位=WinPCに交互割り当て。入力本文hashとは区別し、assignment_sha256とinput_sha256を両方保存した。同じ問題の全構成・全seedは常に同じPCで実行する計画。

| PC | 開発外34問のうち | 機構72問のうち | 合計 | 本計測の予定枠数 |
|---|---:|---:|---:|---:|
| superPC | 21 | 32 | 53 | 1908 |
| WinPC | 13 | 40 | 53 | 1908 |

hash順による割り当てなので群ごとの台数比は揃え直さない。全106問の固定一覧と入力hashはassignment.json、未実行3816枠の順序はrun-plan.json。本計測を実行するための関数は今回のdriver.pyには実装していない。
