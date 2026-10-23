"""Bounded, two-process execution of the immutable Q40a trial schedule.

SQLite is external, and the coordinator is its only writer. A started slot is
never retried, even after a crash. Each command stops admitting work at 185 s.
"""
from common import *
import argparse
from collections import Counter
import fcntl
import multiprocessing as mp
from multiprocessing.connection import wait
import signal
import sqlite3
import time
import traceback


def connect():
    db = sqlite3.connect(EXTERNAL / 'trials.sqlite')
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA synchronous=FULL')
    db.execute('CREATE TABLE IF NOT EXISTS trials (idx INTEGER PRIMARY KEY, case_id TEXT, seed INTEGER, k INTEGER, variant TEXT, position INTEGER, status TEXT, data TEXT, UNIQUE(case_id,seed,k,variant))')
    db.execute('CREATE TABLE IF NOT EXISTS builds (case_id TEXT, variant TEXT, status TEXT, data TEXT, PRIMARY KEY(case_id,variant))')
    db.execute('CREATE TABLE IF NOT EXISTS events (at_utc TEXT, kind TEXT, data TEXT)')
    if db.execute('SELECT count(*) FROM trials').fetchone()[0] == 0:
        rows = []
        for case in read(PLAN / 'selected.json'):
            for seed, k, variant, position in schedule(case['canonical_id']):
                rows.append((len(rows), case['canonical_id'], seed, k, variant, position, 'unstarted', '{}'))
        db.executemany('INSERT INTO trials VALUES(?,?,?,?,?,?,?,?)', rows)
        db.commit()
    assert db.execute('SELECT count(*) FROM trials').fetchone()[0] == 144000
    return db


def send(conn, kind, **data):
    conn.send({'kind': kind, **clean_json(data)})


