# S9A 部分A 本計測の事前固定

ユーザーの本計測指示により design.md の将来計測禁止を解除。実装・R0〜R3・保存configは変更しない。最大並列は今回の明示指示の6、1ジョブ1コア・内部1スレッド。commit/pushなし。

対象はS1/S3共通12問と problem-set.json の72問の和集合。重複は一度だけ。探索変数0も一覧に残し構造的対象外とする。候補なし・探索handoff未到達・工程失敗は理由付き欠測とし、問題を追加除外しない。
候補はS1のhash照合済み保存物を優先し、次に準備時点で完成済みのS7/run2保存物（入力バイトhash一致、seed0、BASE主探索handoff）を使う。S7/run2の桁数表は読まない。利用元・保存候補のhashを固定。その他はS1 workerのsearch分岐を流用しBASE1・seed0・178秒pipeline/180秒外枠で主探索を一度だけ行い最初のrun_refinement直前を保存。代数前処理で完了してhandoffがない場合も再探索しない。
全構成で全保存tupleを同じ順に使用。問題ごとR0,R1,R2,R3を対象順のindex mod4だけ巡回。各構成は独立プロセスでpatched source・mp.workdps(180)・runtime_session(start+90)・保存configのrefine_candidatesを一度だけ呼ぶ。候補集合全体90秒、親98秒。返却された暫定座標は測定し、強制終了で返却のない工程は欠測。外枠後の救済・途中点の独自採用はしない。再試行・別seedなし。

桁数は凍結版の別プロセスで精密化直後の返却座標から700dpsで評価。参照はS7入力に保存されたbenchmarks正答の正規化式（S1はS1固定式）。丸め・整数同定をせず、複数正答の最小絶対誤差、digits=min(600,-log10(error))、error=0は600。負値は保持。最良候補は評価可能な最小誤差の候補で、通過状態で選別しない。返却なし・有限目標値なしは欠測。測定90秒外枠、部分行を逐次保存。最終検証も別の凍結プロセス、全ablation解除、返却順で候補集合全体90秒/親98秒。未処理は理由記録。凍結source_hashはd8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5。

収束候補数はrefine_candidatesのconverged_count（target_reached）を正本とし、hard_feasibleかつtarget_reachedの数も別列。時間はrefine_candidates呼出し直前から返却までの壁時計秒、探索・測定・検証は別計時。候補単位時間はS1のtimed_singleを流用。
初期残差は保存全候補のx_floatの正確な二進値を180dpsに変換し、通常のload_problem_bundle/build_ir_evaluatorの残差L2ノルムを180dpsで評価した中央値。非有限は+inf、評価例外は欠測（全候補が評価できた問題のみ問題中央値を定義）。全問題中央値は候補がある対象のうち問題中央値が定義された全問題の中央値、厳密な大なりでlarge。欠測数を明記し、残差を見て対象を変えない。
σ_baseはS7/classification.csvの文字列とbase_judgmentをそのまま使用、再計算しない。閾値<1e-60。分類未確定・参照なしはσ欠測。σ数値は指数表記を維持。

A1は特異群で各R1/R3の(digits_R0-digits_Ri)>=40が各50%以上、非特異群で各abs(digits_Ri-digits_R0)<=20が各70%以上、4条件全てで成立。両構成同時条件の割合も補助表示する。A2はlarge群でconverged_R3<converged_R0が70%以上。A3は全候補生成対象でabs(digits_R2-digits_R0)<=20が80%以上。
分母は各固定群の全問題（比較の欠測を分母から引かず非成功に数える）。比較可能数・欠測・分子・率を併記。候補を作れない探索変数あり問題は理由付き欠測として一覧・総数を残し、A3全対象分母に含めた保守的率も追加表示。分母0は判定不能。境界は上記の包含関係のまま。達成しない予測は外れと報告。

各新規ジョブ起動前に/tmp空きを確認、6 GiB未満なら新規開始を停止し報告。既開始のreceiptを再利用して未開始工程のみ継続可能、開始済み工程は再実行禁止。入力・ルール・全script・source・構成・候補hashを最初の計測前にpre-run-hashes.jsonへ固定。工程開始receiptを排他的に作成。生ログ・pickle・詳細測定は外部/tmp、個別ファイルは3,000,000bytes未満に制限。進捗は追記。終了時raw hash・監査・表を保存。
