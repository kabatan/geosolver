"""sol-1: search for coincident-point equality solutions from independent starts.

Only hit coordinates are read from the old search records, to exclude pairs
that coincide in every hit. No failed endpoint, start, or basin label is used.
See ghost-exact/README.md for numerical conventions and limitations.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from datetime import UTC, datetime
from functools import lru_cache
from itertools import combinations
from pathlib import Path

# Limit BLAS threads before importing numpy; independent processes do the work.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import scipy  # noqa: E402
from ghost_scan import point_names  # noqa: E402
from probe_basins import answer_float, construction_coordinates  # noqa: E402
from scipy.optimize import least_squares  # noqa: E402

from geosolver import GeometryProblem  # noqa: E402
from geosolver.engine.standard.evaluation.ir_evaluator import (  # noqa: E402
    IREvaluator,
)
from geosolver.engine.standard.evaluation.snapshots import EvaluationStore  # noqa: E402
from geosolver.engine.standard.problem.infer_problem_bounds import (  # noqa: E402
    infer_problem_bounds,
)
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle  # noqa: E402
from geosolver.problem.ir.schema import IRConstruction  # noqa: E402

RES_TOL = 1e-10
RANK_RTOL = 1e-8
DIFF_STEP = 1e-6
N_STARTS = 20
PAIR_FIELDS = [
    "id",
    "P",
    "Q",
    "found",
    "best_res",
    "dim",
    "has_hits",
    "i",
    "j",
    "n_starts",
    "n_success",
    "n_failed",
    "n_limit",
    "n_rank_failed",
    "n_padding",
    "best_x",
    "dim_x",
    "dim_res",
    "singular_values",
    "errors",
]
PROBLEM_FIELDS = [
    "id",
    "n_vars",
    "n_pairs",
    "n_pairs_found",
    "max_dim",
    "has_hits",
    "n_hits",
    "n_points",
    "n_pairs_total",
    "n_pairs_excluded",
    "n_starts",
    "n_failed",
    "n_limit",
    "n_rank_failed",
    "n_pairs_dim_unknown",
    "n_pairs_all_failed",
    "seconds",
    "status",
    "errors",
]


def central_dimension(fun, x):
    """Numerical tangent nullity of the unpadded augmented equality system."""
    x = np.asarray(x, dtype=float)
    cols = []
    for j in range(x.size):
        step = DIFF_STEP * max(1.0, abs(x[j]))
        xp, xm = x.copy(), x.copy()
        xp[j] += step
        xm[j] -= step
        cols.append((fun(xp) - fun(xm)) / (2 * step))
    jac = np.column_stack(cols)
    if not np.all(np.isfinite(jac)):
        raise ValueError("nonfinite central-difference Jacobian")
    s = np.linalg.svd(jac, compute_uv=False)
    rank = int(np.count_nonzero(s >= s[0] * RANK_RTOL)) if s.size and s[0] > 0 else 0
    return x.size - rank, s.tolist()


def coordinate_at(coord, base_names, x):
    names, evaluator = coord
    vals = dict(zip(base_names, x, strict=True))
    value = answer_float(evaluator, [vals[n] for n in names])
    return float("nan") if value is None else value


def augmented_evaluator(bundle, coords, p, q):
    """Use construction_coordinates' targets in one shared numerical snapshot.

    Appending their x/y differences to the IR residual list avoids rebuilding
    the same constructions four times per LM evaluation. No guard, inequality,
    hard-feasibility, target-answer, or bounds penalty is appended.
    """
    extra = []
    for axis in "xy":
        a = coords[f"{axis}_{p}"][1].bundle.spec.answer_expr
        b = coords[f"{axis}_{q}"][1].bundle.spec.answer_expr
        extra.append(f"({a}) - ({b})")
    spec = replace(
        bundle.spec,
        construction=[IRConstruction("ORIGINZ", "Point(0, 0)"), *bundle.spec.construction],
        constraints=[*bundle.spec.constraints, *extra],
        v=[*bundle.targets, 0, 0],
        m=len(bundle.targets) + 2,
    )
    augmented = replace(bundle, spec=spec, targets=(*bundle.targets, 0, 0))
    return IREvaluator(augmented, (), EvaluationStore(augmented, capacity=16))


def solve_pair(cid, names, i, j, bundle, coords, bounds, has_hits):
    p, q = names[i], names[j]
    ev = augmented_evaluator(bundle, coords, p, q)

    def residual(x):
        return np.asarray(ev.evaluate_float_residual(x.tolist()).residual_vector, dtype=float)

    n = len(bundle.var_names)
    padding = max(0, n - len(ev.bundle.targets))

    def lm_residual(x):
        r = residual(x)
        # MINPACK requires m >= n. Zero rows leave the objective and rank intact.
        return np.pad(r, (0, padding)) if padding else r

    rng = np.random.default_rng([0, i, j])
    best, best_x = math.inf, None
    dim, dim_x, dim_res, svals = -1, None, None, None
    n_success = n_failed = n_limit = n_rank_failed = 0
    errors = Counter()
    for _ in range(N_STARTS):
        start = bounds[:, 0] + rng.random(n) * (bounds[:, 1] - bounds[:, 0])
        try:
            result = least_squares(
                lm_residual,
                start,
                method="lm",
                max_nfev=100 * n,
                ftol=1e-14,
                xtol=1e-14,
                gtol=1e-14,
            )
            n_limit += int(result.status == 0)
            r = residual(result.x)
            norm = float(np.linalg.norm(r)) if np.all(np.isfinite(r)) else math.inf
        except Exception as error:  # failure is recorded, never replaced by a finite penalty
            n_failed += 1
            errors[f"{type(error).__name__}: {error}"] += 1
            continue
        if norm < best:
            best, best_x = norm, result.x.tolist()
        if norm <= RES_TOL:
            n_success += 1
            try:
                d, s = central_dimension(residual, result.x)
            except Exception as error:
                n_rank_failed += 1
                errors[f"rank {type(error).__name__}: {error}"] += 1
                continue
            # Keep the largest observed nullity; break ties by residual.
            if d > dim or (d == dim and (dim_res is None or norm < dim_res)):
                dim, dim_x, dim_res, svals = d, result.x.tolist(), norm, s
    return dict(
        id=cid,
        P=p,
        Q=q,
        found=int(n_success > 0),
        best_res=best,
        dim=dim,
        has_hits=int(has_hits),
        i=i,
        j=j,
        n_starts=N_STARTS,
        n_success=n_success,
        n_failed=n_failed,
        n_limit=n_limit,
        n_rank_failed=n_rank_failed,
        n_padding=padding,
        best_x=best_x,
        dim_x=dim_x,
        dim_res=dim_res,
        singular_values=svals,
        errors=dict(errors),
    )


def prepare_problem(row, case, raw_dir=None):
    cid, dsl = row["id"], case["dsl"]
    bundle = load_problem_bundle(GeometryProblem.model_validate(dsl).engine_document())
    if len(bundle.var_names) != int(row["n_vars"]):
        raise ValueError(f"{cid}: n_vars differs from basins table")
    bounds = np.asarray(infer_problem_bounds(bundle), dtype=float)
    if not np.all(np.isfinite(bounds)) or np.any(bounds[:, 1] <= bounds[:, 0]):
        raise ValueError(f"{cid}: invalid random-start bounds")
    names = sorted(point_names(dsl))
    coords = construction_coordinates(dsl, names)
    raw_dir = Path(raw_dir) if raw_dir is not None else ROOT / "jssa/difficulty/minima/raw-323"
    raw = json.loads((raw_dir / f"{cid}.json").read_text())
    hits = [r["x"] for r in raw.get("records", []) if r["cls"] == "hit"]
    # Exactly the pair exclusion convention in ghost_scan.py, including its
    # use of all finite point coordinates to define the relative tolerance.
    figures = []
    for x in hits:
        figure = {}
        for name in names:
            point = np.array(
                [coordinate_at(coords[f"{a}_{name}"], bundle.var_names, x) for a in "xy"]
            )
            if np.all(np.isfinite(point)):
                figure[name] = point
        figures.append(figure)
    excluded = set()
    for i, j in combinations(range(len(names)), 2):
        p, q = names[i], names[j]
        if figures and all(
            p in f
            and q in f
            and np.linalg.norm(f[p] - f[q])
            < 1e-6 * max(1.0, max(np.linalg.norm(v) for v in f.values()))
            for f in figures
        ):
            excluded.add((i, j))
    return bundle, coords, bounds, names, hits, excluded


def prepare_summary(row, case, raw_dir=None):
    began = time.monotonic()
    bundle, _, _, names, hits, excluded = prepare_problem(row, case, raw_dir)
    indices = [ij for ij in combinations(range(len(names)), 2) if ij not in excluded]
    meta = dict(
        id=row["id"],
        n_vars=len(bundle.var_names),
        has_hits=int(bool(hits)),
        n_hits=len(hits),
        n_points=len(names),
        n_pairs_total=len(names) * (len(names) - 1) // 2,
        n_pairs_excluded=len(excluded),
        prep_seconds=time.monotonic() - began,
    )
    return meta, indices


@lru_cache(maxsize=4)
def chunk_context(dsl_json):
    dsl = json.loads(dsl_json)
    bundle = load_problem_bundle(GeometryProblem.model_validate(dsl).engine_document())
    names = sorted(point_names(dsl))
    return (
        bundle,
        construction_coordinates(dsl, names),
        np.asarray(infer_problem_bounds(bundle), dtype=float),
        names,
    )


def solve_chunk(cid, dsl_json, indices, has_hits):
    began = time.monotonic()
    bundle, coords, bounds, names = chunk_context(dsl_json)
    pairs = [solve_pair(cid, names, i, j, bundle, coords, bounds, has_hits) for i, j in indices]
    return pairs, time.monotonic() - began


def summarize(meta, pairs, seconds):
    errors = Counter()
    for pair in pairs:
        errors.update(pair["errors"])
    problem = dict(
        **{k: v for k, v in meta.items() if k != "prep_seconds"},
        n_pairs=len(pairs),
        n_pairs_found=sum(p["found"] for p in pairs),
        max_dim=max((p["dim"] for p in pairs), default=-1),
        n_starts=sum(p["n_starts"] for p in pairs),
        n_failed=sum(p["n_failed"] for p in pairs),
        n_limit=sum(p["n_limit"] for p in pairs),
        n_rank_failed=sum(p["n_rank_failed"] for p in pairs),
        seconds=seconds,
        status="ok",
        errors=dict(errors),
    )
    return problem


def read_checkpoint(out):
    """Read completed problems only; tolerate the initial, narrower CSV schema."""
    numeric = set(PAIR_FIELDS + PROBLEM_FIELDS) - {
        "id",
        "P",
        "Q",
        "best_res",
        "seconds",
        "best_x",
        "dim_x",
        "dim_res",
        "singular_values",
        "errors",
        "status",
    }

    def read(path):
        with path.open() as file:
            rows = list(csv.DictReader(file))
        for row in rows:
            for k, v in row.items():
                if not v:
                    row[k] = None
                elif k in numeric:
                    row[k] = int(v)
                elif k in ("best_res", "seconds", "dim_res"):
                    row[k] = float(v)
                elif k in ("best_x", "dim_x", "singular_values", "errors"):
                    row[k] = json.loads(v)
        return rows

    problems = {r["id"]: r for r in read(out / "per-problem.csv")}
    pairs = {cid: [] for cid in problems}
    for pair in read(out / "per-pair.csv"):
        if pair["id"] in problems:
            pairs[pair["id"]].append(pair)
    for cid, problem in problems.items():
        if len(pairs[cid]) != problem["n_pairs"] or any(
            p["n_starts"] != N_STARTS for p in pairs[cid]
        ):
            raise ValueError(f"incomplete checkpoint for {cid}")
    report = (out / "README.md").read_text()
    started = re.search(r"開始 UTC: ([^。]+)", report).group(1)
    return problems, pairs, started


def csv_row(row):
    return {
        k: json.dumps(v, separators=(",", ":"), allow_nan=False)
        if isinstance(v, list | dict)
        else ""
        if v is None
        else v
        for k, v in row.items()
    }


def write_csv(path, fields, rows):
    # Parent process alone writes the three sol-1 outputs. sol-2 files untouched.
    temporary = path.with_suffix(path.suffix + ".sol1-tmp")
    with temporary.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(csv_row(r) for r in rows)
    temporary.replace(path)


def write_report(out, problems, pairs, elapsed, started, args):
    # Missing central differences must not be encoded as D=-1 (no solution).
    for cid, problem in problems.items():
        for pair in pairs[cid]:
            if pair["found"] and pair["dim"] == -1:
                pair["dim"] = None
        problem["n_pairs_dim_unknown"] = sum(p["found"] and p["dim"] is None for p in pairs[cid])
        problem["n_pairs_all_failed"] = sum(p["n_failed"] == p["n_starts"] for p in pairs[cid])
        dims = [p["dim"] for p in pairs[cid] if p["dim"] is not None and p["dim"] >= 0]
        problem["max_dim"] = max(dims) if dims else None if problem["n_pairs_found"] else -1
    done = list(problems.values())
    rows = [r for cid in sorted(pairs) for r in pairs[cid]]
    write_csv(out / "per-pair.csv", PAIR_FIELDS, rows)
    write_csv(out / "per-problem.csv", PROBLEM_FIELDS, sorted(done, key=lambda r: r["id"]))
    dim_counts = Counter(r["max_dim"] for r in done)
    total = sum(r["n_starts"] for r in done)
    hashes = {}
    for rel in [
        "benchmarks/cases.jsonl",
        "jssa/difficulty/minima/basins-323.csv",
        "jssa/difficulty/ghost-1023/preregistration.md",
        "jssa/difficulty/ghost_exact.py",
    ]:
        path = ROOT / rel
        if path.exists():
            hashes[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    report = f"""# sol-1: 点対の一致を加えた等式系（数値探索）

