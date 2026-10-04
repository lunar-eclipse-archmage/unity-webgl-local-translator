import json,re,time,urllib.request,urllib.error,threading
from .translation_prompt import instructions, PROMPT_VERSION
from .translation_validation import REFUSAL
from collections import Counter
from concurrent.futures import ThreadPoolExecutor,as_completed
from .common import ROOT,read_json,write_json,digest,log
TOKEN=re.compile(r'<[^>\n]+>|\\[nrt]|\{[^{}\n]+\}|%\d*\$?[sdif]|\r\n|\n|\r')
def protect(text):
    if '⟦KEEP_' in text:raise ValueError('原文与保护标记冲突')
    parts=[]
    def sub(m):parts.append(m.group());return f'⟦KEEP_{len(parts)-1}⟧'
    return TOKEN.sub(sub,text),parts
def restore(text,parts):
    if re.search(r'⟦KEEP_(?!\d+⟧)',text):raise ValueError('未知或格式错误的保护标记')
    ids=re.findall(r'⟦KEEP_(\d+)⟧',text)
    if ids!=[str(i) for i in range(len(parts))]:raise ValueError('标签/变量/换行保护校验失败')
    text=re.sub(r'⟦KEEP_(\d+)⟧',lambda m:parts[int(m.group(1))],text)
    return text
class TranslationBlocked(RuntimeError):
    pass

def ask(rows,cfg,glossary,diagnostic=None,context=None):
    schema={'type':'object','properties':{'translations':{'type':'object','properties':{r['id']:{'type':'string'} for r in rows},'required':[r['id'] for r in rows],'additionalProperties':False}},'required':['translations'],'additionalProperties':False}
    payload={'model':cfg.MODEL,'store':False,'max_output_tokens':cfg.MAX_OUTPUT_TOKENS,'instructions':instructions(cfg.TARGET_LANGUAGE,glossary),'input':json.dumps({'context':context or [],'rows':rows},ensure_ascii=False),'text':{'format':{'type':'json_schema','name':'bundle_translation','strict':True,'schema':schema}}}
    effort=getattr(cfg,'REASONING_EFFORT',None)
    if effort and cfg.MODEL.startswith('gpt-6'):
        payload['reasoning']={'effort':effort}
    req=urllib.request.Request(cfg.BASE_URL.rstrip('/')+'/responses',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+cfg.OPENAI_API_KEY,'Content-Type':'application/json'})
    for attempt in range(cfg.API_RETRIES+1):
        try:
            with urllib.request.urlopen(req,timeout=cfg.API_TIMEOUT) as response:
                request_id=response.headers.get('x-request-id')
                result=json.load(response)
            if diagnostic:write_json(diagnostic,{'request_id':request_id,'response':result})
            if result.get('status')!='completed':raise TranslationBlocked('API未完成：'+str(result.get('status'))+' '+str(result.get('incomplete_details')))
            output=[]
            for item in result.get('output',[]):
                for part in item.get('content',[]):
                    if part.get('type')=='refusal':raise TranslationBlocked('API拒绝：'+str(part.get('refusal','API未提供具体说明')))
                    if part.get('type')=='output_text':output.append(part['text'])
            def unique_object(pairs):
                result={}
                for key,value in pairs:
                    if key in result:raise TranslationBlocked('API返回重复JSON键：'+str(key))
                    result[key]=value
                return result
            try:values=json.loads(''.join(output),object_pairs_hook=unique_object)['translations']
            except (json.JSONDecodeError,KeyError) as e:raise TranslationBlocked('API返回格式无效，请查看response.json：'+str(e)) from None
            if isinstance(values,dict):values=[{'id':k,'text':v} for k,v in values.items()]
            return values,result.get('usage',{})
        except urllib.error.HTTPError as e:
            if e.code not in (429,500,502,503,504):raise TranslationBlocked(f'API HTTP {e.code}；检查模型、余额或配置，暂停自动重试') from None
            if attempt==cfg.API_RETRIES:raise RuntimeError(f'API HTTP {e.code}，临时错误重试已耗尽') from None
            wait=min(2**attempt*2,30);log(f'API HTTP {e.code}，{wait}s后重试');time.sleep(wait)
        except (urllib.error.URLError,TimeoutError):
            if attempt==cfg.API_RETRIES:raise RuntimeError('API网络连接失败或超时') from None
            time.sleep(min(2**attempt*2,30))