def worker(conn, case, slots, prior_builds, stop_at, cpu):
    os.sched_setaffinity(0, {cpu})
    import numpy as np
    from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds
    from geosolver.engine.standard.contracts.external_pipeline_config import ExternalPipelineConfig
    from geosolver.engine.standard.search.scipy_multistart_backend import (
        _collect_local_start_record, _SearchTelemetry, _SearchDeadlineExceeded)
    from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
    from geosolver.engine.standard.evaluation.search_point import evaluate_search_point
    from geosolver.runtime.deadline import deadline_scope
    from geosolver.engine.standard.search.scipy_lazy import least_squares
    # Import scipy before any trial deadline, without running an optimization.
    import scipy.optimize
    case_id = case['canonical_id']
    bundle_map, failures = {}, {}
    common_names = None
    common_bounds = None
    for variant in VARIANTS:
        prior = prior_builds.get(variant)
        if prior and prior['status'] != 'built':
            failures[variant] = prior
            continue
        if time.monotonic() > stop_at - 65:
            send(conn, 'yield')
            return
        send(conn, 'build_start', variant=variant, previously_built=bool(prior))
        assert conn.recv() == 'ack'
        started = time.monotonic()
        try:
            with deadline_scope(started + 60):
                bundle, evaluator = assemble(case_id, variant)
                if variant == 'original':
                    common_names = list(bundle.var_names)
                    common_bounds = [[float(a), float(b)] for a, b in infer_problem_bounds(bundle)]
                    # The contract compares compiled variables across variants;
                    # frozen compilation may eliminate a fixed input variable.
                    assert len(common_bounds) == len(common_names)
                    assert all(math.isfinite(a) and math.isfinite(b) and b > a for a, b in common_bounds)
                else:
                    assert common_names is not None, 'Original bounds unavailable'
                    assert set(bundle.var_names) == set(common_names), 'Variable set differs'
                    assert len(bundle.var_names) == len(common_names), 'Dimension differs'
                positions = [common_names.index(name) for name in bundle.var_names]
                bounds = [common_bounds[j] for j in positions]
                method = 'Powell' if len(bounds) > len(bundle.spec.constraints) else 'LM'
                meta = {'status': 'built', 'variant': variant, 'var_names': list(bundle.var_names),
                        'original_var_names': common_names, 'original_bounds': common_bounds,
                        'bounds': bounds, 'positions': positions, 'method': method,
                        'n_vars': len(bounds), 'n_eq': len(bundle.spec.constraints),
                        'dsl_sha256': sha((PLAN / 'dsl' / case_id / (variant+'.json')).read_bytes()),
                        'seconds': time.monotonic()-started, 'at_utc': utc()}
                if prior:
                    for key in ('var_names','bounds','method','n_vars','n_eq','dsl_sha256'):
                        assert meta[key] == prior[key], (variant, key)
                bundle_map[variant] = (bundle, evaluator, meta)
        except Exception as error:
            meta = {'status': 'build_failed', 'error': type(error).__name__ + ': ' + str(error),
                    'seconds': time.monotonic()-started, 'at_utc': utc()}
            failures[variant] = meta
        send(conn, 'build_done', variant=variant, data=meta)
        assert conn.recv() == 'ack'
    if common_bounds is None:
        for variant in VARIANTS:
            failures.setdefault(variant, {'status': 'build_failed', 'error': 'Original bounds unavailable'})
    arrays = {seed: starts(case_id, seed, common_bounds) for seed in SEEDS} if common_bounds else {}
    configs = {s: ExternalPipelineConfig.production_baseline_tier(seed=s,total_time_budget_sec=180).search for s in SEEDS}
    for idx, seed, k, variant, position in slots:
        if time.monotonic() > stop_at - 10:
            break
        if variant in failures:
            send(conn, 'unexecutable', idx=idx, data={'status':'build_failed','reason':failures[variant], 'attempted':False,'hit':False})
            assert conn.recv() == 'ack'
            continue
        bundle, evaluator, meta = bundle_map[variant]
        x0 = arrays[seed][k, meta['positions']]
        send(conn, 'trial_start', idx=idx, data={'started_at_utc':utc(), 'method':meta['method'],
             'x0':x0.tolist(), 'start_sha256':sha(x0.astype('<f8').tobytes()), 'cpu':cpu})
        assert conn.recv() == 'ack'
        telemetry = _SearchTelemetry()
        record = {'attempted':True, 'method':meta['method'], 'hit':False}
        started = time.monotonic()
        try:
            candidate = _collect_local_start_record(
                bundle=bundle, evaluator=evaluator, bounds=meta['bounds'], config=configs[seed],
                seed=seed, start_index=k, start=x0.copy(), deadline_monotonic=started+2,
                telemetry=telemetry, constraint_scales=None)
            record['local_seconds'] = time.monotonic()-started
            record['status'] = 'returned' if candidate is not None else 'no_candidate'
            record['endpoint'] = list(candidate.x_float) if candidate is not None else None
        except (_SearchDeadlineExceeded, TimeoutError):
            candidate = None
            record.update(status='local_timeout', local_seconds=time.monotonic()-started)
        except Exception as error:
            candidate = None
            record.update(status='local_exception', error=type(error).__name__+': '+str(error),local_seconds=time.monotonic()-started)
        record['evaluations'] = telemetry.evaluation_count
        record['evaluation_failures'] = telemetry.failure_count
        send(conn, 'local_done', idx=idx, data=record)
        assert conn.recv() == 'ack'
        if candidate is not None:
            # This is endpoint scoring, outside the local 2-second deadline.
            try:
                point = np.asarray(candidate.x_float, dtype=float)
                residual = evaluator.evaluate_float_residual(point)
                score = evaluate_search_point(evaluator=evaluator, values=point, residual=residual)
                finite = bool(np.all(np.isfinite(point)) and np.all(np.isfinite(residual.residual_vector)))
                norm = math.hypot(*residual.residual_vector)
                in_box = all(lo <= x <= hi for x, (lo,hi) in zip(point,meta['bounds'],strict=True))
                eligible = bool(finite and residual.evaluation_status is EvaluationStatus.OK and score.guard_ok is True and score.hard.hard_feasible is True and in_box)
                record.update(F=list(residual.residual_vector), residual_norm=norm,
                    evaluation_status=residual.evaluation_status.value, finite=finite,
                    guard_ok=bool(score.guard_ok), hard_feasible=bool(score.hard.hard_feasible),
                    guard_violations=list(score.guard_violations), in_box=bool(in_box),
                    eligible=eligible, hit=eligible and norm<=1e-8,
                    hit_strict=eligible and norm<=1e-10, hit_loose=eligible and norm<=1e-6)
            except Exception as error:
                record.update(status='scoring_exception', error=type(error).__name__+': '+str(error))
        record['finished_at_utc'] = utc()
        send(conn, 'trial_done', idx=idx, data=record)
        assert conn.recv() == 'ack'
    send(conn, 'yield')


