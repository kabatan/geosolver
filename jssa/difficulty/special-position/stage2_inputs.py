"""Q42: arithmetic on sealed inputs only; no solver/evaluator imports."""
from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
Q22 = ROOT / "jssa/strategy/astra-consult-18/q22a-hidden-coincidence"
STRUCT = ("n_vars", "n_eq", "n_ineq", "n_pts", "n_circ", "dsl_len", "has_angle", "has_tangent")
TOLS = ("1e-08", "1e-07", "1e-06")
KINDS = ("equal_length", "collinear", "concyclic")


def finite(x):
    try:
        return x is not None and x != "" and math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def integer(x):
    return finite(x) and float(x) >= 0 and float(x).is_integer()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(name, data):
    content = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    assert len(content.encode()) <= 5_000_000
    (HERE / name).write_text(content, encoding="utf-8")


def write_csv(name, rows):
    import io
    stream = io.StringIO(newline="")
    keys = list(dict.fromkeys(k for row in rows for k in row))
    writer = csv.DictWriter(stream, fieldnames=keys)
    writer.writeheader()
    writer.writerows(rows)
    content = stream.getvalue()
    assert len(content.encode()) <= 5_000_000
    (HERE / name).write_text(content, encoding="utf-8", newline="")


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def unique_index(rows, key, label, errors):
    counts = Counter(r[key] for r in rows)
    for cid, n in counts.items():
        if n != 1:
            errors.append(f"{label}: duplicate exact ID {cid}: {n}")
    return {r[key]: r for r in rows}


def structure_depth(dsl):
    # Same lexical dependency rule as the sealed Q22a structure(), without import.
    expressions = {c["name"]: c["expression"] for c in dsl["constructions"]}
    if len(expressions) != len(dsl["constructions"]):
        raise ValueError("duplicate construction name")
    names = set(expressions)
    deps = {n: (set(re.findall(r"(?<![\w.])[A-Za-z_]\w*", e)) & names) - {n}
            for n, e in expressions.items()}
    depth = {}

    def get(n, stack=frozenset()):
        if n in stack:
            raise ValueError("cyclic construction")
        if n not in depth:
            depth[n] = 1 + max((get(q, stack | {n}) for q in deps[n]), default=0)
        return depth[n]

    for n in expressions:
        get(n)
    return max(depth.values(), default=0)


