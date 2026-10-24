# 完成driverのWinPC/WSLでの起動

run-on-winpc.mdのBASE1再構築とDSL展開を済ませる。以下は起動手順のみで、この作業でWinPCは実行していない。S8一式（references.json、references-hashes.json、旧原本、measurement-*.py等を含む）を転送する。Python 3.12とsource-hashes.jsonの依存版は事前確認で照合する。Python binaryはWinPC側のhashを記録する。

```bash
S8_DIR="$PWD/jssa/difficulty/mechanism-1024/stage/S8"
S8_BASE1="$HOME/work/s8-base1"
S8_INPUT_ROOT="$HOME/work/s8-input-root"
S8_PYTHON="$S8_BASE1/.venv/bin/python"

"$S8_PYTHON" -B "$S8_DIR/driver.py" verify-plan \
  --machine winpc --base-src "$S8_BASE1" --repo-root "$S8_INPUT_ROOT" \
  --python "$S8_PYTHON"

# 模擬プロセスのみ。実問題・solverは起動しない。
"$S8_PYTHON" -B "$S8_DIR/test_measurement_contract.py"

# WinPC分が別途実行許可された際の累積7構成。53問×3seed×7=1113枠。
# source/seed/180秒/1コア/内部thread1を変えず、N+2〜N+6は含めない。
"$S8_PYTHON" -B "$S8_DIR/driver.py" run \
  --machine winpc --configs N C1 C2 C3 C4 C5 BASE --max-parallel 8 \
  --base-src "$S8_BASE1" --repo-root "$S8_INPUT_ROOT" --python "$S8_PYTHON" \
  --memory-mib 4096 --address-space-mib 16384 \
  --output "$S8_DIR/run-winpc"

# 中断後は同じ引数でrunをresumeに替える。start済み枠の再試行はしない。
"$S8_PYTHON" -B "$S8_DIR/driver.py" resume \
  --machine winpc --configs N C1 C2 C3 C4 C5 BASE --max-parallel 8 \
  --base-src "$S8_BASE1" --repo-root "$S8_INPUT_ROOT" --python "$S8_PYTHON" \
  --output "$S8_DIR/run-winpc"

# 計測終了後の独立採点。solveは呼ばない。
"$S8_PYTHON" -B "$S8_DIR/driver.py" grade \
  --machine winpc --configs N C1 C2 C3 C4 C5 BASE \
  --output "$S8_DIR/run-winpc"
```

--raw-rootは既存repo外の空ディレクトリを指定可能。省略時は/tmpへ一意作成。生ログは終了receiptのhashと併せて保管し、消去しない。runは既存campaignを上書きしない。resumeは同一の機械・パス・構成・メモリ契約とPython binaryでのみ続行。3MB以上のファイルは作らず、ログは分割する。出力ディレクトリのflockで二重起動を拒否する。

採点参照をWinPCで再生成しない。転送済みの固定参照を使い、採点コードとそのhashも維持する。時間比や成功率はまず機械内で比較し、両機の結果を合算するまでは106問の最終判定を出さない。