def run(seconds):
    assert 15 <= seconds <= 190
    assert read(HERE / 'receipt.json')['execution_authorized']
    verify_source()
    for name, info in read(PLAN / 'prediction.lock.json')['files'].items():
        assert sha((PLAN/name).read_bytes()) == info['sha256'], name
    EXTERNAL.mkdir(exist_ok=True)
    with (EXTERNAL / 'runner.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        db = connect()
        # An uncommitted return is never substituted by a second local call.
        for idx, payload in db.execute("SELECT idx,data FROM trials WHERE status IN ('started','local_done')").fetchall():
            data=json.loads(payload); data.update(status='worker_abnormal',hit=False,unknown=True,recovered_at_utc=utc())
            db.execute('UPDATE trials SET status=?,data=? WHERE idx=?',('worker_abnormal',json.dumps(data),idx))
        for case_id,variant in db.execute("SELECT case_id,variant FROM builds WHERE status='building'").fetchall():
            db.execute('UPDATE builds SET status=?,data=? WHERE case_id=? AND variant=?',
                ('build_failed',json.dumps({'status':'build_failed','error':'interrupted build; no retry'}),case_id,variant))
        db.commit()
        start_at=time.monotonic(); stop_at=start_at+seconds
        ctx=mp.get_context('fork')
        cases=read(PLAN/'selected.json')
        cpus=sorted(os.sched_getaffinity(0))[:2]
        active={}; finished_cases=set(); batch_counts=Counter()
        batch={'started_at_utc':utc(),'loadavg_start':os.getloadavg(),'cpus':cpus,'source_hash':SOURCE_HASH,
               'instrumentation':{p.name:sha(p.read_bytes()) for p in HERE.glob('*.py')},'command_budget_seconds':seconds}

        def event(kind,data):
            db.execute('INSERT INTO events VALUES(?,?,?)',(utc(),kind,json.dumps(clean_json(data))))

        def launch(lane):
            if time.monotonic()>stop_at-70:
                return
            # Preserve each lane's queue, then help with unstarted work in the
            # other queue. Never give one case to two simultaneous workers.
            for case in cases[lane::2] + cases[1-lane::2]:
                cid=case['canonical_id']
                if any(state['case']==cid for state in active.values()): continue
                if cid in finished_cases: continue
                slots=db.execute("SELECT idx,seed,k,variant,position FROM trials WHERE case_id=? AND status='unstarted' ORDER BY idx",(cid,)).fetchall()
                if not slots:
                    finished_cases.add(cid); continue
                builds={v:dict(json.loads(data),status=status) for v,status,data in db.execute('SELECT variant,status,data FROM builds WHERE case_id=?',(cid,))}
                parent,child=ctx.Pipe()
                proc=ctx.Process(target=worker,args=(child,case,slots,builds,stop_at,cpus[lane]))
                proc.start(); child.close()
                active[parent]={'proc':proc,'case':cid,'lane':lane,'phase':'initializing','at':time.monotonic(),'slot':None,'variant':None}
                event('worker_started',{'pid':proc.pid,'case_id':cid,'lane':lane,'remaining':len(slots)})
                db.commit()
                return

        def failure(conn,reason):
            state=active.pop(conn); proc=state['proc']
            if proc.is_alive(): proc.kill()
            proc.join(timeout=1); conn.close()
            if state['slot'] is not None:
                idx=state['slot']; data=json.loads(db.execute('SELECT data FROM trials WHERE idx=?',(idx,)).fetchone()[0])
                data.update(status=reason,hit=False,unknown=True,finished_at_utc=utc())
                db.execute('UPDATE trials SET status=?,data=? WHERE idx=?',(reason,json.dumps(data),idx))
                batch_counts[reason]+=1
            if state['phase']=='building':
                data={'status':'build_failed','error':reason,'at_utc':utc()}
                db.execute('INSERT OR REPLACE INTO builds VALUES(?,?,?,?)',(state['case'],state['variant'],'build_failed',json.dumps(data)))
            event('worker_stopped',{'case_id':state['case'],'reason':reason,'phase':state['phase']})
            db.commit(); launch(state['lane'])

        launch(0); launch(1)
        last_report=start_at
        while active:
            for conn in wait(list(active),timeout=.05):
                state=active.get(conn)
                if state is None: continue
                try: message=conn.recv()
                except EOFError:
                    failure(conn,'worker_abnormal'); continue
                kind=message['kind']; now=time.monotonic()
                if kind=='yield':
                    proc=state['proc']; proc.join(timeout=1)
                    if proc.is_alive(): proc.kill(); proc.join(timeout=1)
                    conn.close(); del active[conn]
                    if not db.execute("SELECT 1 FROM trials WHERE case_id=? AND status='unstarted' LIMIT 1",(state['case'],)).fetchone():
                        finished_cases.add(state['case'])
                    launch(state['lane']); continue
                if kind=='build_start':
                    state.update(phase='building',at=now,variant=message['variant'])
                    db.execute('INSERT OR REPLACE INTO builds VALUES(?,?,?,?)',(state['case'],message['variant'],'building',json.dumps(message)))
                    event(kind,{'case_id':state['case'],**message})
                elif kind=='build_done':
                    data=message['data']; db.execute('INSERT OR REPLACE INTO builds VALUES(?,?,?,?)',(state['case'],message['variant'],data['status'],json.dumps(data)))
                    state.update(phase='idle',at=now)
                elif kind=='trial_start':
                    idx=message['idx']; assert db.execute('SELECT status FROM trials WHERE idx=?',(idx,)).fetchone()[0]=='unstarted'
                    data=message['data']; data['source_hash']=SOURCE_HASH
                    db.execute('UPDATE trials SET status=?,data=? WHERE idx=?',('started',json.dumps(data),idx))
                    state.update(phase='local',at=now,slot=idx)
                elif kind in ('local_done','trial_done','unexecutable'):
                    idx=message['idx']; data=json.loads(db.execute('SELECT data FROM trials WHERE idx=?',(idx,)).fetchone()[0]); data.update(message['data'])
                    status='local_done' if kind=='local_done' else data['status']
                    db.execute('UPDATE trials SET status=?,data=? WHERE idx=?',(status,json.dumps(clean_json(data)),idx))
                    if kind=='local_done': state.update(phase='scoring',at=now)
                    else:
                        state.update(phase='idle',at=now,slot=None); batch_counts[status]+=1
                else: raise AssertionError(kind)
                db.commit(); conn.send('ack')
            now=time.monotonic()
            for conn,state in list(active.items()):
                limit=5 if state['phase']=='local' else 60
                if now-state['at']>limit or now>stop_at+5:
                    failure(conn,'outer_timeout' if state['phase']=='local' else 'worker_abnormal')
            if now-last_report>25:
                print(json.dumps({'batch_finished':sum(batch_counts.values()),'statuses':batch_counts,'elapsed':round(now-start_at,1)}),flush=True)
                last_report=now
        batch.update(finished_at_utc=utc(),seconds=time.monotonic()-start_at,counts=dict(batch_counts),loadavg_end=os.getloadavg())
        event('batch_completed',batch); db.commit()
        counts=dict(db.execute('SELECT status,count(*) FROM trials GROUP BY status'))
        builds=dict(db.execute('SELECT status,count(*) FROM builds GROUP BY status'))
        batch['overall_statuses']=counts; batch['build_statuses']=builds
        write(EXTERNAL/'batches'/(batch['started_at_utc'].replace(':','')+'.json'),batch)
        write(HERE/'progress.json',{'at_utc':utc(),'planned':144000,'statuses':counts,'builds':builds,'raw_directory':str(EXTERNAL),'complete':counts.get('unstarted',0)==0})
        db.close()
        print(json.dumps(batch),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--seconds',type=float,default=185)
    run(parser.parse_args().seconds)