def read_probe(cid, seed, basin, errors):
    directory = "raw-323" if seed == 0 else "raw-323-seed1"
    path = ROOT / "jssa/difficulty/minima" / directory / f"{cid}.json"
    out = {"raw_present": path.exists(), "p_reason": "raw_file_absent", "S_reason": "raw_file_absent"}
    branch_rows = []
    if not path.exists():
        return out, branch_rows
    raw = json.loads(path.read_text())
    if raw.get("case_id") != cid or raw.get("seed") != seed:
        errors.append(f"{cid}/seed{seed}: ID or seed mismatch")
    n = raw.get("n_vars")
    if not integer(n) or n != int(basin["n_vars"]):
        errors.append(f"{cid}/seed{seed}: n_vars mismatch")
        return out, branch_rows
    refs = raw.get("references")
    if not isinstance(refs, list):
        errors.append(f"{cid}/seed{seed}: references absent")
        return out, branch_rows
    out.update(n_vars=n, n_refs=len(refs), raw_status=raw.get("status"))
    N = raw.get("starts_requested")
    if not integer(N) or N <= 0:
        errors.append(f"{cid}/seed{seed}: invalid starts_requested")
        return out, branch_rows
    out["starts_requested"] = N
    if n == 0:
        out.update(p_reason="n_vars_0_no_search", S_reason="n_vars_0", dimension="n0")
        if raw.get("status") != "no_variables":
            errors.append(f"{cid}/seed{seed}: unexpected zero-variable status")
        if seed == 0 and (basin["p"] or basin["n_starts"]):
            errors.append(f"{cid}: zero-variable basins p/start should be blank")
        return out, branch_rows
    records = raw.get("records")
    if not isinstance(records, list):
        errors.append(f"{cid}/seed{seed}: records absent")
        return out, branch_rows
    h = sum(r.get("cls") == "hit" for r in records)
    ks = [r.get("k") for r in records]
    if (raw.get("starts_done") != len(records) or len(set(ks)) != len(records)
            or not all(integer(k) and k < N for k in ks) or not h <= len(records) <= N):
        errors.append(f"{cid}/seed{seed}: starts_done/k/count inconsistency")
    p_completed = h / len(records) if records else None
    if seed == 0:
        if not integer(basin["n_starts"]) or int(basin["n_starts"]) != len(records):
            errors.append(f"{cid}: basins n_starts mismatch")
        if not finite(basin["p"]) or p_completed is None or abs(float(basin["p"]) - p_completed) > 1e-12:
            errors.append(f"{cid}: basins p mismatch")
    if Counter(r.get("cls") for r in records) != Counter(raw.get("counts", {})):
        errors.append(f"{cid}/seed{seed}: counts mismatch")
    out.update(p=h / N, p_completed=p_completed, p_reason="observed", hits=h,
               starts_done=len(records), missing_starts=N - len(records),
               incomplete=len(records) < N, non_success=N - h)
    for kind in ("hit", "wrong_answer", "wrong_branch", "stuck", "left_box", "error", "timeout"):
        out[f"count_{kind}"] = sum(r.get("cls") == kind for r in records)
    for key in ("nfev", "sec"):
        values = [float(r[key]) for r in records if finite(r.get(key)) and float(r[key]) >= 0]
        out[f"{key}_recorded"] = len(values)
        out[f"{key}_missing_record"] = len(records) - len(values)
        out[f"{key}_missing_planned"] = N - len(values)
        out[f"{key}_coverage"] = len(values) / N
        out[f"{key}_median"] = median(values) if values else None
    first = raw.get("first_hit", {})
    hit_refs = {str(r["ref"]) for r in records if r.get("cls") == "hit"}
    if set(first) != hit_refs:
        errors.append(f"{cid}/seed{seed}: first_hit/ref mismatch")
    for key, b in first.items():
        if not key.isdigit() or not 0 <= int(key) < len(refs):
            errors.append(f"{cid}/seed{seed}: invalid first_hit reference {key}")
            continue
        matching = [r for r in records if r.get("cls") == "hit" and r.get("ref") == int(key)]
        if not matching or b.get("k") != min(r["k"] for r in matching):
            errors.append(f"{cid}/seed{seed}: first_hit k mismatch")
        m, sv = b.get("n_residuals"), b.get("svals")
        valid = integer(m) and isinstance(sv, list) and len(sv) == min(m, n) and all(finite(v) and v >= 0 for v in sv)
        br = dict(id=cid, seed=seed, ref=int(key), n=n, m=m, valid_svals=bool(valid),
                  svals_json=json.dumps(sv), observed_k=b.get("k"))
        if valid and sv:
            lo, hi = min(sv), max(sv)
            ratio = lo / hi if hi > 0 else None
            br.update(sigma_min=lo, sigma_max=hi, r=ratio, all_zero=hi == 0,
                      S=12.0 if hi == 0 else -math.log10(max(ratio, 1e-12)),
                      S_raw=-math.log10(max(lo, 1e-300)),
                      rank_defect=n - sum(v > 1e-8 * hi for v in sv))
        branch_rows.append(br)
    out.update(branches_observed=len(first), branches_valid=sum(b["valid_svals"] for b in branch_rows),
               refs_unobserved=len(refs) - len(first), all_refs_saved=len(first) == len(refs),
               any_zero_J=any(b.get("all_zero", False) for b in branch_rows))
    ms = {b["m"] for b in branch_rows if integer(b["m"])}
    out["m"] = next(iter(ms)) if len(ms) == 1 else None
    if len(ms) > 1:
        errors.append(f"{cid}/seed{seed}: branch equality-row counts differ")
    valid_branches = [b for b in branch_rows if b.get("S") is not None and b["valid_svals"]]
    if valid_branches:
        for key in ("sigma_min", "sigma_max", "S_raw", "rank_defect"):
            out[key] = median(b[key] for b in valid_branches)
        out["S_branch_min"] = min(b["S"] for b in valid_branches)
        out["S_branch_max"] = max(b["S"] for b in valid_branches)
        out["S_branch_range"] = out["S_branch_max"] - out["S_branch_min"]
    if n == 1:
        reason = "n_vars_1_separate"
    elif not first:
        reason = "no_first_hit_m_unknown"
    elif out["m"] is not None and out["m"] < n:
        reason = "m_less_than_n"
    elif len(valid_branches) != len(first) or out["m"] is None:
        reason = "invalid_saved_svals"
    else:
        reason = "observed"
        out["S"] = median(b["S"] for b in valid_branches)
    out.update(S_reason=reason, dimension=reason)
    return out, branch_rows


