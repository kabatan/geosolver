"""Verify retained bytes, complete coverage, scoring, gates, resource contract."""
from common import *
import base64
from collections import Counter,defaultdict
import csv
import math
import time
import zlib
from benchmarks import research_runner as research
from geosolver.exact import describe_exact

lock=verify_lock()
completion=read(HERE/"completion.json")
assert completion["completed_runs"]==646 and not completion["active"] and not completion["stopped"]
manifest={r["id"]:r for r in read(HERE/"manifest.json")}
cases={c.identifier:c for c in research._load_cases()}
expected={i:sorted({research._canonical_json(describe_exact(v).canonical_key())
                    for ref in c.references for v in research.reference_expressions(ref)})
          for i,c in cases.items()}
csv_rows={(r["id"],r["mode"]):r for r in csv.DictReader((HERE/"per-run.csv").open())}
seen=set()
records={}
recovered=[]
counts={m:Counter() for m in ("B","R")}
failures=[]
events=[]
cpu_counts=defaultdict(Counter)
statuses={m:Counter() for m in ("B","R")}
for bundle in sorted((HERE/"return-bundles").glob("*.json")):
    for item in read(bundle):
        identifier,mode=item["id"],item["mode"]
        key=(identifier,mode)
        assert key not in seen and identifier in manifest and mode in ("B","R")
        seen.add(key)
        raw=json.loads(zlib.decompress(base64.b64decode(item["zlib_base64"])))
        receipt=item["receipt"]
        directory=HERE/"campaign"/mode/"runs"/identifier
        for name,value in (("0.json",raw),("0.receipt.json",receipt)):
            path=directory/name
            if not path.exists():
                dump(path,value)
                recovered.append(dict(id=identifier,mode=mode,file=name))
            assert read(path)==value, f"return/file mismatch: {path}"
        result=raw["solver_result"]
        audit=receipt["audit"]
        embedded=result["diagnostics"]["q13_role_audit"]
        assert audit["source"]==embedded["source"]=="embedded_worker_artifact"
        assert audit["verified"] and audit["final_evaluator_unchanged"] and audit["condition"]==mode
        assert audit["counts"]==embedded["counts"] and embedded["condition"]==mode
        info=result["diagnostics"]["process_info"]
        assert embedded["pid"]==info["pid"]
        assert receipt["started_unix"]>=completion["started_unix"]
        assert receipt["started_unix"] <= receipt["finished_unix"] <= datetime.fromisoformat(completion["finished_utc"]).timestamp()
        assert raw["source_hash"]==lock["runtime"]["source_hash"]
        assert not raw["execution_contract_issues"] and receipt["runner_error"] is None
        assert raw["config"]["time_limit_seconds"]==180 and raw["config"]["cores"]==1 and raw["seed"]==0
        assert raw["config"]["thread_environment"]==research.THREAD_ENVIRONMENT
        for kind in ("requested_resources","used_resources"):
            assert result[kind]["seed"]==0 and result[kind]["cores"]==1
        assert info["effective_cores"]==1 and info["cpu_affinity"]==[receipt["cpu"]]
        assert raw["process"]["actual_affinity"]==[receipt["cpu"]]
        assert raw["process"]["returncode"]==0 and not raw["process"]["timed_out"]
        assert raw["transport"]["parse_error"] is None
        assert raw["problem_hash"]==research._sha256_bytes(research._canonical_json(cases[identifier].dsl).encode())
        actual=research._answer_keys(result)
        matched=research.read_run_outcome(raw)["normal_completion"] and actual==expected[identifier]
        assert matched==(csv_rows[key]["matched"]=="True")
        counts[mode].update(audit["counts"])
        assert audit["counts"].get("hard_bypassed",0)==(audit["counts"].get("hard_calls",0) if mode=="R" else 0)
        statuses[mode][result["status"]]+=1
        records[key]=dict(receipt=receipt,matched=matched,termination=result["termination_reason"],
                          seconds=result["elapsed_seconds"],cpu=info["cpu_seconds"],audit=audit)
        events.extend(((receipt["started_unix"],1),(receipt["finished_unix"],-1)))
        cpu_counts[receipt["cpu"]][mode]+=1
        if not matched:
            failures.append(dict(id=identifier,mode=mode,status=csv_rows[key]["status"],
                termination_reason=result["termination_reason"],
                failure_stage=csv_rows[key]["failure_stage"],
                solver_seconds=result["elapsed_seconds"],
                returned_answer_keys=actual,expected_answer_keys=expected[identifier]))
        if len(seen)%100==0:
            print(json.dumps(dict(verified=len(seen))),flush=True)
assert seen=={(i,m) for i in manifest for m in ("B","R")}
active=maximum=0
for timestamp,increment in sorted(events):
    active+=increment
    maximum=max(maximum,active)
assert maximum<=8 and active==0
for identifier,m in manifest.items():
    b,r=(records[(identifier,mode)] for mode in ("B","R"))
    bi,ri=(lock["cpus"].index(x["receipt"]["cpu"]) for x in (b,r))
    assert bi//2==ri//2 and bi!=ri
    assert (bi%2==0)==(m["first"]=="B")
    assert b["matched"]==r["matched"]
paths=[p for p in HERE.rglob("*") if p.is_file()]
largest=max(paths,key=lambda p:p.stat().st_size)
assert largest.stat().st_size<=20_000_000
assert not (ROOT/"verify-placeholder-unused").exists()
verify_lock()
report=dict(utc=now(),passed=True,paired_problems=323,verified_runs=len(seen),
            return_bundle_files=len(list((HERE/"return-bundles").glob("*.json"))),
            all_return_bytes_match_saved_json=True,all_embedded_audits_verified=True,
            all_final_evaluators_unchanged=True,all_seed0_core1_affinity_thread_contracts_valid=True,
            recovered_after_completion=recovered,max_simultaneous_solve_intervals=maximum,
            per_cpu_condition_counts={str(k):dict(v) for k,v in sorted(cpu_counts.items())},
            counts={m:dict(c) for m,c in counts.items()},raw_statuses={m:dict(c) for m,c in statuses.items()},
            storage_error_runs=sum(bool(x["receipt"].get("storage_error")) for x in records.values()),
            deadline_hit_but_correct={m:[i for (i,mode),x in records.items() if mode==m and x["matched"] and x["termination"]=="time_limit_reached"] for m in ("B","R")},
            largest_file=str(largest.relative_to(HERE)),largest_file_bytes=largest.stat().st_size,
            prereg_sha256=sha(HERE/"preregistration.md"),source_hash=lock["runtime"]["source_hash"])
dump(HERE/"delivery-verification.json",report)
dump(HERE/"failures.json",failures)
print(json.dumps(report,ensure_ascii=False))
