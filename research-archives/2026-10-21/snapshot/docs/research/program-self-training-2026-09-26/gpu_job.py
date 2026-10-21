"""One explicitly requested GPU command, exclusive lock and provenance receipt.

No study commands or phases are chosen here. The calling orchestrator must have
authorization and supply the exact frozen command. No shell, driver installation,
device reset, retry or killing another job is performed.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import xml.etree.ElementTree as ET


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--runtime',type=Path,default=Path('qwen/.runtime/program_self_training_20260926'))
    ap.add_argument('--label',required=True)
    ap.add_argument('--recovery-libs',type=Path,required=True)
    ap.add_argument('--input',type=Path,action='append',default=[])
    ap.add_argument('--desktop-inventory',type=Path)
    ap.add_argument('command',nargs=argparse.REMAINDER)
    args=ap.parse_args(); command=args.command[1:] if args.command[:1]==['--'] else args.command
    if not command:ap.error('supply one exact command after --')
    if '/' in args.label or args.label in {'.','..'}:raise ValueError('label must be one directory name')
    runtime=args.runtime.resolve();runtime.mkdir(parents=True,exist_ok=True)
    with (runtime/'gpu-exclusive.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        libs=args.recovery_libs.resolve()
        env=os.environ.copy();env['LD_LIBRARY_PATH']=str(libs)+((':'+env['LD_LIBRARY_PATH']) if env.get('LD_LIBRARY_PATH') else '')
        health=subprocess.run(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader,nounits'],env=env,capture_output=True,text=True,timeout=15,check=True)
        compute_pids={int(line.strip()) for line in health.stdout.splitlines() if line.strip().isdigit()}
        ignored=[]
        if args.desktop_inventory:
            authorized=json.loads(args.desktop_inventory.read_text())['desktop_inventory']
            if len({x['pid'] for x in authorized})!=len(authorized):raise ValueError('duplicate desktop PID inventory')
            xml=subprocess.run(['nvidia-smi','-q','-x'],env=env,capture_output=True,text=True,timeout=15,check=True)
            present={int(x.findtext('pid')):x for x in ET.fromstring(xml.stdout).findall('.//process_info')}
            for baseline in authorized:
                pid=baseline['pid']
                if pid not in compute_pids:continue
                proc=Path('/proc')/str(pid)
                cmdline=(proc/'cmdline').read_bytes()
                info=present.get(pid)
                if (str((proc/'exe').resolve())!=baseline['executable'] or
                        hashlib.sha256(cmdline).hexdigest()!=baseline['cmdline_sha256'] or
                        info is None or info.findtext('type')!=baseline['xml_type'] or baseline['xml_type']!='C+G'):
                    raise RuntimeError(f'desktop PID identity/type changed: {pid}; refusing bypass')
                ignored.append(dict(baseline,cmdline=cmdline.decode(errors='replace').split('\0')[:-1],
                                    observed_type=info.findtext('type'),used_memory=info.findtext('used_memory')))
                compute_pids.remove(pid)
        if compute_pids:
            raise RuntimeError(f'unknown GPU compute process present: {sorted(compute_pids)}; refusing competing work')
        out=runtime/args.label;out.mkdir(exist_ok=False)
        row=dict(status='running',command=command,start_unix=time.time(),driver_sha256=digest(__file__),
                 inputs={str(p.resolve()):digest(p) for p in args.input},recovery_libraries=str(libs),
                 desktop_inventory_sha256=digest(args.desktop_inventory) if args.desktop_inventory else None,
                 ignored_verified_desktop_processes=ignored,
                 library_sha256={p.name:digest(p) for p in [libs/'libcuda.so.595.84',libs/'libnvidia-ml.so.595.84'] if p.exists()})
        receipt=out/'receipt.json';receipt.write_text(json.dumps(row,indent=2)+'\n');tick=time.monotonic()
        try:
            with (out/'driver.log').open('w') as log:
                result=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT)
            row.update(returncode=result.returncode,status='complete' if result.returncode==0 else 'failed')
        except BaseException as exc:
            row.update(status='failed',error=repr(exc));raise
        finally:
            row.update(end_unix=time.time(),elapsed_seconds=time.monotonic()-tick)
            receipt.write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(row),flush=True)
        if result.returncode:raise SystemExit(result.returncode)


if __name__=='__main__':main()
