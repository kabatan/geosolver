"""Create immutable training configs and record inputs before any new output."""
import subprocess,xml.etree.ElementTree as ET,time
import run_study as op
P,R,O=op.P,op.R,op.O

def main():
    assert not (O/'freeze.json').exists()
    base=op.read(op.DOC/'config-sft-a-32.json')
    for arm,updates,script in [('correct',512,op.FIT),('shuffled',32,op.TRAIN),('shuffled',128,op.CONT),('shuffled',512,op.FIT)]:
        dataset=O/f'train-{arm}.json'
        c=dict(base,dataset=str(dataset),dataset_sha256=op.sha(dataset),updates=updates,save_checkpoints=[],protocol_sha256=op.sha(P/'PROTOCOL.md'))
        c.pop('extension_wrapper_sha256',None);c.pop('prior_checkpoint',None)
        if updates>32:
            prior=(op.OLD/'sft-a-train128/final') if arm=='correct' else O/f'shuffled-train{32 if updates==128 else 128}/final'
            c.update(prior_checkpoint=str(prior),extension_wrapper_sha256=op.sha(script))
        op.write(P/f'config-{arm}-{updates}.json',c)
    xml=ET.fromstring(subprocess.check_output(['nvidia-smi','-q','-x'],text=True));inventory=[]
    for x in xml.findall('.//process_info'):
        if x.findtext('type')!='C+G':continue
        pid=int(x.findtext('pid'));proc=op.Path('/proc')/str(pid)
        inventory.append({'pid':pid,'executable':str((proc/'exe').resolve()),'cmdline_sha256':op.sha(proc/'cmdline'),'xml_type':'C+G'})
    op.write(O/'desktop-inventory.json',{'desktop_inventory':inventory})
    inputs=[P/'PROTOCOL.md',P/'run_study.py',P/'score_fit.py',P/'freeze_study.py',P/'prepare_data.py',
            O/'train-correct.json',O/'train-shuffled.json',O/'shuffle-map.json',O/'fit-jobs.json',O/'fit-answer-key.json',
            op.DRIVER,op.TRAIN,op.CONT,op.FIT,op.GUARD,
            op.DOC/'analyze.py',R/'qwen/answer_check.py',
            R/'docs/research/transfer-reanalysis-2026-09-26/score_numeric.py',
            R/'docs/research/qwen35-self-materials-2026-09-23/model.json',
            op.OLD/'data-provenance.json',op.OLD/'sft-a-train128/final/receipt.json',
            op.OLD/'sft-a-train128/final/adapter/adapter_model.safetensors',
            op.OLD/'sft-a-train128/final/adapter-vllm/adapter_model.safetensors',
            op.OLD/'sft-a-train128/final/optimizer.pt']+sorted(P.glob('config-*.json'))
    op.write(O/'freeze.json',{'status':'frozen','unix':time.time(),'arms':op.ARMS,'train_examples':80,'heldout_examples':30,
                             'seed':2026092701,'sha256':{str(p):op.sha(p) for p in inputs}})
    print('Frozen',len(inputs),'files')
if __name__=='__main__':main()
