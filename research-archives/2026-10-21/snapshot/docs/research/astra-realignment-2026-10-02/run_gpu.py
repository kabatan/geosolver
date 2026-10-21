import hashlib,json,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
from prepare_diagnostic import ROOT,RUN,HERE
def main():
    allowed={'/home/kabatan/.local/opt/codex-desktop-linux/codex-app/ChatGPT','/usr/lib/claude-desktop/claude-desktop','/usr/bin/nautilus','/usr/bin/ptyxis','/home/kabatan/.config/discord/app-1.0.159/Discord'}
    inventory=[]
    for x in ET.fromstring(subprocess.check_output(['nvidia-smi','-q','-x'],text=True,timeout=15)).findall('.//process_info'):
        if x.findtext('type')!='C+G':continue
        pid=int(x.findtext('pid'));proc=Path('/proc')/str(pid);exe=str((proc/'exe').resolve())
        if exe in allowed:inventory.append(dict(pid=pid,executable=exe,cmdline_sha256=hashlib.sha256((proc/'cmdline').read_bytes()).hexdigest(),xml_type='C+G'))
    inv=RUN/'desktop.json';inv.write_text(json.dumps(dict(desktop_inventory=inventory),indent=2)+'\n')
    py=ROOT/'qwen/.runtime/vllm-venv/bin/python';actor=ROOT/'docs/research/geometryzero-stage1-2026-09-30/rollout-screen-frozen.py'
    cmd=[str(py),str(ROOT/'docs/research/program-self-training-2026-09-26/gpu_job.py'),'--runtime',str(ROOT/'qwen/.runtime/program_self_training_20260926'),'--label','astra-realign-20261002-diagnostic','--recovery-libs','/usr/lib/x86_64-linux-gnu','--desktop-inventory',str(inv),'--input',str(RUN/'jobs.json'),'--input',str(actor),'--',str(py),str(actor),'--jobs',str(RUN/'jobs.json'),'--out',str(RUN/'diagnostic'),'--cap','1024']
    with (RUN/'diagnostic.log').open('x') as log:rc=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT).returncode
    print(json.dumps(dict(returncode=rc)));raise SystemExit(rc)
if __name__=='__main__':main()
