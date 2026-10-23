import urllib.request, hashlib, json, datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parent
LIMIT=5_000_000

def fetch(url, name=None):
    rec={'url':url,'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'limit_bytes':LIMIT}
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Q26-public-research/1.0'}),timeout=35) as r:
            data=r.read(LIMIT+1)
            if len(data)>LIMIT: raise ValueError('response exceeds 5 MB limit')
            rec.update(status=r.status,bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
        if name: (ROOT/name).write_bytes(data); rec['saved_as']=name
    except Exception as e:
        rec.update(status='未取得',reason=str(e)); data=None
    with (ROOT/'fetch-log.jsonl').open('a') as f: f.write(json.dumps(rec,ensure_ascii=False)+'\n')
    return data
if __name__=='__main__':
    b=fetch('https://matharena.ai/','site.html')
    if b:
        for line in b.decode().splitlines():
            if any(x in line for x in ['fetch(','.json','script src','script defer src','dataUrl','data_url']): print(line[:1000])
