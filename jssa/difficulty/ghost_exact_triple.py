"""Twenty-start equality-only LM search for collinear degeneracies (sol-2).

Only writes per-triple.csv, per-problem-triple.csv and README-triple.md.
Run with the existing solver venv; no dependency installation is needed.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
import csv
from datetime import datetime, timezone
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
# Each worker uses one BLAS thread, including when other experiments are running.
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
import numpy as np
import scipy
from scipy.optimize import least_squares
from mpmath import mp

from geosolver import GeometryProblem
from geosolver.engine.standard.evaluation.ir_evaluator import IREvaluator
from geosolver.engine.standard.evaluation.snapshots import EvaluationStore
from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.problem.ir.schema import IRConstruction
from ghost_scan import point_names
from probe_basins import answer_float, construction_coordinates

TRIPLE_FIELDS = ["id", "P", "Q", "R", "found", "best_res", "dim", "has_hits",
                 "i", "j", "k", "n_starts", "n_found", "n_lm_errors", "n_cap",
                 "n_rank_errors", "nfev", "witness_x", "svals", "best_found_res",
                 "outside_box", "scale_at_witness", "max_scale_seen", "n_inflated_endpoints",
                 "errors"]
PROBLEM_FIELDS = ["id", "n_vars", "n_triples", "n_triples_found", "max_dim", "has_hits",
                  "problem_number", "n_points", "n_all_triples", "n_excluded", "n_eligible",
                  "sampled", "n_hits", "n_coordinate_checks", "coordinate_max_error",
                  "unavailable_points",
                  "n_starts", "n_lm_errors", "n_cap", "n_rank_errors", "nfev", "sec",
                  "hit_diameter", "n_inflated_endpoints", "max_scale_seen", "status", "error"]


class Figure:
    """Same numerical construction kernels as construction_coordinates, shared per x.

    Avoid rebuilding/evaluating two separate bundles per point per LM call.
    All retained coordinates are checked against construction_coordinates at a
    hit or a fresh random point before solving the problem.
    """
    def __init__(self, bundle, names):
        self.bundle = bundle
        self.names = names
        self.store = EvaluationStore(bundle, capacity=16)

    def snapshot(self, x, high_precision=False):
        vals = [mp.mpf(repr(float(v))) if high_precision else mp.mpf(float(v)) for v in x]
        return self.store.get(vals, arithmetic="hp" if high_precision else "float")

    def points(self, x, names=None, high_precision=False):
        names = self.names if names is None else names
        with mp.workdps(30) if high_precision else mp.workprec(53):
            snapshot = self.snapshot(x, high_precision)
            out = {}
            for name in names:
                try:
                    p = snapshot.for_expressions([name])[name]
                    xy = np.array([float(p.x), float(p.y)])
                    if np.isfinite(xy).all():
                        out[name] = xy
                except Exception:
                    pass
            return out

def signed_area(a, b, c):
    u, v = b - a, c - a
    return float((u[0] * v[1] - u[1] * v[0]) / 2)


def augmented_residual(bundle, coords, triple):
    """Use the helper's coordinate expressions in one shared IR evaluation."""
    p, q, r = triple
    ex = {f"{axis}_{nm}": (coords[f"{axis}_{nm}"][1].bundle.spec.answer_expr
                            if f"{axis}_{nm}" in coords else f"Vector(ORIGINZ, {nm}).{axis}")
          for nm in triple for axis in "xy"}
    diff = lambda axis, a, b: f"(({ex[f'{axis}_{a}']})-({ex[f'{axis}_{b}']}))"
    area = f"({diff('x', q, p)}*{diff('y', r, p)}-{diff('y', q, p)}*{diff('x', r, p)})/2"
    spec = replace(bundle.spec,
                   construction=[IRConstruction("ORIGINZ", "Point(0, 0)"), *bundle.spec.construction],
                   constraints=[*bundle.spec.constraints, area],
                   v=[*bundle.targets, 0], m=len(bundle.targets) + 1)
    augmented = replace(bundle, spec=spec, targets=(*bundle.targets, 0))
    evaluator = IREvaluator(augmented, (), EvaluationStore(augmented, capacity=16))
    n = len(bundle.var_names)
    padding = max(0, n - len(augmented.targets))

    def residual(x):
        result = np.asarray(evaluator.evaluate_float_residual(list(map(float, x))).residual_vector)
        if not np.isfinite(result).all():
            raise ValueError("nonfinite augmented residual")
        return np.pad(result, (0, padding)) if padding else result
    return residual


