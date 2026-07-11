# GeoTarget solver 詳細引継ぎ資料

| 項目 | 値 |
|---|---|
| 作成日 | 2026-07-11 (Asia/Tokyo) |
| 対象 algorithm revision | `e2cf389346f5ffa3a307e52204542ad219ebdd07` |
| algorithm-ready tag | `algorithm-lab-ready-2026-07-11` |
| 詳細資料の引継ぎ tag | `solver-handoff-2026-07-11` |
| 状態 | **アルゴリズム実験へ入れる基盤はあるが、solver は未完成** |

## まず結論

次の担当者は、新しい基盤や厳密解法の大枠を作るところから始める必要はない。現在の repository には、black-box 幾何 DSL、plugin ABI、compiler/oracle、production の探索 loop、canonical validation、truth-blind な local-solver 実験 runner、および代表 baseline が揃っている。

ただし、現 baseline は 9 件の診断用 case にすぎず、8 starts で全 target を得たのは 6/9 case、Gold と整合しない residual-qualified endpoint も多い。これは solver の完成や一般成功率を意味しない。次の中心課題は、**現 solver を基準に、一度に一つのアルゴリズム機構を同一 budget で比較し、local correctness、all-target discovery、特異・悪条件への対応を順に改善すること**である。

最初の有力実験は次の順序である。

1. 現 runner に frozen-assessor / reported-acceptance 指標を最小追加し、legacy、prod-tol、prod-options controls を分ける。
2. 過去に強い開発 signal があった bound-aware Trust Region と、現行 LM の scale-aware damping を、現在の truth-blind lab で比較する。
3. survivor が出た場合だけ native な小さい Trust Region / safeguarded LM candidate を実装する。
4. その local champion に condition-aware correction / acceptance を加え、NearRank と Tangent の不正確な endpoint を減らす。
5. local pipeline を固定してから、independent-uniform 保険 laneを残した current counter/Halton/scrambled-QMC discovery を比較する。

アルゴリズム名を最初から最終決定しない。各段階で failure を測り、最大の原因に対する仮説を選び、paired experiment の gate を通ったものだけ残す。

## この資料の優先順位

この directory の文書は、次の順に読む。

1. [01_OWNER_DIRECTIVES_AND_SCOPE_ja.md](01_OWNER_DIRECTIVES_AND_SCOPE_ja.md) — これまでオーナーが明示した方針。計画のドリフト防止に最優先。
2. [02_REPO_STATUS_AND_ARCHITECTURE_ja.md](02_REPO_STATUS_AND_ARCHITECTURE_ja.md) — 現在の Git、実装、DSL、research seam、既知の限界。
3. [03_BASELINE_AND_PRIOR_EVIDENCE_ja.md](03_BASELINE_AND_PRIOR_EVIDENCE_ja.md) — 現 baseline、過去の有効な signal、negative results。
4. [04_ALGORITHM_RESEARCH_ROADMAP_ja.md](04_ALGORITHM_RESEARCH_ROADMAP_ja.md) — 仮説駆動のアルゴリズム研究計画と分岐条件。
5. [05_EXPERIMENT_PLAYBOOK_ja.md](05_EXPERIMENT_PLAYBOOK_ja.md) — case、seed、budget、metrics、統計、実装・commit・rollback 手順。
6. [06_COMPLETION_AND_RELEASE_CRITERIA_ja.md](06_COMPLETION_AND_RELEASE_CRITERIA_ja.md) — 「solver 完成」の段階定義と release gate。
7. [07_NEXT_AGENT_START_HERE_ja.md](07_NEXT_AGENT_START_HERE_ja.md) — 最初の数 commit の具体的作業。
8. [08_PRIMARY_SOURCES_ja.md](08_PRIMARY_SOURCES_ja.md) — 候補手法の一次資料と、GeoTarget で成立しない仮定。

既存の短い運用境界は [../../operations/HANDOFF.md](../../operations/HANDOFF.md)、一次資料の全 matrix は [../../research/LITERATURE_MATRIX.md](../../research/LITERATURE_MATRIX.md)、negative-result の machine-readable 正本は [../../../research/negative-results/ledger.json](../../../research/negative-results/ledger.json) にある。

## 30 分で再開する手順

```powershell
cd C:\solver
git status --short --branch
git rev-parse HEAD
git tag --points-at HEAD
powershell -File scripts/doctor.ps1

julia +1.12.6 --startup-file=no --history-file=no --project=julia `
  benchmarks/solver_lab/run.jl `
  --families=TANGENT-CIRCLE-LINE,MULTIROOT-WARPED `
  --prefixes=2,4,8 `
  --output=benchmarks/results/raw/handoff-smoke.json
```

期待する Git 状態は `main`、`solver-handoff-2026-07-11` が指す clean documentation commit であり、`algorithm-lab-ready-2026-07-11` (`e2cf389`) がその直前の algorithm-ready ancestor である。remote は設定されていない。raw JSON は `benchmarks/results/raw/` に生成され、Git では無視される。

次に [07_NEXT_AGENT_START_HERE_ja.md](07_NEXT_AGENT_START_HERE_ja.md) の `ALG-LAB-000` から開始する。過去の `EXP-LOCAL-003` formal launcher や AppContainer は実行しない。

## 現時点の重要な数値

baseline artifact:

- path: `benchmarks/results/raw/solver-lab-baseline.json`
- SHA-256: `B495F81FDA8376C28017123D9DCD78D733057E7BC2040F37E50E472D111F7817`
- Julia 1.12.6、1 thread、clean HEAD
- 9 cases、72 attempts、2/4/8 saved-start prefixes
- 600 black-box evaluations/start、120 iterations/start
- prefix 8: all-target 6/9 cases、targets 9/16、configurations 9/18
- prefix 8: 12,391 callback evaluations、13 false-candidate proxies、14 false-target proxies
- exception 0、runner budget overrun 0、evaluation-count mismatch 0

ここで `false candidate/target` は public な false validated answer そのものではない。現在の lab summary は未採用 endpoint も含めて Gold と比較している。さらに旧 lab control は 120/600 + `sqrt(eps)`、nominal production local options は 250/2000 + `1e-12` である。local comparison には common frozen assessor と reported acceptance を分け、legacy/prod-tol/prod-options controls を別に作る必要がある。この修正は最初の小作業として明記している。

## 本資料が上書きする古い曖昧さ

- 長期 branch を増やさず `main` を唯一の正本とする。必要な場合だけ短命の `codex/exp-*` を使い、統合後すぐ削除する。
- formal protocol の完成を algorithm experiment の前提にしない。
- exact algebraic solver、RUR、Gröbner を一般問題の main route にしない。
- `research/` の過去 infrastructure を通常の実験 template として複製しない。
- local-solver lab と end-to-end discovery experiment を区別する。
- DSL/plugin の black-box 表現力を保ち、多項式への lowering を candidate の前提にしない。

## 引継ぎ package の検証

ZIP には repository-relative tree のままこの directory、baseline JSON、オーナー入力 plan、および選択した正本資料を含める。ZIP 内の `MANIFEST.sha256` は manifest 自身を除く全 file を列挙し、展開先 root で次のように検証できる。

```powershell
Get-Content MANIFEST.sha256 | ForEach-Object {
  $hash, $path = $_ -split '  ', 2
  if ((Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash -ne $hash) {
    throw "checksum mismatch: $path"
  }
}
```

ZIP は配布物であり repository history を太らせないため `artifacts/raw/` に置く。Markdown 正本だけを Git に commit する。
