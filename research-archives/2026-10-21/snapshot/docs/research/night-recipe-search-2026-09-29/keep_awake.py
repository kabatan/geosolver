"""Release sleep inhibition on completion, or a deadline if policy has one."""
import os,time
from timing import RUN,deadline,write
write(RUN/'sleep-inhibitor.json',dict(pid=os.getpid(),parent_pid=os.getppid(),deadline_policy='current timing policy; completion marker ends inhibition'))
while not (RUN/'campaign-complete.json').exists():
    limit=deadline()
    remaining=None if limit is None else limit-time.time()
    if remaining is not None and remaining<=0:break
    time.sleep(30 if remaining is None else min(30,remaining))
