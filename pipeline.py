import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/"python_libs"))
import argparse,time
from pathlib import Path
import local as cfg
from modules.common import ROOT,work_for,read_json,log,TaskLock
from modules.extract import extract
from modules.translate import translate,TranslationBlocked
from modules.pack import pack
from modules.deploy import deploy
from modules.skip import already_translated

def _process(bundle,stage):
    work=work_for(bundle);work.mkdir(parents=True,exist_ok=True)
    if stage in ('all','extract'):result=extract(bundle,work,cfg)
    else:result=read_json(work/'extracted.json')
    if not result['rows']:
        log(bundle.name+' 无已识别可翻译文案；跳过API/打包/部署');return
    if stage in ('all','translate'):
        if already_translated(bundle,work,cfg):return
        translate(work,cfg)
    if stage in ('all','pack'):pack(bundle,work)
    if stage in ('all','deploy'):
        with TaskLock(ROOT/'.deployment.lock'):deploy(bundle,work,cfg)

def process(bundle,stage):
    work=work_for(bundle)
    with TaskLock(work/'.task.lock'):
        return _process(bundle,stage)

def main():
    ap=argparse.ArgumentParser(description='本地Unity bundle翻译流水线')
    ap.add_argument('stage',choices=['all','extract','translate','pack','deploy'])
    ap.add_argument('paths',nargs='*',help='bundle文件或包含bundle的目录；默认inbox')
    ap.add_argument('--watch',action='store_true',help='每5秒扫描，失败任务60秒后重试')
    args=ap.parse_args();done=set();retry={}
    while True:
        sources=[]
        for name in args.paths or [str(ROOT/'inbox')]:
            p=Path(name);sources.extend(p.rglob('*.bundle') if p.is_dir() else [p])
        failed=False
        conflicts=set()
        if args.stage in ('pack','deploy','all'):
            versions={}
            for item in set(sources):versions.setdefault(item.name.lower(),set()).add(str(item.resolve()))
            conflicts={name for name,paths in versions.items() if len(paths)>1}
            for name in sorted(conflicts):
                log(name+' 同名输入有多个版本，全部跳过；请指定唯一原始bundle路径');failed=True
        for bundle in sorted(set(sources)):
            if bundle.name.lower() in conflicts:continue
            signature=None
            try:
                signature=(str(bundle.resolve()),bundle.stat().st_mtime_ns,bundle.stat().st_size)
                if signature in done or time.monotonic()<retry.get(signature,0):continue
                process(bundle,args.stage);done.add(signature)
            except TranslationBlocked as e:
                log(bundle.name+' 已暂停：'+str(e));failed=True
                if signature is not None:done.add(signature)
            except Exception as e:
                log(bundle.name+' 失败：'+str(e));failed=True
                if signature is not None:retry[signature]=time.monotonic()+60
        if not args.watch:return 1 if failed else 0
        time.sleep(5)
if __name__=='__main__':
    try:raise SystemExit(main())
    except KeyboardInterrupt:log('流水线已停止；已完成翻译批次保留，可重跑续传')