開始 UTC: {started}。最終更新 UTC: {datetime.now(UTC).isoformat()}。
完了 {len(done)} / {args.expected} 問。実測 wall time {elapsed:.3f} 秒
（{elapsed / 60:.3f} 分）、問題別処理時間の合計 {sum(r["seconds"] for r in done):.3f} 秒。
worker 数 {args.workers}。Python {sys.version.split()[0]}、NumPy {np.__version__}、
SciPy {scipy.__version__}。
完了済み {args.resumed_count} 問を再開時に再利用。
点対を最大 {args.chunk_size} 組ずつ分配する（各点対の乱数・計算条件は不変）。
wall time は初回開始からの経過で、中断・再開の準備と破棄された未完了試行の時間も含む。
問題別secondsは準備と点対処理時間の合計（同じ問題の点対を並列処理した時間は加算）。

## 手順

- 対象は `minima/basins-323.csv` の n_vars >= 1（全体292問）。DSL は `benchmarks/cases.jsonl`。
- 点名は `ghost_scan.point_names` を使い辞書順に並べた0始まりの添字 i,j。
  座標式は `probe_basins.construction_coordinates` から取得。元の等式のIR残差 F に
  座標式の差 x_P-x_Q, y_P-y_Q の2行を追加する。同じ作図を毎回4回評価しないよう、
  これらを1つのIR残差ベクトルにまとめ、既存のfloat評価器で評価する。
  指定の point_names は Area などのスカラー名も返す。その候補名も規則どおり保持し、
  座標を定義できない点対の失敗を隠さず記録する（例: AIME-2006-I-07 の Areg）。
