# 再現方法と試験の区別

作業ディレクトリはrepository root。使用Pythonは `/home/kabatan/work/solver/.venv/bin/python` (3.12.11)。依存版・src hash・DSL hashは `experiment-plan.json` に記録している。以下のスクリプトはsrc・元DSL・既存採点を編集しない。既存結果を保つため、再実験はこのディレクトリのスクリプトを同じ階層の新しい出力用ディレクトリにコピーしてから実行する。

```bash
/home/kabatan/work/solver/.venv/bin/python jssa/difficulty/unseen-1983/failure-audit/a/check_witnesses.py
/home/kabatan/work/solver/.venv/bin/python jssa/difficulty/unseen-1983/failure-audit/a/compare_development.py
/home/kabatan/work/solver/.venv/bin/python jssa/difficulty/unseen-1983/failure-audit/a/run_global.py
```

`run_global.py` は元DSL・通常workerのまま各問を900秒上限で実行。選んだseedは既存assessmentの最初の失敗seed（4問201、1991-14のみ205）。3ストリームをCPU 0,1,2に固定し、残る1ストリームを近傍試験に使った。CPU 0〜3は互いに異なる物理コア。BLAS/OpenMPは1 thread。各workerに2GiBのメモリ制限と4,900,000 byteのファイル制限を課した。

```bash
/home/kabatan/work/solver/.venv/bin/python jssa/difficulty/unseen-1983/failure-audit/a/run_local.py
/home/kabatan/work/solver/.venv/bin/python jssa/difficulty/unseen-1983/failure-audit/a/run_warm_initial.py
```

この2コマンドは互いに同時実行しない。`run_local.py` はCPU 3、各180秒上限。全変数に `sign * 0.01 * (-1)^i` を足した2点を凍結 `MpmathRefiner` と `assemble_exact_results` へ渡す。その後、`warm_worker.py` で候補発見を一つの近傍点に差し替え、元のproduction B/C・出力処理を通す。これは**oracleによる候補注入**であり通常の未知問題の成功率には数えない。`warm_worker.py` が置換する4関数をそのファイルに列挙している。srcファイル自体は変更しない。

`run_warm_initial.py` は別の診断。`warm_initial_worker.py` が置換するのは初期probeだけであり、通常の大域探索、ヒューリスティック範囲、追加サンプル、B/Cを残す。範囲外の初期点を与えた4問はworkerが−11で終了し、範囲内の1991-14は保存された再試行で解けた。範囲外入力と異常終了の因果を確かめるbackend単体試験は行っていない。元の凍結試験で異常終了したと誤読しないこと。

サイズ検査は書き込み前に行う。1991-14の2試験で初版のpretty JSONが上限を超え、結果を保存できなかったため、その2件だけ再試行した。以後はcompact JSONを優先し、それでも大きい場合は重複するpipeline_summary/candidate_recordsを出力から除き、除去した内容のbytes・hashを残す。solverの計算・答え判定を変えるものではない。経緯は `operational-events.json`。初回の未保存結果を成功にも失敗にも数えない。

全試験の保存後に実行する：

```bash
/home/kabatan/work/solver/.venv/bin/python jssa/difficulty/unseen-1983/failure-audit/a/build_report.py
```

新しい通常worker出力の採点は既存 `research_runner._answer_keys` と `describe_exact` のcanonical keyで一致判定。元130実行はassessmentを読むだけで採点し直さない。900秒は上限であり、評価回数や候補の枯渇で早く終わる。また時間配分が変わるので180秒runの単純な続行ではない。共有計算機のwall timeには変動があり、特に近傍試験の保存失敗後の再試行は初回と時間・結果が同じだったとは主張できない。

`structure.csv` の不等式数はDSL中の比較関係の本数、predicateは別列。ConvexPolygonやBoundを展開した原子的条件数ではない。作図で消した自由座標数はDSLだけから一意に復元できないため、構築数・Point構築数をその代用指標と断言しない。Q29の追記にある書換え・新seed206〜210の検証は本ディレクトリでは行っていない。
