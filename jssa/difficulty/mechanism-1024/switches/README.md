# 新スイッチ2つ

実装・軽量確認を完了。作業は約12分で、2時間以内に安全に動かせた。solverは1件ずつ、1 coreで実行した。共有srcは変更せず、このリポジトリでのcommit/push、昇格コマンドは行っていない。

`new-switches.patch` は **BASE1（凍結版60db4b6＋指定の既存patch）に対する差分**。15,064 bytesで3MB未満。独立した `/tmp/switch-impl` にBASE0、BASE1、最終版の3コミットを作った。

- `GEOSOLVER_ABLATE_NO_RESIDUAL_REWRITE=1`：精密化の `_smooth_zero_constraint_residuals` を通さない。接条件・距離0・正の半径補助式が対象。書き換え依存の解析微分計画だけ使わず、通常の解析微分と整数closureは残す。`verification_numerics.py` と `final_verifier.py` は凍結版とバイト一致。
- `GEOSOLVER_ABLATE_NO_DIVERSE_SELECTION=1`：探索終了後、同じ選択前候補から生の `residual_norm_float` 昇順で最大20個を精密化へ渡す。幾何的な近接除去・seed枠は使わない。同点はUID、元の順序で決める。非有限残差を除き、同じUIDの重複は最初の1件を使う。通常探索の適格条件、NOMAD fallbackの元の母集団、直通候補の扱いを保つ。救済の新規バッチも全boxの評価台帳から最大20個を選ぶ。

値が `1` のときだけON。未設定時の既存処理を残し、候補の引継ぎ用フィールドも既定は `None`。初期値、探索中のhybrid用候補、救済箱の広い台帳、後続の精密化・検証・同定・予算のロジックは共通。

確認結果：

- OFF経路の構文比較はBASE1と一致（追加import・宣言・内部フィールドを除き、新分岐をOFFにして比較）。新しい実行分岐以外の既存処理変更なし。
- 開発問題4問、seed 0、15秒でBASE0・BASE1・最終版OFFの答え集合・成功状態が一致。選択候補UID、残差、書き換え呼出数も一致。
- 各新スイッチONで2問ずつ完走。書き換え呼出49回・1690回が各0回になり、残差順選択は2→2個、200→20個。後者の選択UIDは既定20個と1個だけ共通。
- 新規境界検査23件、既存回帰検査40件が通過。patchを新しいBASE1展開物へ適用し、最終版の253ファイルとバイト一致。integrity検査も通過。

source_hash：

- BASE0：`sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5`
- BASE1：`sha256:e2115f553d6a59d6d85a30413e5719992c09e376d23d3e3e124fd07fd135b8ee`
- 最終版：`sha256:03a44bfbb743b972d95306c63a14c04b78c7d12b96a1ba83d147c56eea7f86a3`

engine-lockは既存patchと同じく2か所のsource hashだけ更新。凍結版との差分ファイル一覧、計数、手順は [verify-log.md](verify-log.md) に記録した。

未確認：全323問、長時間計測、両スイッチ同時ON、既存スイッチとの全組合せ、Windows実行、実問題での救済発動・第2探索。救済選択とhybrid/fallbackの引継ぎは軽い模擬入力で検査した。精度・正解率・速度の良し悪しは評価していない。公開CLIは180秒未満を拒否するため、15秒確認には既存EngineRunnerを直接使用した。
