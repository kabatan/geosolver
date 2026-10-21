"""One fixed longer-training check; targets remain numeric only."""
from pathlib import Path
import time
from run_remaining import OUT,HERE,PYTHON,GENERATE,read,write,digest,run


def main():
    config=read(HERE/'config-128.json')
    config.update(updates=512,prior_checkpoint=str(OUT/'train128/final'),
                  extension_wrapper_sha256=digest(HERE/'train_fit512.py'),
                  fit_amendment_sha256=digest(HERE/'AMENDMENT-FIT-CHECK.md'))
    assert not (HERE/'config-512.json').exists();write(HERE/'config-512.json',config)
    jobs=[r for r in read(OUT/'data/numeric-jobs.json') if r['split']=='train_probe'];assert len(jobs)==4
    job_path=OUT/'fit512-probe-jobs.json';write(job_path,jobs)
    write(OUT/'fit512-freeze.json',{'frozen_unix':time.time(),'sha256':{str(p):digest(p) for p in
          [HERE/'config-512.json',HERE/'train_fit512.py',Path(__file__),HERE/'AMENDMENT-FIT-CHECK.md',job_path]}})
    deadline=time.monotonic()+7200
    while not (OUT/'coordinate-completion.json').exists():
        if time.monotonic()>deadline:raise RuntimeError('preceding diagnostics not complete; inspect')
        time.sleep(5)
    trainer=HERE/'train_fit512.py';cfg=HERE/'config-512.json'
    run([PYTHON,trainer,'--config',cfg,'--out',OUT/'preflight512','--preflight'],'preflight512')
    run([PYTHON,trainer,'--config',cfg,'--out',OUT/'train512'],'train512',gpu=True,inputs=[cfg,OUT/'data/train.json'])
    def generate_probe(path,extended=False):
        label='fit512-probe'+('-81k' if extended else '')
        command=[PYTHON,GENERATE,'--jobs',path,'--out',OUT/label,'--batch-size','4',
                 '--adapter',OUT/'train512/final/adapter-vllm']
        if extended:command+=['--cap','81920','--context','98304']
        run(command,label,gpu=True,inputs=[path,HERE/'AMENDMENT-FIT-CHECK.md'])
    generate_probe(job_path)
    capped=[j for j in jobs if read(OUT/'fit512-probe'/f"{j['id']}-0.json")['finish_reason']=='length']
    if capped:
        extension=OUT/'fit512-probe-extension-jobs.json';write(extension,capped);generate_probe(extension,True)
    write(OUT/'fit512-completion.json',{'status':'generated','end_unix':time.time(),'probe_count':4,
                                      'extended_jobs':[r['id'] for r in capped]})


if __name__=='__main__':main()
