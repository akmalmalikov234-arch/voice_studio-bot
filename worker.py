import os, json, time, uuid, random, mimetypes, logging, tempfile
from pathlib import Path
import requests

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(message)s')
BACKEND=os.getenv('BACKEND_URL','').rstrip('/')
WORKER_KEY=os.getenv('WORKER_KEY','').strip()
WORKER_NAME=os.getenv('WORKER_NAME','local-gpu-1')
COMFY_URL=os.getenv('COMFY_URL','http://127.0.0.1:8188').rstrip('/')
CHECKPOINT=os.getenv('COMFY_CHECKPOINT','').strip()
POLL=float(os.getenv('POLL_SECONDS','2'))
TIMEOUT=int(os.getenv('JOB_TIMEOUT','1800'))

if not BACKEND or not WORKER_KEY:
    raise SystemExit('BACKEND_URL va WORKER_KEY ni environmentga kiriting.')


def headers(): return {'X-Worker-Key':WORKER_KEY}

def comfy_json(path, payload=None, method='get'):
    url=COMFY_URL+path
    if method=='post':
        r=requests.post(url,json=payload,timeout=30)
    else:
        r=requests.get(url,timeout=30)
    r.raise_for_status(); return r.json()


def native_sdxl_workflow(prompt, negative, size):
    try:w,h=[int(x) for x in size.lower().split('x')]
    except Exception:w,h=1024,1024
    # Standard ComfyUI API-format graph. The checkpoint filename is supplied by COMFY_CHECKPOINT.
    return {
      '3':{'class_type':'CheckpointLoaderSimple','inputs':{'ckpt_name':CHECKPOINT}},
      '6':{'class_type':'CLIPTextEncode','inputs':{'text':prompt,'clip':['3',1]}},
      '7':{'class_type':'CLIPTextEncode','inputs':{'text':negative or 'low quality, blurry, distorted, watermark','clip':['3',1]}},
      '5':{'class_type':'EmptyLatentImage','inputs':{'width':w,'height':h,'batch_size':1}},
      '4':{'class_type':'KSampler','inputs':{'seed':random.randint(1,2**31-1),'steps':28,'cfg':7,'sampler_name':'euler','scheduler':'normal','denoise':1.0,'model':['3',0],'positive':['6',0],'negative':['7',0],'latent_image':['5',0]}},
      '8':{'class_type':'VAEDecode','inputs':{'samples':['4',0],'vae':['3',2]}},
      '9':{'class_type':'SaveImage','inputs':{'filename_prefix':'VoiceStudio','images':['8',0]}}
    }


def inject_prompt(workflow,prompt,negative):
    # Works with most ComfyUI API-exported workflows without requiring custom nodes.
    wf=json.loads(workflow) if isinstance(workflow,str) else workflow
    text_nodes=[]
    for nid,node in wf.items():
        if not isinstance(node,dict): continue
        inp=node.get('inputs',{})
        if node.get('class_type') in ('CLIPTextEncode','CLIPTextEncodeSDXL','CLIPTextEncodeFlux') and 'text' in inp:
            text_nodes.append((nid,inp))
    if text_nodes:
        text_nodes[0][1]['text']=prompt
        if len(text_nodes)>1 and negative is not None: text_nodes[1][1]['text']=negative
    return wf


def submit(workflow):
    cid=str(uuid.uuid4())
    r=requests.post(COMFY_URL+'/prompt',json={'prompt':workflow,'client_id':cid},timeout=60)
    r.raise_for_status(); d=r.json()
    if d.get('error'): raise RuntimeError(str(d['error']))
    return d['prompt_id']


def wait_history(pid):
    started=time.time()
    while time.time()-started<TIMEOUT:
        r=requests.get(COMFY_URL+'/history/'+pid,timeout=30)
        if r.ok:
            d=r.json()
            item=d.get(pid)
            if item:
                state=item.get('status',{})
                if state.get('status_str')=='error':
                    raise RuntimeError(str(state.get('messages','ComfyUI error')))
                if state.get('completed'):
                    return item.get('outputs',{})
        time.sleep(2)
    raise TimeoutError('ComfyUI job timeout')


def first_output(outputs):
    for node in outputs.values():
        if not isinstance(node,dict): continue
        for typ in ('images','gifs','videos'):
            for item in node.get(typ,[]) or []:
                if item.get('filename'): return item, typ
    raise RuntimeError('ComfyUI natija faylini qaytarmadi')


def download_output(item):
    params={'filename':item['filename'],'subfolder':item.get('subfolder',''),'type':item.get('type','output')}
    r=requests.get(COMFY_URL+'/view',params=params,timeout=120);r.raise_for_status()
    suffix=Path(item['filename']).suffix or '.bin'
    fd,path=tempfile.mkstemp(prefix='voice_studio_',suffix=suffix);os.close(fd);Path(path).write_bytes(r.content)
    return path


def report(job_id,path=None,kind='image',error=''):
    data={'job_id':str(job_id),'status':'done' if path else 'failed','type':kind,'error':error}
    files={'file':(Path(path).name,open(path,'rb'),mimetypes.guess_type(path)[0] or 'application/octet-stream')} if path else None
    try:
        r=requests.post(BACKEND+'/worker/result',headers=headers(),data=data,files=files,timeout=180)
        r.raise_for_status();return r.json()
    finally:
        if files: files['file'][1].close()


def run_job(job):
    jid=job['id']; kind=job['kind']; prompt=job['prompt']; negative=job.get('negative',''); size=job.get('params',{}).get('size','1024x1024')
    workflow=job.get('workflow')
    if workflow: wf=inject_prompt(workflow,prompt,negative)
    elif kind=='image' and CHECKPOINT: wf=native_sdxl_workflow(prompt,negative,size)
    else: raise RuntimeError('Bu model uchun ComfyUI workflow sozlanmagan. Admin paneldan workflow JSON kiriting yoki COMFY_CHECKPOINT ni belgilang.')
    pid=submit(wf); logging.info('job #%s -> comfy %s',jid,pid)
    outputs=wait_history(pid); item,typ=first_output(outputs); path=download_output(item)
    out_kind='video' if typ in ('videos','gifs') or Path(path).suffix.lower() in ('.mp4','.webm','.mov','.gif') else 'image'
    report(jid,path,out_kind)
    os.unlink(path)


def main():
    logging.info('Worker %s -> %s | ComfyUI %s',WORKER_NAME,BACKEND,COMFY_URL)
    while True:
        try:
            try:
                chk=requests.get(COMFY_URL+'/system_stats',timeout=8)
                comfy_ready=chk.ok
            except requests.RequestException: comfy_ready=False
            if not comfy_ready:
                logging.warning('ComfyUI ulanmagan: %s',COMFY_URL)
                time.sleep(8)
                continue
            hb=requests.post(BACKEND+'/worker/heartbeat',headers=headers(),json={'default_image':bool(CHECKPOINT)},timeout=20)
            hb.raise_for_status()
            r=requests.get(BACKEND+'/worker/next',headers=headers(),timeout=30);r.raise_for_status();d=r.json();job=d.get('job')
            if not job:time.sleep(POLL);continue
            logging.info('Processing #%s %s',job['id'],job['name'])
            try:run_job(job)
            except Exception as e:
                logging.exception('job #%s failed',job['id']);report(job['id'],error=str(e)[:1000])
        except Exception as e:
            logging.warning('worker connection: %s',e);time.sleep(max(POLL,3))

if __name__=='__main__':main()