- 過去の記録は cls == hit の x だけを使用し、全hitで常に一致する点対を除く。
  一致判定は既存の `ghost_scan.py` と同じ：距離 < 1e-6 * max(1, 全有限点の原点からの距離の最大値)。
  当たりが無い問題は除外なし。両CSVの has_hits 列で区別する。
- 各残存点対ごとに `np.random.default_rng([0, i, j])`、`infer_problem_bounds` の箱から
  一様乱数で独立な20出発点。見つかった後も20回すべて実行する。終点や過去の乱数出発点を初期値に使わない。
- `scipy.optimize.least_squares(method="lm", max_nfev=100*n, ftol=xtol=gtol=1e-14)`。
  max_nfev は当該SciPy版の既定値と同じ。箱は初期値だけに使い、探索中は無拘束。
  不等式・ガード・hard-feasibility・正解値の条件や罰則は加えない。
  残差行数 < n の場合だけ0行を追加してLMの m>=n 制限に対応（目的関数とランクは不変）。
- 有限な終点の拡張残差のユークリッドノルム <= 1e-10 を found=1 とする。
  best_res は20回の返却終点の最小ノルム（全失敗なら inf）。
  終了ステータスにかかわらずこの残差条件で判定する。
  未定義・非有限値を有限な罰則に置き換えない。LM例外は n_failed/errors、上限停止は n_limit に記録。