def diameter(pts):
    return max((float(np.linalg.norm(a - b)) for a, b in itertools.combinations(pts.values(), 2)), default=0.)


def rank_dimension(fun, x):
    cols = []
    for j in range(len(x)):
        h = 1e-6 * max(1., abs(x[j]))
        xp, xm = x.copy(), x.copy()
        xp[j] += h
        xm[j] -= h
        cols.append((fun(xp) - fun(xm)) / (2 * h))
    s = np.linalg.svd(np.column_stack(cols), compute_uv=False)
    rank = int(np.count_nonzero(s >= s[0] * 1e-8)) if len(s) and s[0] > 0 else 0
    return len(x) - rank, s.tolist()


def prepare_figures(dsl, bundle, records, names, bounds):
    figure = Figure(bundle, names)
    hit_records = [r for r in records if r.get("cls") == "hit" and "x" in r]
    hits = [figure.points(r["x"], high_precision=True) for r in hit_records]
    # Keep the fixed candidate set. Undefined coordinates fail preprocessing;
    # do not turn an unvalidated problem into a completed search.
    rng = np.random.default_rng(123456)
    probes = [r["x"] for r in hit_records[:1]]
    probes += list(rng.uniform(bounds[:, 0], bounds[:, 1], size=(20, len(bounds))))
    checks, max_error = 0, 0.
    all_coords = {}
    unavailable = []
    for name in names:
        try:
            coords = construction_coordinates(dsl, [name])
        except Exception as error:
            raise ValueError(f"coordinate helper failed: {name}: {error}") from error
        all_coords.update(coords)
        checked = False
        for x in probes:
            points = figure.points(x, [name])
            if name not in points:
                continue
            vals = dict(zip(bundle.var_names, x))
            reference = [answer_float(ev, [vals[n] for n in vn]) for vn, ev in
                         (coords[f"x_{name}"], coords[f"y_{name}"])]
            if any(v is None or not math.isfinite(v) for v in reference):
                continue
            error = float(np.linalg.norm(points[name] - reference) / max(1., np.linalg.norm(reference)))
            if error > 1e-9:
                raise ValueError(f"coordinate mismatch: {name}: {error}")
            checks += 2
            max_error = max(max_error, error)
            checked = True
            break
        if not checked:
            raise ValueError(f"no defined coordinate validation point: {name}")
    return figure, hits, checks, max_error, all_coords, unavailable


