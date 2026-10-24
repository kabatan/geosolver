# 実問題の次数と作図の深さ

実問題表を先行保存した。開発外34問、開発群323問の全行を収録。集計図と人工族は続けて作成する。

|群|件数|既存系の次数判明|強化系の次数判明|
|---|---:|---:|---:|
|unseen34|34|30|24|
|dev323|323|271|232|

次数は重複度込み。正次元は有限個の複素解数ではなく、次元とイデアル次数を別列に記録する。
既存系は変更しないalgebraize.translate(fresh, with_target=False)とrun_exact.build(rabinowitsch=True)。
強化系は変更しないstrong_translate.translateとrun_strong.prepareによるT付き系を非零因子ごとに飽和する。
Singularのstd, dim, multを使用。各系30秒、1問2系で最大60秒、4並列。solverの新規実行なし。
深さは名前付き作図命令の依存DAG。定数・自由変数だけによるPointは0、他命令は入力の最大深さ+1。
条件とtargetは深さに加えない。匿名入れ子はその命令の一部。詳細はdepths/に保存。

## 続く集計

深さ別分布、回帰、既存msolve失敗、solver時間、反例、欠測、人工族、段階2設計。