- 成功終点で拡張系（0埋め前）の中心差分Jacobianを計算。
  各変数の刻みは 1e-6 * max(1, abs(x_j))、最大特異値の1e-8倍未満を0とし、dim=n-rank。
  最大特異値が0ならrank=0。点対のdimは20回で見つかった成功終点の最大値。
  問題のmax_dimもその最大値。見つからなければ -1。
  次元計算に失敗した場合は n_rank_failed に記録し、その終点の次元を欠測にする。
  found=1 だが全成功終点で次元が計算できなかった点対の dim は空欄。
  問題のmax_dimは有効な次元の最大値（発見があって全次元欠測なら空欄）。
  n_pairs_dim_unknown>0 の問題では max_dim は不完全な観測値として扱う。

## 数値集計（解釈なし）

| 項目 | 値 |
|---|---:|
| 完了問題 | {len(done)} |
| has_hits=0 の問題 | {sum(not r["has_hits"] for r in done)} |
| 除外前の点対 | {sum(r["n_pairs_total"] for r in done)} |
| 全hitで一致するため除外した点対 | {sum(r["n_pairs_excluded"] for r in done)} |
| 調べた点対 | {len(rows)} |
| found=1 の点対 | {sum(r["found"] for r in rows)} |
| G=1 の問題（n_pairs_found>0） | {sum(r["n_pairs_found"] > 0 for r in done)} |
| LM出発点 | {total} |
| LM例外で終点が得られなかった出発点 | {sum(r["n_failed"] for r in done)} |
| max_nfev に達した出発点 | {sum(r["n_limit"] for r in done)} |
| 成功終点の次元計算失敗 | {sum(r["n_rank_failed"] for r in done)} |
| found=1 だが次元がすべて欠測の点対 | {sum(r["n_pairs_dim_unknown"] for r in done)} |
| 全20出発点でLM例外になった点対 | {sum(r["n_pairs_all_failed"] for r in done)} |