def run_problem(task):
    problem_number, row, dsl, starts, max_nfev = task[:5]
    chunk = task[5:] or None
    t0 = time.monotonic()
    cid = row["id"]
    summary = dict.fromkeys(PROBLEM_FIELDS, "")
    summary.update(id=cid, n_vars=int(row["n_vars"]), problem_number=problem_number,
                   n_triples=0, n_triples_found=0, max_dim=-1, n_starts=0,
                   n_lm_errors=0, n_cap=0, n_rank_errors=0, nfev=0, n_inflated_endpoints=0)
    rows = []
    try:
        bundle = load_problem_bundle(GeometryProblem.model_validate(dsl).engine_document())
        n = len(bundle.var_names)
        if n != int(row["n_vars"]):
            raise ValueError(f"n_vars mismatch: {n} != {row['n_vars']}")
        bounds = np.asarray(infer_problem_bounds(bundle), dtype=float)
        records = json.loads((ROOT / "jssa/difficulty/minima/raw-323" / f"{cid}.json").read_text())["records"]
        names = sorted(point_names(dsl))
        summary["n_points"] = len(names)
        summary["n_hits"] = sum(r.get("cls") == "hit" for r in records)
        summary["has_hits"] = int(summary["n_hits"] > 0)
        figure, hits, checks, max_error, coords, unavailable = prepare_figures(dsl, bundle, records, names, bounds)
        summary.update(n_coordinate_checks=checks, coordinate_max_error=max_error,
                       unavailable_points=json.dumps(unavailable, ensure_ascii=False))
        hit_diameters = [diameter(f) for f in hits]
        diam_hit = float(np.median(hit_diameters)) if hits else math.nan
        summary["hit_diameter"] = diam_hit
        all_triples = list(itertools.combinations(range(len(names)), 3))
        eligible = []
        for indices in all_triples:
            triple = tuple(names[i] for i in indices)
            if hits and all(all(nm in f for nm in triple) and
                            abs(signed_area(*(f[nm] for nm in triple))) < 1e-6 * max(1e-300, d) ** 2
                            for f, d in zip(hits, hit_diameters)):
                continue
            eligible.append(indices)
        summary.update(n_all_triples=len(all_triples), n_excluded=len(all_triples) - len(eligible),
                       n_eligible=len(eligible), sampled=int(len(names) > 12 and len(eligible) > 200))
        if summary["sampled"]:
            indices = np.random.default_rng([1, problem_number]).choice(len(eligible), size=200, replace=False)
            eligible = [eligible[i] for i in sorted(indices)]
        if chunk:
            eligible = eligible[chunk[0]:chunk[1]]
        for indices in eligible:
            triple = tuple(names[i] for i in indices)
            rng = np.random.default_rng([0, *indices])
            out = dict.fromkeys(TRIPLE_FIELDS, "")
            out.update(id=cid, P=triple[0], Q=triple[1], R=triple[2], found=0, best_res=math.inf,
                       dim=-1, has_hits=int(bool(hits)), i=indices[0], j=indices[1], k=indices[2],
                       n_starts=0, n_found=0, n_lm_errors=0, n_cap=0, n_rank_errors=0, nfev=0,
                       n_inflated_endpoints=0, max_scale_seen=math.nan)
            errors = Counter()
            scales = []
            fun = augmented_residual(bundle, coords, triple)
            for _ in range(starts):
                x0 = rng.uniform(bounds[:, 0], bounds[:, 1])
                out["n_starts"] += 1
                try:
                    result = least_squares(fun, x0, method="lm", ftol=1e-14, xtol=1e-14,
                                           gtol=1e-14, max_nfev=max_nfev or 100 * n)
                    out["nfev"] += result.nfev
                    out["n_cap"] += result.status == 0
                    res = float(np.linalg.norm(fun(result.x)))
                    out["best_res"] = min(out["best_res"], res)
                    scale = diameter(figure.points(result.x)) / diam_hit if diam_hit > 0 else math.nan
                    if math.isfinite(scale):
                        scales.append(scale)
                        out["n_inflated_endpoints"] += scale > 100
                    if res <= 1e-10:
                        out["found"] = 1
                        out["n_found"] += 1
                        try:
                            dim, svals = rank_dimension(fun, result.x)
                        except Exception as error:
                            out["n_rank_errors"] += 1
                            errors["rank:" + type(error).__name__ + ":" + str(error)[:120]] += 1
                            dim, svals = -1, []
                        # Retain the maximum-dimension witness (then best residual).
                        if not out["witness_x"] or dim > out["dim"] or (dim == out["dim"] and res < out["best_found_res"]):
                            out.update(dim=dim, witness_x=json.dumps(result.x.tolist(), separators=(",", ":")),
                                       svals=json.dumps(svals, separators=(",", ":")), best_found_res=res,
                                       outside_box=int(np.any((result.x < bounds[:, 0]) | (result.x > bounds[:, 1]))),
                                       scale_at_witness=scale)
                except Exception as error:
                    out["n_lm_errors"] += 1
                    errors[type(error).__name__ + ":" + str(error)[:120]] += 1
            out["errors"] = json.dumps(dict(errors), separators=(",", ":")) if errors else ""
            out["max_scale_seen"] = max(scales, default=math.nan)
            rows.append(out)
        summary.update(n_triples=len(rows), n_triples_found=sum(r["found"] for r in rows),
                       max_dim=max((r["dim"] for r in rows), default=-1), status="ok")
        for key in ("n_starts", "n_lm_errors", "n_cap", "n_rank_errors", "nfev", "n_inflated_endpoints"):
            summary[key] = sum(r[key] for r in rows)
        summary["max_scale_seen"] = max((r["max_scale_seen"] for r in rows if math.isfinite(r["max_scale_seen"])), default=math.nan)
    except Exception:
        summary.update(status="error", error=traceback.format_exc(limit=4))
    summary["sec"] = time.monotonic() - t0
    return rows, summary


