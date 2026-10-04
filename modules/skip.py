import re
import UnityPy
from pathlib import Path
from .common import ROOT,read_json,digest,log
from .extract import extract
KANA=re.compile(r'[\u3041-\u3096\u30a1-\u30fa\uff66-\uff9d]')
HAN=re.compile(r'[\u3400-\u9fff]')
def already_translated(bundle,work,cfg):
    source=read_json(work/'extracted.json')
    text=''.join(r['source'] for r in source['rows'])
    deployed=ROOT/'deployed.json'
    if deployed.exists():
        for item in read_json(deployed).get('targets',{}).values():
            if item.get('file')!=bundle.name:continue
            root=Path(cfg.OVERRIDES_ROOT) if cfg.OVERRIDES_ROOT else None
            relative=item.get('override_path')
            target=root/Path(relative) if root and relative else None
            if target and target.exists() and item.get('source_sha256')==source['source_sha256'] and digest(target.read_bytes())==item.get('sha256'):
                log(bundle.name+' 跳过API：同一原始版本已经部署，文件校验一致');return True
    return False