def geometry(cid, row, errors):
    out = {"G_reason": "not_in_Q22a_human_subset"}
    if row is None:
        return out
    out["Q22_status"] = row["status"]
    if row["status"] != "ok":
        out["G_reason"] = "Q22a_" + row["status"]
        return out
    keys = ("accepted_figures", "measured_points", "measured_circles")
    if not all(integer(row.get(k)) for k in keys) or float(row["accepted_figures"]) < 1:
        out["G_reason"] = "invalid_geometry_counts"
        return out
    path = Q22 / "figures" / f"{cid}.json"
    if not path.exists():
        out["G_reason"] = "figure_file_absent"
        return out
    fig = json.loads(path.read_text())
    q, nc = int(float(row["measured_points"])), int(float(row["measured_circles"]))
    if (fig["id"] != cid or q != len(fig.get("points", {})) or nc != len(fig.get("circles", {}))
            or len(fig.get("saved_coordinates", [])) != int(float(row["accepted_figures"]))):
        errors.append(f"{cid}: Q22 figure/count mismatch")
    candidates = dict(equal_length=math.comb(math.comb(q, 2), 2), collinear=math.comb(q, 3),
                      concyclic=math.comb(q, 4), tangent=math.comb(q, 2)*nc + math.comb(nc, 2))
    out.update(measured_points=q, measured_circles=nc, accepted_figures=int(float(row["accepted_figures"])))
    for kind, M in candidates.items():
        out[f"candidates_{kind}"] = M
    valid = True
    for tol in TOLS:
        for prefix in ("hidden", "raw"):
            densities = []
            for kind in (*KINDS, "tangent"):
                key = f"{prefix}_{kind}_{tol}"
                value = row.get(key)
                if not integer(value) or float(value) > candidates[kind]:
                    valid = False
                    continue
                count = int(float(value))
                # Count sealed max_error entries, preserving Q22a's shared-figure definition.
                saved = sum(f["kind"] == kind and finite(f.get("max_error"))
                            and float(f["max_error"]) <= float(tol)
                            and (prefix == "raw" or f["explicit"] is False) for f in fig["predicates"])
                if saved != count:
                    errors.append(f"{cid}: saved max_error/count mismatch: {key}")
                out[key] = count
                density = count / max(1, candidates[kind])
                if kind == "tangent":
                    out[f"tangent_{prefix}_{tol}"] = density
                else:
                    densities.append(math.log1p(1000 * density))
            if valid and len(densities) == 3:
                out[f"G_{prefix}_{tol}"] = sum(densities) / 3
    out["G_reason"] = "observed" if valid else "invalid_geometry_counts"
    if valid:
        out["G"] = out["G_hidden_1e-07"]
    points = list(fig.get("points", {}).values())
    if not all(len(p) == 2 and all(finite(x) for x in p) for p in points):
        out["right_angle_reason"] = "invalid_saved_points"
        return out
    out["right_angle_reason"] = "first_saved_figure_only"
    out["candidates_right_angle"] = q * math.comb(q - 1, 2) if q else 0
    counts = dict.fromkeys(TOLS, 0)
    valid_pairs = 0
    for b in range(q):
        for a, c in itertools.combinations([i for i in range(q) if i != b], 2):
            u = [points[a][j] - points[b][j] for j in (0, 1)]
            v = [points[c][j] - points[b][j] for j in (0, 1)]
            u2, v2 = sum(t*t for t in u), sum(t*t for t in v)
            if u2 <= 1e-12 or v2 <= 1e-12:
                continue
            valid_pairs += 1
            cosine = abs(sum(x*y for x, y in zip(u, v))) / math.sqrt(u2*v2)
            for tol in TOLS:
                counts[tol] += cosine <= float(tol)
    out["right_angle_valid_candidates"] = valid_pairs
    for tol, count in counts.items():
        out[f"right_angle_count_{tol}"] = count
        out[f"right_angle_{tol}"] = count / max(1, out["candidates_right_angle"])
    return out


