import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/"python_libs"))
# Import user-completed pending.json, with no API calls.
import argparse,json
import local as cfg
from pathlib import Path
from modules.common import ROOT,read_json,write_json,log,digest
from modules.translate import protect
from modules.translation_prompt import PROMPT_VERSION

def _main():
    ap=argparse.ArgumentParser();ap.add_argument('work_folder');ap.add_argument('translated_pending');args=ap.parse_args()
    work=Path(args.work_folder);original=read_json(work/'extracted.json')
    cache_path=work/'translation_cache.json'
    if cache_path.exists():
        cache=read_json(cache_path)
    else:
        # A request can fail before the first successful cache write.
        # Match translate()'s current fingerprint so imported rows can resume.
        glossary=read_json(ROOT/cfg.GLOSSARY_FILE)
        fingerprint=digest(json.dumps({'model':cfg.MODEL,'target':cfg.TARGET_LANGUAGE,'glossary':glossary,'prompt_version':PROMPT_VERSION,'reasoning_effort':getattr(cfg,'REASONING_EFFORT',None)},sort_keys=True,ensure_ascii=False).encode())
        cache={'fingerprint':fingerprint,'entries':{}}
    provided=read_json(args.translated_pending)
    expected={r['id']:r for r in original['rows']};updates={}
    for row in provided['rows']:
        key=row['id'];text=row.get('translation','')
        if not text:continue
        if key not in expected or row['source']!=expected[key]['source']:raise ValueError('原文或ID不匹配：'+key)
        if key in updates:raise ValueError('重复ID：'+key)
        if protect(row['source'])[1]!=protect(text)[1]:raise ValueError('标签/变量/换行不匹配：'+key)
        updates[key]={'source':row['source'],'translation':text}
    cache['entries'].update(updates);write_json(work/'translation_cache.json',cache)
    remaining=[r for r in original['rows'] if r['id'] not in cache['entries'] or cache['entries'][r['id']]['source']!=r['source']]
    write_json(work/'pending.json',{'file':original['file'],'rows':[{**r,'translation':''} for r in remaining]})
    if not remaining:
        write_json(work/'translated.json',{**original,'rows':[{**r,'translation':cache['entries'][r['id']]['translation']} for r in original['rows']]})
        (work/'blocked.json').unlink(missing_ok=True)
    log(f'导入{len(updates)}条，剩余{len(remaining)}条；'+('可运行pack和deploy' if not remaining else '继续补充pending.json'))
if __name__=='__main__':
    from modules.common import TaskLock
    if len(sys.argv)<2: _main()
    else:
        with TaskLock(Path(sys.argv[1])/'.task.lock'): _main()

