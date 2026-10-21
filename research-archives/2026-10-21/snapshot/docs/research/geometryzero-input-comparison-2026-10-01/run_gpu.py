"""New immutable run, reusing the workspace GPU lock and frozen stage1 actor."""
import argparse,hashlib,json,subprocess
from pathlib import Path
import xml.etree.ElementTree as ET
from formalize import ROOT,RUN

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--label',required=True);a=ap.parse_args()
    py=ROOT/'qwen/.runtime/vllm-venv/bin/python'
    old=ROOT/'docs/research/geometryzero-stage1-2026-09-30'
    allowed={'/home/kabatan/.local/opt/codex-desktop-linux/codex-app/ChatGPT','/usr/lib/claude-desktop/claude-desktop','/usr/bin/nautilus','/usr/bin/ptyxis','/home/kabatan/.config/discord/app-1.0.159/Discord'}
    rows=[];xml=subprocess.check_output(['nvidia-smi','-q','-x'],text=True,timeout=15)
    for x in ET.fromstring(xml).findall('.//process_info'):
        if x.findtext('type')!='C+G':continue
        pid=int(x.findtext('pid'));p=Path('/proc')/str(pid);exe=str((p/'exe').resolve())
        if exe in allowed:rows.append(dict(pid=pid,executable=exe,cmdline_sha256=hashlib.sha256((p/'cmdline').read_bytes()).hexdigest(),xml_type='C+G'))
    inv=RUN/('desktop-'+a.label+'.json');inv.write_text(json.dumps(dict(desktop_inventory=rows),indent=2)+'\n')
    cmd=[str(py),str(ROOT/'docs/research/program-self-training-2026-09-26/gpu_job.py'),'--runtime',str(ROOT/'qwen/.runtime/program_self_training_20260926'),'--label','geometryzero-input-20261001-'+a.label,'--recovery-libs','/usr/lib/x86_64-linux-gnu','--desktop-inventory',str(inv),'--input',str(RUN/'jobs.json'),'--input',str(old/'rollout-screen-frozen.py'),'--',str(py),str(old/'rollout-screen-frozen.py'),'--jobs',str(RUN/'jobs.json'),'--out',str(RUN/a.label),'--cap','1024']
    with (RUN/(a.label+'.log')).open('x') as log:rc=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT).returncode
    print(json.dumps(dict(label=a.label,returncode=rc)));raise SystemExit(rc)

if __name__=='__main__':main()
