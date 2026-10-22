import csv, glob, json, os, re
rows = []
jobs = dict(l.split() for l in open("jobs.txt"))
for cid in sorted(jobs):
    d = f"all/{cid}"
    r = {"id": cid, "P_coeffs": jobs[cid]}
    if os.path.exists(f"{d}/result.json"):
        j = json.load(open(f"{d}/result.json"))
        st = j["status"]
        if st == "ok":
            st = "identity_P" if j["member"] else "identity_E"
            if not j.get("identity_check_sympy"):
                st += "_sympy_fail"
        r.update(status=st, dim=j.get("dim"), free=";".join(j.get("independent_vars") or []), elim=j.get("elim_poly"),
                 N=j.get("N"), cofactor_terms=sum(j.get("cofactor_terms") or []), seconds=round(j["seconds"], 2),
                 check="singular+sympy" if st.startswith("identity") else "")
    elif os.path.exists(f"{d}/singular.out"):
        head = open(f"{d}/singular.out").read(20000).split("COFACTORS")[0]
        if "CHECK" in head and head.split("CHECK")[1].strip().startswith("1"):
            el = head.split("ELIM")[1].split("ENDELIM")[0].strip()
            r.update(status="identity_E_large", dim=int(head.split("DIM")[1].split("INDEP")[0]), elim=el[:120],
                     check=f"singular only (cofactors {os.path.getsize(d+'/singular.out')//2**20} MB)")
        else:
            r.update(status="timeout_300s")
    else:
        r.update(status="unsupported_angle_target")
    rows.append(r)
keys = ["id", "status", "dim", "free", "P_coeffs", "elim", "N", "cofactor_terms", "seconds", "check"]
with open("out/batch-summary.csv", "w", newline="") as f:
    w = csv.DictWriter(f, keys); w.writeheader(); [w.writerow({k: r.get(k, "") for k in keys}) for r in rows]
from collections import Counter
print(Counter(r["status"] for r in rows))
