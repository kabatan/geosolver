# S3 段階1：接する条件の残差スイッチ

`GEOSOLVER_S3_TANGENCY_MODE=T0 / T1 / T2` を `/tmp/s3-impl/src` に実装した。未設定はT2。事前登録10の条件・対象・予測Q1〜Q4・読み方は変更していない。本計測の精密化は行っていない。

- **T0**：接する条件の残差を元のまま残す。距離0の座標差と正の半径補助式は残す。接する条件の書き換えに依存する解析微分計画（requires_smoothing）を採用しない。
- **T1**：接点・共通点の有無によらず、直線・円はδ²−r²、円円は内外接の符号付き距離差の絶対値が小さい枝。解析微分は二乗式に合わせ、対応できない円円とDistance=半径の計画は使わない。
- **T2／未設定**：元のfinalの接点・共通点式とfallbackを維持。12問の先頭候補で元のfinalとの残差・使用式のバイト一致を確認した。

Distance=半径のT1は、凍結版の `distance_contact_sources` と同じLine／Circle・中心・半径の一致構文を使い、接点の証明を要求せずに二乗式へ置き換える。T2は凍結版どおり接点を示せるDistance=半径だけを接点式にする。この表現は固定12問にはない。T0のDistance形式は凍結版の元の左辺−右辺を保持する（IsTangentの非負残差とは別）。

変更は `refinement/mpmath_refiner.py`、`refinement/analytic_jacobian.py`、新設 `refinement/s3_tangency.py`、および `engine-lock.json` のソースhash2値だけ。最終検証・同定・探索・候補選択・整数closure・精度設定は共通。不正なモード値はValueError。既存のNO_RESIDUAL_REWRITEは一式を外す既存スイッチであり、S3確認では未設定にした。

開始時の `/tmp/s3-impl` には3ファイルの差分があったため、`/tmp/s3-impl.pre-resume-20261024` に退避した。元のfinalから作り直し、変更前の253ファイルの名前・内容がバイト一致することを確認してからスイッチを適用した。元のfinalは書き換えていない。

成果物：

- [switch.patch](switch.patch)：`/tmp/mechanism-7b-lkdjle5l/final` に対する差分（9,125 bytes、3MB未満）。`src/` の親ディレクトリで `git apply switch.patch`。
- [impl-hashes.json](impl-hashes.json)：実装全ファイル・変更ファイル・比較元・確認コード・成果物のSHA-256と再適用記録。
- [contacts.json](contacts.json)：26接条件の構文判定。群A 6問、群B 6問。Distance(中心,直線)=半径は0件。
- [switch-check.md](switch-check.md)／[switch-check.json](switch-check.json)：各問の先頭候補の使用式、T2＝未設定＝元のfinalのバイト照合、解析微分と補助式の軽量確認。
- [check_stage1.py](check_stage1.py)／[check_boundaries.py](check_boundaries.py)：確認用コード。並列1・1 core・内部スレッド1。探索・精密化・最終検証・目標値の誤差評価は実行しない。

比較元 source_hash：`sha256:03a44bfbb743b972d95306c63a14c04b78c7d12b96a1ba83d147c56eea7f86a3`。実装 source_hash：`sha256:add5afaf829806ca3cbd11fb07b69d956102752e1c6738b0630581a3ceb121eb`。engine-lockの検証も通過した。生の完全な残差ベクトルは `/tmp/s3-impl/check` に保存した。

本計測前の固定・pushはこの段階では行わない。S4と他タスクのファイルは変更せず、commit/push・昇格・システム導入も行っていない。
