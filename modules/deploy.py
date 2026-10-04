import json,os,re,shutil,datetime
from pathlib import Path,PurePosixPath
from .common import ROOT,read_json,write_json,digest,log,warn_override_path
from .translation_validation import validate_task,translation_hash

def deploy(bundle,work,cfg):
    translated=validate_task(work)
    manifest=read_json(work/'packed.json');patched=work/Path(bundle).name
    if digest(Path(bundle).read_bytes())!=translated['source_sha256']:raise ValueError('输入bundle与译文来源不同')
    if manifest.get('source_sha256')!=translated['source_sha256']:raise ValueError('打包来源与译文不同')
    if manifest.get('translation_sha256')!=translation_hash(work):raise ValueError('译文已更改或旧打包报告缺少译文校验；请先重新pack')
    if digest(patched.read_bytes())!=manifest['sha256']:raise ValueError('已打包文件与验证报告不一致')
    relative=cfg.OVERRIDE_PATHS.get(patched.name)
    sidecar=Path(str(bundle)+'.source.json')
    if not relative and sidecar.exists():relative=read_json(sidecar).get('override_path')
    if not cfg.OVERRIDES_ROOT:raise ValueError('local.py尚未设置OVERRIDES_ROOT；文件已打包，暂不复制')
    if not relative:raise ValueError('缺少精确Overrides路径，请在local.py的OVERRIDE_PATHS设置：'+patched.name)
    route=PurePosixPath(relative.replace('\\','/'))
    if route.is_absolute() or '..' in route.parts or any(':' in p for p in route.parts):raise ValueError('Overrides路径必须为安全相对路径')
    if route.name!=patched.name:raise ValueError('路径末尾必须是原bundle文件名；带query的请求需手动核对并另行适配')
    root=Path(cfg.OVERRIDES_ROOT).resolve();destination=root.joinpath(*route.parts).resolve()
    if not destination.is_relative_to(root):raise ValueError('路径超出Overrides根目录')
    warn_override_path(root,Path(*route.parts))
    match=re.search(r'([a-fA-F0-9]{32})\.bundle$',patched.name)
    if not match:raise ValueError('文件名末尾没有32位bundle hash，需要手动适配catalog')
    targets_path=ROOT/'deployed.json';targets=read_json(targets_path) if targets_path.exists() else {'targets':{}}
    entry={**manifest,'override_path':str(route),'hash':match[1].lower()}
    old=targets['targets'].get(entry['hash'])
    if old and old.get('override_path','').replace('\\','/')==str(route) and old.get('sha256')==entry['sha256'] and destination.exists() and digest(destination.read_bytes())==entry['sha256']:
        log(patched.name+' 已部署且内容一致，跳过复制');return
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists():
        backup=ROOT/'backups'/datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')/Path(*route.parts)
        backup.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(destination,backup)
    temp=destination.with_name(destination.name+'.translation.tmp');shutil.copyfile(patched,temp)
    if digest(temp.read_bytes())!=manifest['sha256']:raise ValueError('复制校验失败')
    # No game reads these files until the next load; manifest published only after copy.
    os.replace(temp,destination)
    targets['targets'][entry['hash']]=entry;write_json(targets_path,targets)
    log(patched.name+' 已部署到 '+str(destination)+'；下次游戏启动读取')
