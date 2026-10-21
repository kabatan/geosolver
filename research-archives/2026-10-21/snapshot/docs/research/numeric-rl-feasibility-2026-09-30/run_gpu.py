"""Use the existing shared exclusive GPU lock, with a new immutable receipt."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
import xml.etree.ElementTree as ET
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];RUN=ROOT/'qwen/.runtime/numeric_rl_feasibility_20260930'
PY=ROOT/'qwen/.runtime/vllm-venv/bin/python'
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--label',required=True);ap.add_argument('--input',action='append',default=[]);ap.add_argument('command',nargs=argparse.REMAINDER);a=ap.parse_args();cmd=a.command[1:] if a.command[:1]==['--'] else a.command
    if not cmd:raise ValueError('supply exact command')
    allowed={'/home/kabatan/.local/opt/codex-desktop-linux/codex-app/ChatGPT','/usr/lib/claude-desktop/claude-desktop','/usr/bin/nautilus','/usr/bin/ptyxis','/home/kabatan/.config/discord/app-1.0.159/Discord'}
    rows=[];xml=subprocess.check_output(['nvidia-smi','-q','-x'],text=True,timeout=15)
    for x in ET.fromstring(xml).findall('.//process_info'):
        if x.findtext('type')!='C+G':continue
        pid=int(x.findtext('pid'));p=Path('/proc')/str(pid);exe=str((p/'exe').resolve())
        if exe in allowed:rows.append(dict(pid=pid,executable=exe,cmdline_sha256=hashlib.sha256((p/'cmdline').read_bytes()).hexdigest(),xml_type='C+G'))
    inv=RUN/('desktop-'+a.label+'.json');inv.write_text(json.dumps(dict(desktop_inventory=rows),indent=2)+'\n')
    guard=[str(PY),str(ROOT/'docs/research/program-self-training-2026-09-26/gpu_job.py'),'--runtime',str(ROOT/'qwen/.runtime/program_self_training_20260926'),'--label','rl-feasibility-20260930-'+a.label,'--recovery-libs','/usr/lib/x86_64-linux-gnu','--desktop-inventory',str(inv)]
    for p in a.input:guard+=['--input',p]
    guard+=['--']+cmd
    with (RUN/(a.label+'.log')).open('x') as log:rc=subprocess.run(guard,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT).returncode
    print(json.dumps(dict(label=a.label,returncode=rc,guard_receipt=str(ROOT/'qwen/.runtime/program_self_training_20260926'/('rl-feasibility-20260930-'+a.label)/'receipt.json'))))
    raise SystemExit(rc)
if __name__=='__main__':main()
