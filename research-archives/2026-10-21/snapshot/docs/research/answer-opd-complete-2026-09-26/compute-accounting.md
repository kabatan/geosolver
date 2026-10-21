# OPD 正式学習の計算時間集計

16 rounds・128軌跡・32 optimizer updates の完了済みreceiptを読み、処理ごとの `elapsed_seconds` を1回ずつ加算した。

| 計算区分 | 件数 | elapsed | 生成token |
|---|---:|---:|---:|
| 32k rollout | 16 | 9,515.16 秒 (02:38:35) | 1,225,059 |
| 81k retry | 4 | 832.23 秒 (00:13:52) | 33,711 |
| 成功train | 16 | 2,225.81 秒 (00:37:06) | 採用 1,127,698 |
| **成功した正式計算の合計** | **36 receipt** | **12,573.20 秒 (03:29:33)** | **1,258,770 generated-attempt tokens** |

採用tokenは **1,127,698**（32kから1,093,987、81k retryから33,711）。生成試行全体との差 **131,072 token** は最終trainに採用されていない。4件のretryは元出力が各32,768 tokenで `length` 終了し、retryは 11066, 9386, 5875, 7384 tokenで `stop` 終了した。4件すべてで元出力とretry prefixは一致しなかった。

round 15の失敗train試行は **34.95 秒・0 update**、保存済みCUDA healthcheckは **0.413 秒・0 learning update**。どちらも成功計算合計には含めない。GPU watchdog/Xid 8 の失敗後に同一完了batchを再利用して学習を完了した。再起動・復旧待機の経過時間は記録がないため加算していない。準備・calibration・待機・評価時間も含まない。

成功train時間のreceipt合計はcombined manifestの **2,225.81 秒**、採用tokenはmanifestの **1,127,698** と一致する。集計元final summary SHA-256: `a296dc3662ed3b855b03c9c005b36d351e1ea8bef96aac0b010703d1be272c32`。

詳細: [`compute-accounting.json`](compute-accounting.json)。
