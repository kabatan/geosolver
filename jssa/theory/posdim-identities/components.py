"""For cases whose elimination ideal in t is zero: decompose and show where t varies."""
import json, re, subprocess, sys
sys.path.insert(0, ".")
from certify import load, translate, build, poly_str, sp

def run(cid):
    case = load(cid)
    sys_, target = translate(case["dsl"], mode="fresh", with_target=True)
    eqs, used, nondeg = build(sys_, rabinowitsch=True)
    ren = {v: sp.Symbol(f"x{i}") for i, v in enumerate(used)}
    names = [f"x{i}" for i in range(len(used))]
    t = str(ren[target]); others = "*".join(n for n in names if n != t)
    sc = ['LIB "primdec.lib";', f"ring r=0,({','.join(names)}),dp;",
          "ideal I=" + ",".join(poly_str(e.xreplace(ren)) for e in eqs) + ";",
          "list L=minAssGTZ(I); int i;",
          'for(i=1;i<=size(L);i++){print("COMP"); print(dim(std(L[i]))); print("ELIM"); print(eliminate(L[i],' + others + ')); print("GENS"); print(L[i]); print("ENDC");}',
          "quit;"]
    try:
        o = subprocess.run(["Singular", "-q"], input="\n".join(sc), capture_output=True, text=True, timeout=300).stdout
    except subprocess.TimeoutExpired:
        return {"id": cid, "status": "timeout"}
    comps = []
    for blk in o.split("COMP")[1:]:
        d = int(blk.split("ELIM")[0].strip())
        el = blk.split("ELIM")[1].split("GENS")[0].strip().replace("\n", " ")
        gens = blk.split("GENS")[1].split("ENDC")[0].strip().replace("\n", " ")
        comps.append({"dim": d, "t_constant": not re.fullmatch(r"(_\[1\]=)?0", el), "elim": el[:200], "gens": gens[:400]})
    legend = {str(ren[v]): str(v) for v in used}
    return {"id": cid, "status": "ok", "t": t, "legend": legend, "components": comps}

out = [run(c) for c in sys.argv[1:]]
json.dump(out, open("out/components.json", "w"), indent=1)
for r in out:
    if r["status"] != "ok": print(r); continue
    print(r["id"], [(c["dim"], c["t_constant"]) for c in r["components"]])
