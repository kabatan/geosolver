# S9A 動作確認記録

S1の先頭問題`AIME-2015-II-15`の先頭保存候補を使い、R0→R1→R2→R3の順に、第1精度段階`_run_stage`を各1回だけ呼んだ。全構成が1プロセス0.42秒以内に戻り、10秒上限への到達・強制終了・worker例外はなかった。並列1、1コア、内部スレッド1。再実行なし。本計測・探索・最終検証・同定は実行していない。

## 制御フローの観測

| 構成 | LM線形方向の計算回数 | LMソルバに渡ったλ | 適応λ更新行の実行回数 | LM側line search呼出し / 試行数 | Newton closure呼出し / 線形ステップ試行数 |
| --- | ---: | --- | ---: | --- | --- |
| R0 | 1 | 1e-6 | 1 | 1 / 2 | 0 / 0 |
| R1 | 1 | 0 | 0 | 1 / 2 | 0 / 0 |
| R2 | 1 | 1e-6 | 0 | 1 / 2 | 0 / 0 |
| R3 | 0 | 呼出しなし | 0 | 0 / 0 | 1 / 2 |

R3は`mp.findroot`を1回呼び、指定solverは`mnewton`。既存mpmathのタプル残差に対する`MDNewton`内の線形ステップ行を2回通った。R3でLM方向計算とLM側line searchを呼ばず、Newtonへ進んだことを確認した。

R1/R2では適応λ更新行を通らず、指定されたλをLM線形ソルバへ渡した。R0では適応更新行を通った。これは数値品質・収束・速度の比較ではなく、呼出しと分岐の記録である。座標、答え、残差、正しい桁数、正誤、収束候補数、品質statusは出力していない。

## 確認範囲とassertion 1件の失敗

4回のworker実行は全て正常に戻ったが、その後の`smoke_driver.py`の確認処理は、`assert len(rows['R0']['lambda_values']) > 1`で終了コード1になった。短い確認でLM線形方向の計算は各1回だけだったため、更新後のλを渡す2回目の線形計算は観測されなかった。このassertionは複数ステップの観測を余分に要求していた。

元のdriver・worker・事前固定hashは変更せず保存した。solverを再実行せず、`audit.py`が保存済みの制御フローとソースを照合し、以下を確認した。確認方法を変更したことは`smoke/checks.json`でも`original_driver_assertions_passed=false`として残した。

- R0の適応更新行の実行、R1/R2での更新行の非実行と指定λ、R3のLM迂回とNewton実行。
- R0の新スイッチをfalseに代入した`_run_stage`のASTが指定BASE1のASTと一致。
- 適用後Pythonファイルの構文解析、smoke前後の適用前・適用後・凍結版の全ファイルhash一致。
- 最終検証・同定の12ファイルの生バイト一致。

従って切り替えの呼出し・分岐は確認できたが、R0の更新後λを次の反復で使うところや、R1/R2の複数反復にわたる固定を実行traceから実証したとはしない。固定の持続性はpatchの両方の更新分岐を止めるコードで確認する。warm Newton、direct accept、post-polish、整数派生経路の到達性も今回の段階smokeでは動かしておらず、design.mdのコード読解に基づく。

## 成果物

- `switch-r.patch`：指定BASE1へ適用する3ファイルの差分（数値コードは2ファイル、残りはengine lock）。
- `configs.json`：環境変数集合・スレッド条件・smoke上限。
- `source-hashes.json`：全3ソースの全ファイルhash、適用後source_hash、保護ファイルの一致、patchのクリーン再適用記録。
- `pre-smoke-hashes.json`：実行前に固定した設計・コード・入力候補hash。
- `smoke/R0.json`〜`R3.json`：制御フローだけの観測値。
- `smoke/driver.json`：4回の外側時間とreturncode。
- `smoke/checks.json`：元のassertion失敗を含む事後監査記録。
- `artifact-hashes.json`：成果物全ファイルの生バイトSHA256（自己参照を避けるため自身だけ除外）。

本計測やgit操作は行っていない。将来の90秒計測は別途の明示的な実行指示が必要。
