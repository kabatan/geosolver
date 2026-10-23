"""Reproduce the completed protocol, sequentially, using the supplied Python environment."""
import argparse
import json
import experiment as e

ap = argparse.ArgumentParser()
ap.add_argument("--box-only", action="store_true")
args = ap.parse_args()
if not args.box_only:
    e.features()
    known = ["AIME-2020-II-15", "HMMT-2017-FEB-GEO-10", "HMMT-2021-FEB-GEO-04"]
    features = json.loads((e.HERE / "features.json").read_text())
    extra = [r["case_id"] for r in sorted(features, key=lambda r: r["metric"], reverse=True)
             if r["rule_R"] and r["case_id"] not in known][:3]
    plan = known + extra + ["AIME-2018-I-15"]
    e.save("run_plan.json", dict(cases=plan, seed=102301, starts=60, rule="fixed protocol.md", extra_selected=extra))
    for cid in plan:
        systems = ["E", "Y", "Z", "ZG", "Ynorm", "Eunit"] if cid == known[0] else ["E", "Y"]
        e.run(cid, systems, 60, 102301, "fresh")
e.run("AIME-2020-II-15", ["E", "Y"], 60, 102301, "compact", boxfactor=.01)
e.summarize()