def triple_key(row):
    """Reject incomplete records explicitly, before sorting or rewriting output."""
    try:
        indices = tuple(int(row[k]) for k in ("i", "j", "k"))
        if not 0 <= indices[0] < indices[1] < indices[2]:
            raise ValueError("indices must satisfy 0 <= i < j < k")
        return (row["id"], *indices)
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"invalid triple indices for {row.get('id')!r}") from error


def read_checkpoint_table(path, fields, audit):
    """Quarantine structurally damaged rows; never fabricate missing indices."""
    table = []
    with path.open(newline="") as f:
        reader = csv.reader(f)
        if next(reader, None) != fields:
            raise ValueError(f"unexpected checkpoint header: {path}")
        for values in reader:
            if len(values) != len(fields) or any("\0" in v for v in values):
                audit[f"{path.name}:malformed_rows"] += 1
                continue
            table.append(dict(zip(fields, values)))
    return table


def completed_checkpoint(directory, tasks, starts, audit):
    """Retain only complete, validated problems; retry inconsistent ones."""
    previous = read_checkpoint_table(directory / "per-problem-triple.csv", PROBLEM_FIELDS, audit)
    triples = read_checkpoint_table(directory / "per-triple.csv", TRIPLE_FIELDS, audit)
    wanted = {t[1]["id"] for t in tasks}
    by_id, seen, invalid = {}, {}, set()
    for row in triples:
        if row["id"] not in wanted:
            continue
        try:
            key = triple_key(row)
        except ValueError:
            invalid.add(row["id"])
            audit["invalid_index_rows"] += 1
            continue
        if key in seen:
            if row != seen[key]:
                invalid.add(row["id"])
            else:
                audit["identical_duplicate_triples"] += 1
            continue
        seen[key] = row
        by_id.setdefault(row["id"], []).append(row)
    summaries, rows, retried = [], [], []
    unique = {}
    for s in previous:
        cid = s["id"]
        if cid not in wanted:
            continue
        if cid in unique:
            audit["duplicate_summaries"] += 1
            if unique[cid] != s:
                invalid.add(cid)
        unique[cid] = s
    for cid, s in unique.items():
        rr = by_id.get(cid, [])
        try:
            valid = s["status"] == "ok" and cid not in invalid
            valid &= not bool(json.loads(s.get("unavailable_points") or "[]"))
            valid &= len(rr) == int(s["n_triples"])
            valid &= all(int(r["n_starts"]) == starts for r in rr)
            valid &= sum(int(r["found"]) for r in rr) == int(s["n_triples_found"])
            valid &= max((int(r["dim"]) for r in rr), default=-1) == int(s["max_dim"])
            for k in ("n_starts", "n_lm_errors", "n_cap", "n_rank_errors", "nfev", "n_inflated_endpoints"):
                valid &= sum(int(r[k]) for r in rr) == int(s[k])
        except (ValueError, TypeError, KeyError):
            valid = False
        if valid:
            summaries.append(s)
            rows.extend(rr)
        else:
            retried.append(cid)
    return summaries, rows, sorted(retried)


