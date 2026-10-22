"""Build the system Z_G: points re-made as y = h(u) + z (as in Z), but keeping the construction equations G of the
free-point system Y as residual rows instead of z = 0. So Y -> Z_G is a pure change of coordinates
(same residual rows), and Z_G -> Z only changes the construction rows from G to z.
Usage: make_zg.py E.json Y.json Z.json OUT.json"""
import json, sys
e, y, z = (json.load(open(p)) for p in sys.argv[1:4])
key = lambda c: json.dumps(c, sort_keys=True)
e_keys = {key(c) for c in e["conditions"]}
g_rows = [c for c in y["conditions"] if key(c) not in e_keys]
is_ofs = lambda c: isinstance(c.get("left"), str) and c["left"].startswith("ofs") and c.get("operator") == "=" and str(c.get("right")) == "0"
zg = dict(z)
zg["conditions"] = [c for c in z["conditions"] if not is_ofs(c)] + g_rows
zg["id"] = z.get("id", "") + ".zg"
assert sum(map(is_ofs, z["conditions"])) == len([v for v in z["variables"] if v.startswith("ofs")])
json.dump(zg, open(sys.argv[4], "w"), indent=1)
print(sys.argv[4], "G rows:", len(g_rows), "ofs rows removed:", sum(map(is_ofs, z["conditions"])))