def build():
    # Read-only verification of all original hashes before accessing values.
    verification = subprocess.run([sys.executable, "-B", str(HERE / "seal_prediction.py"), "--verify"],
                                  cwd=ROOT, capture_output=True, text=True, check=True)
    errors, branches, rows = [], [], []
    basins = read_csv(ROOT / "jssa/difficulty/minima/basins-323.csv")
    bidx = unique_index(basins, "id", "basins", errors)
    human = unique_index(read_csv(ROOT / "jssa/difficulty/ghost-1023/human_feat.csv"), "case_id", "human", errors)
    q22 = unique_index(read_csv(Q22 / "features.csv"), "id", "Q22a", errors)
    cases = unique_index([json.loads(line) for line in (ROOT / "benchmarks/cases.jsonl").read_text().splitlines() if line],
                         "id", "cases", errors)
    if len(basins) != 323:
        errors.append(f"population {len(basins)} != 323")
    for cid in set(human) | set(q22):
        if cid not in bidx:
            errors.append(f"auxiliary ID outside population: {cid}")
    for basin in basins:
        cid = basin["id"]
        h, q, case = human.get(cid), q22.get(cid), cases.get(cid)
        row = dict(id=cid, n_vars=int(basin["n_vars"]), H=None, G=None, S=None)
        if q and q.get("case_id") != cid:
            errors.append(f"{cid}: Q22a id/case_id mismatch")
        for key in STRUCT:
            hv, qv = (h or {}).get(key), (q or {}).get(key)
            if finite(hv) and finite(qv) and float(hv) != float(qv):
                errors.append(f"{cid}: human/Q22 structure mismatch: {key}")
            val = hv if finite(hv) else qv
            row[key] = int(float(val)) if integer(val) else None
        if row["n_vars"] != int(basin["n_vars"]):
            errors.append(f"{cid}: human/basins n_vars mismatch")
        # IDs are never uppercased/merged. Only contest labels have this explicit spelling map.
        prefix = cid.split("-")[0]
        contest = {"AIME": "AIME", "aime": "AIME", "HMMT": "HMMT", "JMO": "JMO"}.get(prefix)
        row["contest"] = (h or {}).get("contest") or (q or {}).get("contest")
        if not contest or row["contest"] != contest or (q and q["contest"] != contest):
            errors.append(f"{cid}: contest mismatch")
        row["year"] = int(cid.split("-")[1])
        if q and integer(q.get("year")) and int(float(q["year"])) != row["year"]:
            errors.append(f"{cid}: year mismatch")
        row["H"] = float(h["human"]) if h and finite(h.get("human")) else None
        row["H_reason"] = "observed" if row["H"] is not None else "human_blank"
        if case is None:
            errors.append(f"{cid}: case absent")
        else:
            if case["dsl"].get("id") != cid:
                errors.append(f"{cid}: case/dsl ID mismatch")
            try:
                row["construction_depth"] = structure_depth(case["dsl"])
                row["depth_reason"] = "observed_static_DSL"
            except ValueError as exc:
                row["construction_depth"] = None
                row["depth_reason"] = str(exc)
            if q and finite(q.get("construction_depth")) and row["construction_depth"] != int(float(q["construction_depth"])):
                errors.append(f"{cid}: construction_depth mismatch")
        for seed in (0, 1):
            probe, br = read_probe(cid, seed, basin, errors)
            branches.extend(br)
            row.update({f"{k}{seed}": v for k, v in probe.items()})
        if row.get("n_refs0") != row.get("n_refs1"):
            errors.append(f"{cid}: reference counts differ between seeds")
        row["n_refs"] = row.get("n_refs0")
        row["S"] = row.get("S0")
        row["p"] = row.get("p0")
        row["p_basins"] = float(basin["p"]) if finite(basin["p"]) else None
        row.update(geometry(cid, q, errors))
        control_keys = (*STRUCT, "contest", "year", "construction_depth", "n_refs")
        row["X_missing"] = ";".join(k for k in control_keys if row.get(k) is None)
        row["X_complete"] = not row["X_missing"]
        row["known_dimension_eligible"] = row["n_vars"] >= 2 and row.get("m0") is not None and row["m0"] >= row["n_vars"]
        row["P1_available"] = row["X_complete"] and row["G"] is not None and row["S"] is not None
        row["P2_available"] = row["X_complete"] and row["S"] is not None and row["p"] is not None
        row["P34_available"] = row["P1_available"] and row["p"] is not None and row["H"] is not None
        rows.append(row)
    audit = dict(utc=datetime.now(timezone.utc).isoformat(), authorization=dict(
        source="user message: commit/push completed and stage2 authorized", commit="65627f72b0b91817ae3bd056a03fdc6255fe9f19",
        user_reported_push_utc="2026-10-23T17:33:25Z"), lock_verified=True,
        verification_stdout=verification.stdout.strip(), population=len(rows), errors=errors,
        new_solver_runs=0, new_searches=0, new_refinements=0, new_jacobian_evaluations=0,
        fixed_input_count=len(json.loads((HERE / "input-manifest.json").read_text())["files"]),
        prediction_sha256=digest(HERE / "prediction.md"), prediction_lock_sha256=digest(HERE / "prediction.lock.json"),
        coverage={key: dict(Counter(str(r.get(key)) for r in rows)) for key in
                  ("G_reason", "H_reason", "S_reason0", "S_reason1", "X_missing", "P1_available", "P2_available", "P34_available")},
        conventions=dict(ids="exact original case-sensitive strings; no normalization or fuzzy joins",
                         contest="existing contest; explicit ID-prefix spellings aime/AIME both denote AIME, without changing IDs",
                         equality_rows="m is saved n_residuals, not structural n_eq; missing m is not imputed",
                         human="fixed human values/direction; prior E and J source-join audit consulted as provenance only"))
    write_csv("ledger.csv", rows)
    write_csv("branches.csv", branches)
    write_json("input-audit.json", audit)
    print(json.dumps({"errors": errors, "coverage": audit["coverage"]}, ensure_ascii=False), flush=True)
    return rows, audit


if __name__ == "__main__":
    _, audit = build()
    if audit["errors"]:
        raise SystemExit("Input inconsistency: do not run association analysis")
