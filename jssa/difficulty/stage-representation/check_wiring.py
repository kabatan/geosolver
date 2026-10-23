"""Reference-free pre-search checks; no optimization or refinement run."""
import math
from collections import Counter
from pathlib import Path
import tempfile
import time
import diagnostic as d
import execute_stage2 as ex


def main():
    ex.verify_lock()
    results = []
    checked = set()
    for identifier, row in d.selected().items():
        prep = d.read(d.OUT / "prepared" / f"{identifier}.json")
        assert prep["mapping"]["status"] == "verified"
        if row["stratum"] in checked:
            continue
        checked.add(row["stratum"])
        bundle, evaluator, _ = d.problem(identifier)
        reps = d.Representations(bundle, prep["mapping"], prep["scales"])
        probe = next(p for p in prep["scale_probes"] if p.get("a_finite") and p.get("b_valid"))
        x = [float.fromhex(v) for v in probe["x_hex"]]
        a = evaluator.evaluate_float_residual(x)
        b, valid = reps.both(x, list(a.residual_vector), 15)
        assert valid and len(b) == prep["mapping"]["b_rows"]
        with d.mp.workdps(180):
            point = [d.boundary_float_to_mpf(v, origin=d.BoundaryOrigin.INITIAL_POINT) for v in x]
            with d.high_precision_mode():
                hp = evaluator.evaluate_hp_residual(point, precision=180)
                bh, hv = reps.both(point, list(hp.residual_vector), 180)
            assert hv
            original_hooks = (d.mr._smooth_zero_constraint_residuals, d.mr.derivative_plan,
                              d.mr.compute_finite_difference_jacobian, d.mr._run_findroot_closure)
            for mode in ("A", "B", "L", "R0", "mask:tangency_line_gap"):
                snaps, audit = [], Counter()
                with d.rear_hooks(reps, mode, snaps, time.monotonic(), audit):
                    assert d.mr.derivative_plan(bundle) is None
                    with d.high_precision_mode():
                        value = d.mr._smooth_zero_constraint_residuals(bundle=bundle, point=point,
                                  dps=180, residuals=list(hp.residual_vector))
                    assert value and all(d.mp.isfinite(v) for v in value)
                    if mode == "A":
                        assert value == list(hp.residual_vector)
                    if mode == "B":
                        assert value == bh
                assert original_hooks == (d.mr._smooth_zero_constraint_residuals, d.mr.derivative_plan,
                                         d.mr.compute_finite_difference_jacobian, d.mr._run_findroot_closure)
            if row["stratum"] == "distance_point_zero":
                assert math.isclose(sum(v*v for v in a.residual_vector),
                                    sum(float(v)**2 for v in b), rel_tol=1e-12, abs_tol=1e-12)
            if row["stratum"] == "tangency_line_gap":
                l = reps.transform("L", point, list(hp.residual_vector), 180)
                delta = abs(d.mp.fsum(v*v for v in hp.residual_vector) - d.mp.fsum(v*v for v in l))
                assert delta < d.mp.mpf("1e-150")
        results.append({"id": identifier, "stratum": row["stratum"], "status": "passed"})
    with d.mp.workdps(500):
        point = [d.mp.mpf(1) + d.mp.mpf("1e-320"), d.mp.mpf("1e-400")]
    with d.mp.workdps(15):
        assert [x._mpf_ for x in d.unpacked(d.packed(point))] == [x._mpf_ for x in point]
    temp = Path(tempfile.mkdtemp(prefix="q39-storage-check-"))
    value = {"content": "x" * 4_010_000}
    d.save(temp / "record.json", value)
    assert d.read(temp / "record.json") == value
    assert max(p.stat().st_size for p in temp.iterdir()) < 4_000_000
    receipt = {"utc": d.utc(), "tests": results, "exact_binary_roundtrip": "passed",
               "atomic_split_roundtrip": "passed", "storage_check_directory": str(temp),
               "solver_runs": 0, "refinement_runs": 0, "reference_access": False,
               "wrapper_sha256": {p: d.sha(d.BASE / p) for p in
                                   ("diagnostic.py", "execute_stage2.py", "check_wiring.py")}}
    d.save(d.BASE / "wiring-check.json", receipt)
    print({"passed_strata": len(results), "numeric_solver_runs": 0})


if __name__ == "__main__":
    main()