def translate(work,cfg):
    extracted=read_json(work/'extracted.json');rows=extracted['rows']
    if not cfg.OPENAI_API_KEY:raise ValueError('请在local.py设置OPENAI_API_KEY')
    glossary=read_json(ROOT/cfg.GLOSSARY_FILE)
    fingerprint=digest(json.dumps({'model':cfg.MODEL,'target':cfg.TARGET_LANGUAGE,'glossary':glossary,'prompt_version':PROMPT_VERSION,'reasoning_effort':getattr(cfg,'REASONING_EFFORT',None)},sort_keys=True,ensure_ascii=False).encode())
    cache_path=work/'translation_cache.json';cache=read_json(cache_path) if cache_path.exists() else {'fingerprint':fingerprint,'entries':{}}
    if cache.get('fingerprint')!=fingerprint:
        write_json(work/f'translation_cache_backup_{time.time_ns()}.json',cache)
        log('模型或提示词已更改：旧缓存已备份，本次翻译使用新规则')
        cache={'fingerprint':fingerprint,'entries':{}}
    missing=[r for r in rows if r['id'] not in cache['entries'] or cache['entries'][r['id']]['source']!=r['source']]
    blocked_path=work/'blocked.json'
    if blocked_path.exists():
        blocked=read_json(blocked_path)
        if missing and blocked.get('fingerprint')==fingerprint and blocked.get('source_sha256')==extracted['source_sha256']:
            raise TranslationBlocked('任务已暂停：'+blocked.get('reason','需要人工处理')+'；查看blocked.json/failed_batches')
    lock=threading.Lock()
    def save(batch,values):
        with lock:
            for row in batch:
                if row['id'] in values:cache['entries'][row['id']]={'source':row['source'],'translation':values[row['id']]}
            write_json(cache_path,cache)
    batches=[];batch=[];size=0
    for row in missing:
        if batch and (size+len(row['source'])>cfg.BATCH_CHARACTERS or len(batch)>=getattr(cfg,'MAX_BATCH_ITEMS',40)):batches.append(batch);batch=[];size=0
        batch.append(row);size+=len(row['source'])
    if batch:batches.append(batch)
    log(f"{extracted['file']} 翻译：{len(rows)}条，已缓存{len(rows)-len(missing)}条，待请求{len(batches)}批")
    def run(index,batch):
        positions={r['id']:i for i,r in enumerate(rows)}
        lo=max(0,min(positions[r['id']] for r in batch)-4)
        hi=min(len(rows),max(positions[r['id']] for r in batch)+5)
        groups={(r.get('asset'),r.get('path_id')) for r in batch}
        context=[{'id':r['id'],'text':r['source']} for r in rows[lo:hi] if (r.get('asset'),r.get('path_id')) in groups]
        remaining=batch[:]
        for attempt in range(getattr(cfg,'ID_RETRIES',2)+1):
            protected=[];parts={}
            for row in remaining:
                text,marks=protect(row['source']);parts[row['id']]=marks;protected.append({'id':row['id'],'text':text})
            folder=work/'failed_batches'
            stem=f'batch_{index+1}_attempt_{attempt+1}'
            write_json(folder/(stem+'_input.json'),{'rows':remaining,'context':context})
            log(f'翻译批次{index+1}/{len(batches)}：请求{attempt+1}，{len(remaining)}条')
            try:
                outputs,usage=ask(protected,cfg,glossary,folder/(stem+'_response.json'),context=context)
            except Exception as e:
                write_json(folder/(stem+'_error.json'),{'reason':str(e),'ids':[r['id'] for r in remaining]})
                raise
            ids=[o.get('id') for o in outputs if isinstance(o,dict)]
            counts=Counter(ids);duplicates=[k for k,n in counts.items() if n>1]
            expected=set(parts);returned=set(ids)
            missing_ids=sorted(expected-returned);extra_ids=sorted(str(x) for x in returned-expected)
            accepted={};invalid={}
            for item in outputs:
                if not isinstance(item,dict):continue
                key=item.get('id')
                if key not in expected or counts[key]!=1:continue
                try:
                    if not isinstance(item.get('text'),str) or not item['text']:raise ValueError('空译文或非字符串')
                    value=restore(item['text'],parts[key])
                    source=next(r['source'] for r in remaining if r['id']==key)
                    if REFUSAL.search(value) and not REFUSAL.search(source):raise ValueError('疑似API拒绝说明，暂停人工核对')
                    accepted[key]=value
                except Exception as e:invalid[key]=str(e)
            save(remaining,accepted)
            remaining=[r for r in remaining if r['id'] not in accepted]
            log(f'翻译批次{index+1}：保存{len(accepted)}条，剩余{len(remaining)}条；token用量 {usage}')
            details={'missing':missing_ids,'duplicates':duplicates,'extra':extra_ids,'invalid':invalid,'remaining_ids':[r['id'] for r in remaining]}
            if remaining or missing_ids or duplicates or extra_ids or invalid:
                write_json(folder/(stem+'_validation.json'),details)
                log('ID/标签校验差异：'+json.dumps(details,ensure_ascii=False))
            if any('API拒绝说明' in reason for reason in invalid.values()):
                raise TranslationBlocked('译文中出现疑似API拒绝说明；有效译文已保存，暂停该批次')
            if not remaining:return
        raise TranslationBlocked('ID/标签校验重试耗尽；有效译文已保存，剩余条目暂停待人工处理')
    failures=[];blocked_reasons=[]
    with ThreadPoolExecutor(max_workers=cfg.TRANSLATION_WORKERS) as pool:
        futures=[pool.submit(run,i,b) for i,b in enumerate(batches)]
        for future in as_completed(futures):
            try:future.result()
            except Exception as e:
                failures.append(str(e));log('翻译批次失败：'+str(e))
                if isinstance(e,TranslationBlocked):blocked_reasons.append(str(e))
    remaining=[r for r in rows if r['id'] not in cache['entries'] or cache['entries'][r['id']]['source']!=r['source']]
    write_json(work/'pending.json',{'file':extracted['file'],'rows':[{**r,'translation':''} for r in remaining]})
    if blocked_reasons:
        write_json(blocked_path,{'fingerprint':fingerprint,'source_sha256':extracted['source_sha256'],'reason':blocked_reasons[0],'remaining_ids':[r['id'] for r in remaining]})
        raise TranslationBlocked('暂停自动重试；成功译文已保存。'+blocked_reasons[0])
    if failures or remaining:raise RuntimeError('存在未完成批次，可重跑续传；不会打包或部署。'+(failures[0] if failures else '译文不完整'))
    if blocked_path.exists():blocked_path.unlink()
    output={**extracted,'rows':[{**r,'translation':cache['entries'][r['id']]['translation']} for r in rows]}
    write_json(work/'translated.json',output)
    return output