max_dim の問題数（None は欠測）: `{dict(sorted(dim_counts.items(), key=lambda kv: str(kv[0])))}`。

## 出力列と限界

`per-pair.csv` の先頭6列は id,P,Q,found,best_res,dim。has_hits と点添字、
試行数・成功数・例外数・上限停止数、0埋め行数を付記する。best_x は最小残差の証人、
dim_x/dim_res/singular_values は最大次元の証人（同次元なら残差最小）、errors は例外内訳。
`per-problem.csv` の先頭7列は id,n_vars,n_pairs,n_pairs_found,max_dim,has_hits,n_hits。
n_pairs は除外後、n_pairs_total は除外前。n_pairs_excluded と実測seconds等を付記する。
status=ok は処理完了を表し、全試行の数値収束を意味しない。
n_pairs_all_failed は全試行が例外になった点対数で、これらの found=0 は探索不能を含む。
LM出発点の集計は保存された本実験の件数で、中断時の未完了試行や小規模検証の重複実行を含まない。

「厳密解あり」はタスク指定の残差閾値による数値判定で、代数的な存在証明ではない。
found=0 は20個の出発点では発見しなかったことだけを表す。
n-rank はその終点での数値的な接空間の次元であり、特異解では局所解集合の次元と一致しない場合がある。
非有限値や差分誤差、尺度の違いによる限界を含む。事前登録H1〜H4の検定や結果の解釈は実施しない。
例として AIME-2007-II-15 の r=4 付近では PointOnSegment の片側が定義域外となり、
指定の中心差分を評価できない。片側差分や別の方程式への置き換えは行わない。

## 再実行

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \\
PYTHONPATH=src /home/kabatan/work/solver/.venv/bin/python \\
  jssa/difficulty/ghost_exact.py --workers {args.workers} --chunk-size {args.chunk_size}
