# Catalog manifest for registered DevTools Overrides.
import hashlib,re,threading
from pathlib import Path
from .common import ROOT,read_json
LOCK=threading.Lock()
STATS={}
def manifest():
    import local as cfg
    deployed=ROOT/'deployed.json'
    result=read_json(deployed) if deployed.exists() else {'targets':{}}
    previous=dict(result.get('targets',{}))
    result['targets']={}
    root=Path(cfg.OVERRIDES_ROOT).resolve() if cfg.OVERRIDES_ROOT else None
    if not root or not root.is_dir():
        result['local_delivery_error']='OVERRIDES_ROOT未配置或不存在'
        return result
    files={};duplicates=set()
    for p in root.rglob('*.bundle'):
        if not p.is_file():continue
        resolved=p.resolve()
        if not resolved.is_relative_to(root):continue
        match=re.search(r'([a-fA-F0-9]{32})\.bundle$',p.name)
        if not match:continue
        key=match[1].lower()
        if key in files:duplicates.add(key)
        else:files[key]=resolved
    for key in duplicates:files.pop(key,None)
    with LOCK:
        live_signatures=set()
        for key,p in files.items():
            stat=p.stat();signature=(str(p),stat.st_mtime_ns,stat.st_size)
            live_signatures.add(signature)
            item=STATS.get(signature)
            if item is None:
                hasher=hashlib.sha256()
                with p.open('rb') as stream:
                    for block in iter(lambda:stream.read(1024*1024),b''):hasher.update(block)
                after=p.stat()
                if (after.st_mtime_ns,after.st_size)!=(stat.st_mtime_ns,stat.st_size):continue
                item={'file':p.name,'bytes':stat.st_size,'sha256':hasher.hexdigest(),'override_path':p.relative_to(root).as_posix(),'local_available':True}
                STATS[signature]=item
            recorded=previous.get(key)
            if not recorded or recorded.get('sha256')!=item['sha256'] or recorded.get('override_path','').replace('\\','/')!=item['override_path']: continue
            result['targets'][key]={**recorded,**item}
        for signature in list(STATS):
            if signature not in live_signatures:STATS.pop(signature,None)
    result['delivery_mode']='devtools_overrides'
    result['duplicate_hashes']=sorted(duplicates)
    return result
