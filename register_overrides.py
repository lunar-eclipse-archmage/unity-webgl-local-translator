"""Explicitly register existing local patches; no translation, packing or copying."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'python_libs'))
import argparse,re,time
import local as cfg
from modules.common import ROOT,read_json,write_json,digest,TaskLock,warn_override_path

def register(paths=None):
    root=Path(cfg.OVERRIDES_ROOT).resolve()
    if not root.is_dir():raise ValueError('Overrides目录不存在：'+str(root))
    selections=[Path(p).resolve() for p in paths] if paths else [root]
    files=set()
    for p in selections:
        if not p.is_relative_to(root):raise ValueError('只能登记Overrides目录内的文件：'+str(p))
        if not p.exists():raise ValueError('路径不存在：'+str(p))
        files.update(p.rglob('*.bundle') if p.is_dir() else [p])
    if not files:raise ValueError('没有找到bundle文件')
    # Ambiguous hashes are never silently resolved, including unselected siblings.
    locations={}
    for p in root.rglob('*.bundle'):
        match=re.search(r'([a-fA-F0-9]{32})\.bundle$',p.name)
        if match:locations.setdefault(match[1].lower(),set()).add(str(p.resolve()))
    targets={}
    for p in sorted(files):
        p=p.resolve()
        if not p.is_relative_to(root) or not p.is_file():raise ValueError('文件必须位于Overrides内：'+str(p))
        match=re.search(r'([a-fA-F0-9]{32})\.bundle$',p.name)
        if not match:
            if 'longurls' in p.relative_to(root).parts:raise ValueError('发现DevTools longurls短文件：'+str(p)+'；当前不支持短文件名登记。请使用短Overrides根路径并恢复原完整Bundle名称及资源目录')
            raise ValueError('文件名末尾需要32位bundle哈希：'+p.name)
        key=match[1].lower()
        if len(locations.get(key,set()))!=1:raise ValueError('同一bundle哈希存在多个文件，请先明确保留版本：'+key)
        before=p.stat()
        if before.st_size<=0:raise ValueError('空文件：'+p.name)
        data=p.read_bytes()
        if not data.startswith(b'UnityFS\x00'):raise ValueError('仅支持UnityFS Bundle，请确认补丁格式：'+p.name)
        after=p.stat()
        if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('读取期间文件发生变化：'+p.name)
        relative=p.relative_to(root).as_posix()
        if len(Path(relative).parts)<2:raise ValueError('缺少资源主机名目录，请保留DevTools Overrides目录结构：'+p.name)
        warn_override_path(root,relative)
        targets[key]={'file':p.name,'bytes':len(data),'sha256':digest(data),'override_path':relative,'hash':key,'registration':'manual_override','registered_at':time.strftime('%Y-%m-%dT%H:%M:%S%z')}
    with TaskLock(ROOT/'.deployment.lock'):
        record=ROOT/'deployed.json'
        manifest=read_json(record) if record.exists() else {'targets':{}}
        if record.exists():write_json(ROOT/'backups'/('deployed_before_register_'+str(time.time_ns())+'.json'),manifest)
        for key,value in targets.items():
            old=manifest['targets'].get(key,{})
            # Preserve source linkage only if existing binary/path are unchanged.
            manifest['targets'][key]={**old,**value} if old.get('sha256')==value['sha256'] and old.get('override_path','').replace('\\','/')==value['override_path'] else value
        write_json(record,manifest)
    for item in targets.values():print('已登记：'+item['override_path']+'；'+str(item['bytes'])+'字节')
    print('登记完成：'+str(len(targets))+'个；请检查本地服务，然后清理补丁缓存并刷新')
    return targets

def main():
    parser=argparse.ArgumentParser(description='登记已放入Overrides的补丁；默认递归登记整个Overrides。用户须确认选择的文件确为要使用的补丁。')
    parser.add_argument('paths',nargs='*',help='Overrides内的文件或文件夹；不填写时登记整个Overrides')
    args=parser.parse_args()
    try:register(args.paths)
    except Exception as error:print('登记失败：'+str(error),file=sys.stderr);return 1
    return 0
if __name__=='__main__':raise SystemExit(main())