```

`--ids ID ...` で問題を限定、`--out DIR` で別の出力先を指定できる。
`--resume` は既存CSVの完了済み問題を再利用する（計算条件を変えて再開しないこと）。
依存環境の変更、solver本体の変更、commit/pushは行っていない。
sol-2 の per-triple.csv / per-problem-triple.csv には触れない。

入力とコードの SHA-256:

"""
    report += "\n".join(f"- `{name}`: `{digest}`" for name, digest in hashes.items()) + "\n"
    (out / "README.md").write_text(report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--chunk-size", type=int, default=8)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--ids", nargs="+")
    parser.add_argument("--out", type=Path, default=ROOT / "jssa/difficulty/ghost-exact")
    args = parser.parse_args()
    if args.workers < 1 or args.chunk_size < 1:
        parser.error("--workers and --chunk-size must be >= 1")
    with (ROOT / "jssa/difficulty/minima/basins-323.csv").open() as file:
        selected = [r for r in csv.DictReader(file) if int(r["n_vars"]) >= 1]
    if args.ids:
        wanted = set(args.ids)
        selected = [r for r in selected if r["id"] in wanted]
        if {r["id"] for r in selected} != wanted:
            parser.error("unknown id or n_vars=0 in --ids")
    cases = {c["id"]: c for c in map(json.loads, (ROOT / "benchmarks/cases.jsonl").open())}
    args.expected = len(selected)
    args.out.mkdir(parents=True, exist_ok=True)
    began = time.monotonic()
    started = datetime.now(UTC).isoformat()
    problems, pairs = {}, {}
    if args.resume:
        problems, pairs, started = read_checkpoint(args.out)
        if not set(problems) <= {r["id"] for r in selected}:
            parser.error("checkpoint contains problems outside the requested selection")
    args.resumed_count = len(problems)
    previous_seconds = (datetime.now(UTC) - datetime.fromisoformat(started)).total_seconds()
    unfinished = [r for r in selected if r["id"] not in problems]
    meta, indices, seconds, partial = {}, {}, {}, {}
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        prep = {
            pool.submit(prepare_summary, row, cases[row["id"]]): row["id"] for row in unfinished
        }
        for future in as_completed(prep):
            cid = prep[future]
            meta[cid], indices[cid] = future.result()
            seconds[cid], partial[cid] = meta[cid]["prep_seconds"], []
        pending = {}
        for cid in indices:
            if not indices[cid]:
                pairs[cid] = []
                problems[cid] = summarize(meta[cid], [], seconds[cid])
            dsl_json = json.dumps(cases[cid]["dsl"])
            for k in range(0, len(indices[cid]), args.chunk_size):
                job = pool.submit(
                    solve_chunk,
                    cid,
                    dsl_json,
                    indices[cid][k : k + args.chunk_size],
                    meta[cid]["has_hits"],
                )
                pending[job] = cid
        print(
            f"PREPARED {len(unfinished)} problems; {len(pending)} chunks; "
            f"reused {args.resumed_count} completed problems",
            flush=True,
        )
        for future in as_completed(pending):
            cid = pending[future]
            pp, task_seconds = future.result()
            partial[cid].extend(pp)
            seconds[cid] += task_seconds
            if len(partial[cid]) != len(indices[cid]):
                continue
            partial[cid].sort(key=lambda p: (p["i"], p["j"]))
            pairs[cid] = partial.pop(cid)
            problem = summarize(meta[cid], pairs[cid], seconds[cid])
            problems[cid] = problem
            elapsed = previous_seconds + time.monotonic() - began
            write_report(args.out, problems, pairs, elapsed, started, args)
            print(
                f"{len(problems)}/{len(selected)} {cid} pairs={problem['n_pairs']} "
                f"found={problem['n_pairs_found']} dim={problem['max_dim']} "
                f"seconds={problem['seconds']:.1f} wall={elapsed:.1f}",
                flush=True,
            )
    write_report(
        args.out, problems, pairs, previous_seconds + time.monotonic() - began, started, args
    )
    print(
        f"DONE {len(problems)} problems, {sum(len(p) for p in pairs.values())} pairs, "
        f"wall={time.monotonic() - began:.3f}s",
        flush=True,
    )


if __name__ == "__main__":
    main()