def write_readme(out, args, summaries, elapsed, started):
    ok = [s for s in summaries if s["status"] == "ok"]
    errors = [s for s in summaries if s["status"] != "ok"]
    counts = Counter(s["status"] for s in summaries)
    total_sec = sum(float(s["sec"]) for s in summaries)
    command = (f"PYTHONDONTWRITEBYTECODE=1 {sys.executable} jssa/difficulty/ghost_exact_triple.py"
               f" --workers {args.workers} --chunk-size {args.chunk_size} --starts {args.starts}"
               f" --out {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    if args.resume:
        command += " --resume"
    if args.ids:
        command += " --ids " + " ".join(args.ids)
    if args.max_nfev:
        command += f" --max-nfev {args.max_nfev}"
    if args.import_completed:
        command += f" --import-completed {args.import_completed}"
    text = f"""# sol-2: 3点の共線退化の独立探索

実行開始（UTC）: {started}。
今回の実行 wall time: {elapsed:.3f} 秒（入力読込・チェックポイント検証・再計算・CSV最終整列まで）。
保持した正常完了: {args.retained_count} 問、今回再試行/新規処理: {args.recomputed_count} 問。
問題別secの合計: {total_sec:.3f} 秒（保持分 {args.retained_sec:.3f} 秒、今回分 {total_sec - args.retained_sec:.3f} 秒）。
secは各問題の全chunkの処理時間の合計で、重複する座標前処理も含む。並列実行のwall timeやCPU時間とは異なる。
旧READMEの実行開始UTC: {args.original_started}。旧READMEには初回wall time 4245.173秒の記録があるが、その後の再開・停止・待機を含む全セッションの実稼働wall timeは復元できない。旧開始UTCから現在までの経過を実稼働時間とは呼ばない。
Python: `{sys.executable}`、NumPy {np.__version__}、SciPy {scipy.__version__}。
今回のworker数: {args.workers}（BLASは各1 thread）、chunk-size: {args.chunk_size}。

```bash
{command}
```

## 固定した手順

- 対象は `minima/basins-323.csv` の n_vars >= 1 の292問。問題番号は全行の0始まり位置。DSLは `benchmarks/cases.jsonl`。対象・閾値・乱数・出発点数を結果に応じて変えない。
- `ghost_scan.point_names` の返り値を辞書順に使用。一部の非点作図名も候補集合に残す。全候補名の座標を `construction_coordinates` / `answer_float` と比較し、相対誤差1e-9以下を検証する。検証には最初のhitと `default_rng(123456)` の20ランダム点を使う。座標を検証できない問題は `error` とし、名前や組を削除して通さない。
- raw-323 records の cls=hit だけを参照し、全正解図で abs(符号付き面積) < 1e-6 * 図の直径^2 の組を除外。正解図なしは除外なし、has_hits=0。非正解終点は参照しない。
- 12点超で適格組が200超なら `default_rng([1, 問題番号])` で非復元抽出200組。
- 各組(i,j,k)の `default_rng([0,i,j,k])` から探索箱 `infer_problem_bounds` 内の一様乱数{args.starts}出発点。元の未正規化の等式Fに `(Q-P)×(R-P)/2` を1行追加。不等式・ガード・箱外罰則なし。LM自体は箱に制限されない。
- `least_squares(method='lm', ftol=xtol=gtol=1e-14, max_nfev={args.max_nfev or '100*n_vars'})`。m<nなら0行でパディング。評価不能/非有限の出発点はLM例外に数え、別解法に置換しない。成功しても全出発点を処理する。
- found=1は終点の拡張残差L2ノルム <= 1e-10。LM終了statusによらず残差で判定。best_resは返った終点の最小残差（全例外ならinf）。
- 成功終点で中心差分 h_j=1e-6*max(1,abs(u_j))、特異値が最大値の1e-8倍未満なら0。全特異値0ならrank=0。dim=n-rankの最大値と証人・特異値を保存。成功なしはdim=-1、次元評価失敗はn_rank_errors。
- scaleは図の直径/正解図直径の中央値。100超の終点を膨張として補助集計。正解図なしはnan。無限遠の解の存在検証ではない。
- chunkは負荷分散だけに使用。`--resume`はCSVの構造・組の一意性・出発点数・問題別集計の一致と座標検証済みを確認した完了問題を保持し、不整合・未完了・errorは問題単位で再試行する。

## 結果

- 処理済み問題数: {len(summaries)} / 292、status: {dict(counts)}。errorも処理済みだが探索成功とは数えない。
- 正常処理の has_hits=0: {sum(int(s['has_hits']) == 0 for s in ok)}。
- 探索3点組: {sum(int(s['n_triples']) for s in ok)}、found組: {sum(int(s['n_triples_found']) for s in ok)}。
- G3=1の問題（found組が1以上）: {sum(int(s['n_triples_found']) > 0 for s in ok)}、最大D3: {max((int(s['max_dim']) for s in ok), default=-1)}。
- LM出発点: {sum(int(s['n_starts']) for s in ok)}、LM例外: {sum(int(s['n_lm_errors']) for s in ok)}、max_nfev到達: {sum(int(s['n_cap']) for s in ok)}、次元評価例外: {sum(int(s['n_rank_errors']) for s in ok)}。
- 前処理等の失敗: {len(errors)}問。下表は最終例外理由、完全なtracebackは `per-problem-triple.csv` のerror列。

| id | status | 理由 |
| --- | --- | --- |
"""
    for s in errors:
        reason = s['error'].strip().splitlines()[-1] if s['error'].strip() else '理由未記録'
        text += f"| {s['id']} | {s['status']} | {reason.replace('|', '/')} |\n"
    text += f"""
## 引き継ぎ時の不整合と修復

`/tmp/ghost-triple-resume.log` の最後は最終整列時の `int(None)` TypeErrorだった。
引き継ぎCSVを変更前に `.before-resume` へ保存した。問題CSVには正常な27列の292行に加え、26列の53行とNULバイトが混入。組CSVには完全一致する重複行があった。混入の発生原因は特定していない。
引き継いだコードは未検証座標をunavailable_pointsへ記録して処理を続けていたため、今回の指定に従い前処理失敗へ戻した。該当問題の旧okは保持せず再試行した。
不足するi,j,kに仮値を入れることはせず、構造不正行を隔離、完全一致する組行だけ重複除去し、問題別集計が一致した結果を保持した。不整合な問題は再試行対象にする。最終整列は検証済み整数キーを使う。

今回のチェックポイント検査件数: `{dict(args.audit)}`。
再試行対象として検出した既存問題: {args.retried}。
別ディレクトリから取り込んだ完了問題: {args.imported}。

## 出力と限界

- `per-triple.csv`: 組ごとの結果、成功・例外・打ち切り件数、証人、尺度。
- `per-problem-triple.csv`: 問題ごとの集計、除外・標本化・座標検証・所要時間、error理由。
- `README-triple.md`: 手順、集計、実行時間、修復履歴。

sol-2は符号付き面積0を探索するため、3点共線（点の一致も含む）が対象であり、3点すべての同一点への一致だけを数えた実験ではない。
有限回の局所探索なのでfound=0は不存在の証明ではない。found=1も1e-10の数値判定であり代数的厳密証明ではない。n-rankは特異点で真の次元を過大評価しうる。ガード違反や箱外の証人も含む。status=okは処理完了を意味し、各出発点の収束を保証しない。error問題のG3/D3は未測定。H1〜H4の予測検定は実施していない。

入力とコードの SHA-256:

"""
    for rel in ("benchmarks/cases.jsonl", "jssa/difficulty/minima/basins-323.csv",
                "jssa/difficulty/ghost-1023/preregistration.md", "jssa/difficulty/ghost_exact_triple.py"):
        text += f"- `{rel}`: `{hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()}`\n"
    (out / "README-triple.md").write_text(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=ROOT / "jssa/difficulty/ghost-exact")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--starts", type=int, default=20)
    ap.add_argument("--max-nfev", type=int, default=0)
    ap.add_argument("--chunk-size", type=int, default=40, help="triples per job; 0 means one job per problem")
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--resume", action="store_true", help="keep completed problems and retry missing/error rows")
    ap.add_argument("--import-completed", type=Path, help="with --resume, import completed problems from a separate output directory")
    args = ap.parse_args()
    if args.starts < 1 or args.workers < 1 or args.max_nfev < 0 or args.chunk_size < 0:
        ap.error("starts/workers must be positive and max-nfev/chunk-size must be nonnegative")
    if args.import_completed and not args.resume:
        ap.error("--import-completed requires --resume")
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()
    cases = {c["id"]: c["dsl"] for c in map(json.loads, (ROOT / "benchmarks/cases.jsonl").open())}
    with (ROOT / "jssa/difficulty/minima/basins-323.csv").open() as f:
        tasks = [(i, r, cases[r["id"]], args.starts, args.max_nfev) for i, r in enumerate(csv.DictReader(f))
                 if int(r.get("n_vars") or 0) >= 1 and (not args.ids or r["id"] in args.ids)]
    if args.ids and {t[1]["id"] for t in tasks} != set(args.ids):
        ap.error("unknown id or n_vars=0 in --ids")
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    summaries, retained_rows = [], []
    args.retried = []
    args.imported = []
    args.audit = Counter()
    args.original_started = "なし"
    if args.resume and (out / "per-problem-triple.csv").exists():
        summaries, retained_rows, args.retried = completed_checkpoint(out, tasks, args.starts, args.audit)
        completed = {s["id"] for s in summaries}
        tasks = [t for t in tasks if t[1]["id"] not in completed]
        if (out / "README-triple.md").exists():
            old = (out / "README-triple.md").read_text()
            match = re.search(r"実行開始（UTC）: ([^。]+)", old)
            args.original_started = match[1] if match else "不明"
    if args.import_completed:
        imported, import_rows, _ = completed_checkpoint(args.import_completed, tasks, args.starts, args.audit)
        summaries.extend(imported)
        retained_rows.extend(import_rows)
        args.imported = sorted(s["id"] for s in imported)
        tasks = [t for t in tasks if t[1]["id"] not in set(args.imported)]
    args.retained_count = len(summaries)
    args.recomputed_count = len(tasks)
    args.retained_sec = sum(float(s["sec"]) for s in summaries)
    print(json.dumps({"retained": args.retained_count, "retry_or_missing": len(tasks),
                      "checkpoint_audit": dict(args.audit)}, ensure_ascii=False), flush=True)
    with (out / "per-triple.csv").open("w", newline="") as ft, (out / "per-problem-triple.csv").open("w", newline="") as fp:
        tw, pw = csv.DictWriter(ft, TRIPLE_FIELDS), csv.DictWriter(fp, PROBLEM_FIELDS)
        tw.writeheader()
        pw.writeheader()
        tw.writerows(retained_rows)
        pw.writerows(summaries)
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures, remaining, chunks = {}, Counter(), {}
            for task in tasks:
                cid = task[1]["id"]
                num_names = len(point_names(task[2]))
                upper = math.comb(num_names, 3) if num_names >= 3 else 0
                if num_names > 12:
                    upper = min(upper, 200)
                slices = [(0, upper)] if not args.chunk_size else [
                    (k, k + args.chunk_size) for k in range(0, max(1, upper), args.chunk_size)]
                for start, end in slices:
                    future = pool.submit(run_problem, (*task, start, end))
                    futures[future] = cid
                    remaining[cid] += 1
                chunks[cid] = []
            for future in as_completed(futures):
                rows, summary = future.result()
                cid = futures[future]
                chunks[cid].append((rows, summary))
                remaining[cid] -= 1
                if remaining[cid]:
                    continue
                parts = chunks.pop(cid)
                rows = [r for rr, _ in parts for r in rr]
                rows.sort(key=lambda r: (r["i"], r["j"], r["k"]))
                summary = dict(parts[0][1])
                for key in ("n_triples", "n_triples_found", "n_starts", "n_lm_errors", "n_cap", "n_rank_errors", "nfev", "n_inflated_endpoints", "sec"):
                    summary[key] = sum(s[key] for _, s in parts)
                summary["max_dim"] = max(s["max_dim"] for _, s in parts)
                summary["max_scale_seen"] = max((s["max_scale_seen"] for _, s in parts
                                                  if isinstance(s["max_scale_seen"], (int, float)) and math.isfinite(s["max_scale_seen"])), default=math.nan)
                failures = [s["error"] for _, s in parts if s["status"] != "ok"]
                if failures:
                    summary.update(status="error", error="\n".join(sorted(set(failures))))
                tw.writerows(rows)
                pw.writerow(summary)
                ft.flush()
                fp.flush()
                summaries.append(summary)
                print(json.dumps(summary, ensure_ascii=False), flush=True)
    # Completion order depends on scheduling; deliver tables in fixed order.
    final_rows = read_checkpoint_table(out / "per-triple.csv", TRIPLE_FIELDS, Counter())
    final_rows.sort(key=triple_key)
    summaries.sort(key=lambda r: int(r["problem_number"]))
    for path, fields, table in ((out / "per-triple.csv", TRIPLE_FIELDS, final_rows),
                                (out / "per-problem-triple.csv", PROBLEM_FIELDS, summaries)):
        with path.open("w", newline="") as f:
            w = csv.DictWriter(f, fields)
            w.writeheader()
            w.writerows(table)
    elapsed = time.monotonic() - t0
    write_readme(out, args, summaries, elapsed, started)
    print(json.dumps({"elapsed_sec": elapsed, "problems": len(summaries), "errors": sum(s["status"] != "ok" for s in summaries)}), flush=True)
    return int(any(s["status"] != "ok" for s in summaries))


if __name__ == "__main__":
    raise SystemExit(main())
