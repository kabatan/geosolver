"""Current user-authorized timing policy; original clock stays archived.

Actual GPU contention adds at most two hours to the original wall-clock limits.
Only the serial launcher writes the wait ledger. Monitors and the sleep inhibitor
read it; repeated reads and launcher restarts cannot double-count an interval.
"""
import datetime,json,time
from pathlib import Path
RUN=Path(__file__).resolve().parents[3]/'qwen/.runtime/night_recipe_search_20260929'
def read(p):return json.loads(Path(p).read_text())
def write(p,obj):
    p=Path(p);tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n');tmp.replace(p)
def unix(value):return datetime.datetime.fromisoformat(value).timestamp()
def iso(value):return datetime.datetime.fromtimestamp(value,datetime.timezone.utc).isoformat()
def compute(base,policy,ledger,now):
    opened=ledger.get('current_wait_started_utc')
    waiting=float(ledger.get('closed_wait_seconds',0))+max(0,now-unix(opened)) if opened else float(ledger.get('closed_wait_seconds',0))
    if policy.get('mode')=='complete_original_plan':
        return dict(observed_utc=iso(now),actual_gpu_wait_seconds=waiting,
                    credited_wait_seconds=None,maximum_wait_credit_seconds=None,
                    currently_waiting=opened is not None,experimental_cutoff_utc=None,
                    deadline_utc=None,latest_possible_deadline_utc=None,
                    policy='User authorized completion of the original finite plan without a wall-clock cutoff; ComfyUI remains untouched')
    cap=float(policy['maximum_wait_credit_seconds']);credit=min(cap,waiting)
    return dict(observed_utc=iso(now),actual_gpu_wait_seconds=waiting,credited_wait_seconds=credit,
                maximum_wait_credit_seconds=cap,currently_waiting=opened is not None,
                experimental_cutoff_utc=iso(unix(base['experimental_cutoff_utc'])+credit),
                deadline_utc=iso(unix(base['deadline_utc'])+credit),
                latest_possible_deadline_utc=iso(unix(base['deadline_utc'])+cap),
                policy='Original 13-hour limits plus actual GPU waiting, capped at two hours; ComfyUI remains untouched')
def current(now=None):
    return compute(read(RUN/'clock.json'),read(RUN/'timing-policy.json'),read(RUN/'gpu-wait-ledger.json'),time.time() if now is None else now)
def deadline():
    value=current()['deadline_utc']
    return None if value is None else unix(value)
def snapshot():
    value=current();write(RUN/'effective-timing.json',value);return value
def begin_wait(now=None):
    now=time.time() if now is None else now;p=RUN/'gpu-wait-ledger.json';ledger=read(p)
    if ledger.get('current_wait_started_utc') is None:
        ledger['current_wait_started_utc']=iso(now);write(p,ledger)
def end_wait(now=None):
    now=time.time() if now is None else now;p=RUN/'gpu-wait-ledger.json';ledger=read(p);start=ledger.get('current_wait_started_utc')
    if start is not None:
        seconds=max(0,now-unix(start));ledger['closed_wait_seconds']+=seconds
        ledger['closed_intervals'].append(dict(start_utc=start,end_utc=iso(now),seconds=seconds))
        ledger['current_wait_started_utc']=None;write(p,ledger)
    snapshot()
if __name__=='__main__':print(json.dumps(current(),ensure_ascii=False,indent=2))
