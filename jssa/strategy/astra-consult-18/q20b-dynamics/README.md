Q20b・力学系レンズの成果物

**結論は [answer.md](answer.md)。Aの核としては現状「不可」。** 3候補の(a)〜(h)、候補1の小検証、否定的な結果、未実行の1.5日設計を記した。

| ファイル | 内容 |
|---|---|
| [preregistration.md](preregistration.md) | 新探索前に固定した対象・格子・ラベル・継続基準 |
| [registration-lock.json](registration-lock.json) | 固定時刻、3ファイルとsrcのSHA-256、環境版 |
| [inputs.json](inputs.json) | DSL、探索箱、旧2枝、対称交換、代表図、旧rawのハッシュ |
| [experiment.py](experiment.py) | 凍結した準備・実行・解析コード |
| [raw/](raw/) | 4問×2予算、各1024行のJSONL。分類・始点・終点・残差・SciPy終了情報 |
| [replay.json](replay.json) | 旧始点20件の再生と照合 |
| [run-status.json](run-status.json) | 完了状況、件数、所要時間542.209秒 |
| [summary.json](summary.json) | 全集計、Q1〜Q3と継続判定 |
| [uncertainty.csv](uncertainty.csv) | 全96組の問題・予算・ラベル・尺度ごとの相違率 |
| [verification.json](verification.json) | 解析時点での固定ファイル・src・格子・ラベルの確認 |
| [verify.py](verify.py) / [independent-verification.json](independent-verification.json) | 独立な対数え上げ、128終点の再採点、代表図照合、対照の記号計算 |
| [plot.py](plot.py) / [render.py](render.py) | 保存結果のみからSVGとPNGを生成。新探索なし |
| [basin-maps.svg](basin-maps.svg) / [basin-maps.png](basin-maps.png) | 4問の有限予算分類図 |
| [uncertainty-curves.svg](uncertainty-curves.svg) / [uncertainty-curves.png](uncertainty-curves.png) | 4尺度の相違率。フラクタル次元の確定図ではない |
| [theory.md](theory.md) | 既知のWada統合性、条件付きLM同変性、対照の厳密計算、尺度の注意 |
| [literature.md](literature.md) | 確認した一次文献と未確認の範囲 |
| [old-census.json](old-census.json) | 旧323問中71問が複数座標クラスタという確認 |
| [delivery-audit.json](delivery-audit.json) | 最終のハッシュ・リンク・サイズ確認 |

**データを読み直す手順。** リポジトリのルートで、指定Pythonを使う。以下は保存データを再解析・再評価し、このフォルダ内の集計を更新する。新しい局所探索は行わない。

```bash
env PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/q20b-dynamics/experiment.py analyze
env PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/q20b-dynamics/verify.py
env PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/q20b-dynamics/plot.py
/home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-18/q20b-dynamics/render.py
```

`prepare` と `run` は完了済みなので再実行しない。実験の凍結対象は `preregistration.md`・`experiment.py`・`inputs.json`。検算・可視化・文章は実験後に追加した。図の作成時には指定環境にmatplotlibが無かったため、インストールせず標準ライブラリでSVGを生成した。PNGは既設Inkscapeの書出し機能で生成し、目視確認済み。`render.py` は設定・キャッシュもこのフォルダの `render-*` 内へ限定する。

固定したPythonは3.12.11、NumPy 2.5.1、SciPy 1.18.0。srcの246ファイルのまとめたSHA-256は `64bce3ac2991acea9518943240fb20db16607b656ac79b4ef589ec49834c0cea`。rawは各ファイル1024件。seed 0の旧記録は選定と再生にのみ使い、今回の格子件数へ混ぜていない。Kは `max_nfev` であり、実行の全残差評価数や反復数ではない。

**資料の引継ぎ。** 再開時にはこのフォルダに暫定answer.mdだけがあり、前回の新計算結果はなかった。Q20と追加基準、セッション要約、相談16・17、report-draft-v10・supplement-v10、旧basin/raw/human特徴、astra-consult-17のG〜L・Q6〜Q10を参照した。Q3・Q4は実際の保存先 `jssa/difficulty/wall-diagnostic/answer.md` と `jssa/difficulty/multiplicity/answer.md` を参照した。Q5の指定された `full-solver-nohard` の成果物と `astra-consult-17/Q5` は見つからず、未読の資料を読んだとは扱わない。追加取得や大規模な再計算はしていない。

この作業でsrc・旧データ・Python環境は変更していない。pip install、git fetch、commit、pushは行っていない。新しい探索は1プロセス・1スレッドで実施した。全成果物はこのフォルダ内に保存した。
