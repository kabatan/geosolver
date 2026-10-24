# WinPC / WSL で同一BASE1を準備する

この納品ではWinPCへの転送・遠隔操作・本計測はしていない。以下のコマンドはソース復元と読み取り専用preflightまでで、solveは呼ばない。現在のdriverはverify-plan専用。本計測driverの仕様はdriver-design.md。

WSLのLinux filesystem上（例 `~/work/s8`）を使用し、S8ディレクトリ一式を配置する。`patches/base0-60db4b6.tar.gz` は凍結commit `60db4b679b04167175c51c479c87c22fa663fda0` のsrc、pyproject.toml、uv.lockをgit archiveしたもの。既存git worktreeの外側に新しいBASE1ディレクトリを作り、そこに展開する（git applyが親repoを検出して違うパスを対象にしないようにする）。

```bash
# 実際に転送したS8の絶対パスへ置き換える
S8_DIR="$PWD/jssa/difficulty/mechanism-1024/stage/S8"
S8_BASE1="$HOME/work/s8-base1"
(cd "$S8_DIR" && sha256sum -c SHA256SUMS)
mkdir -p "$HOME/work"
mkdir "$S8_BASE1"
tar -xzf "$S8_DIR/patches/base0-60db4b6.tar.gz" -C "$S8_BASE1"
cd "$S8_BASE1"
git apply --check "$S8_DIR/patches/jssa-ablation-67ad79a-vs-60db4b6.patch"
git apply "$S8_DIR/patches/jssa-ablation-67ad79a-vs-60db4b6.patch"
git apply --check "$S8_DIR/patches/new-switches.patch"
git apply "$S8_DIR/patches/new-switches.patch"
uv sync --frozen --extra dev --no-install-project --python 3.12
```

適用順は必ずBASE0 → 既存WinPC ablation patch → new-switches.patch。第1段のsource hashは `sha256:e2115f553d6a59d6d85a30413e5719992c09e376d23d3e3e124fd07fd135b8ee`、完成BASE1は `sha256:03a44bfbb743b972d95306c63a14c04b78c7d12b96a1ba83d147c56eea7f86a3`。同梱パッチは次の原本のバイトコピーで、ローカルで再構築して全src一致を確認済み（patches/reconstruction.json）。

- 既存：`jssa/difficulty/mechanism-1024/run-7/jssa-ablation-67ad79a-vs-60db4b6.patch`
- 新規：`jssa/difficulty/mechanism-1024/switches/new-switches.patch`

engine-lock.jsonの手書き更新や再生成は不要。最終検証はBASE0とバイト一致である。S3のT0/T1/T2パッチ等は追加適用しない。8変数の完全な値はconfigs.jsonから設定する。`GEOSOLVER_ABLATE_SEARCH_MODE` はBASE1では未実装なので使用しない。

対象DSLだけを同梱したinputs.tar.gzを、既存repoまたは新規のinput-rootへ展開する。archive内はassignment.jsonのdsl_pathと同じ相対パス。問題の内容・構成・割り当てをWinPCで再選択しない。

```bash
S8_INPUT_ROOT="$PWD/s8-input-root"
mkdir "$S8_INPUT_ROOT"
tar -xzf "$S8_DIR/inputs.tar.gz" -C "$S8_INPUT_ROOT"
PYTHONDONTWRITEBYTECODE=1 "$S8_BASE1/.venv/bin/python" -B \
  "$S8_DIR/driver.py" verify-plan --machine WinPC \
  --source-root "$S8_BASE1" --repo-root "$S8_INPUT_ROOT" \
  > "$S8_DIR/winpc-preflight.json"
```

preflightは106入力、全BASE1ファイル、source/engine lock、Python 3.12、依存lockの全版、PyNomad importを照合する。Linuxでcoloramaだけ不在なら許容する。source-hashes.json / hashes.jsonに生ファイルhashとlockを保存してある。WSL側Python binary自体はOS/配布物で異なりうるため、同じPython系列・同じ依存版を確認したうえで、そのbinary hash/OSを別受領証に記録する。hash一致を偽装するためのlock書換えはしない。

現在はここで終了する。将来の本計測は、別途実行が指示された際にdriver-design.mdを実装し、WinPC割当53問・1908枠だけをrun-plan.json既定順で動かす。superPC割当は同じ入力でもWinPCで実行しない。最大6並列、各1コア・180秒・seed601〜603・構成ごと新規worker、全GEOSOLVER_*継承除去、内部thread1は両機共通とする。
