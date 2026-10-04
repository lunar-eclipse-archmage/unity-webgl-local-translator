import re
from pathlib import Path
import UnityPy
from .common import digest,write_json,log
LANG=re.compile(r'[\u3040-\u30ff\u3400-\u9fff]')
DISPLAY={'m_text','m_Text','m_sDisplayText','defaultValue'}
JSON_TEXT={'text','Text','message','Message','title','description','dialogue','content','name_ja','text_ja'}
def candidates(tree,path=()):
    if isinstance(tree,dict):
        for key,value in tree.items():
            route=path+(key,)
            if isinstance(value,str) and key in DISPLAY and LANG.search(value):yield route,value
            elif route==('textMap','idToText','values') and isinstance(value,list):
                for i,text in enumerate(value):
                    if isinstance(text,str) and LANG.search(text):yield route+(i,),text
            elif isinstance(value,(dict,list)):yield from candidates(value,route)
    elif isinstance(tree,list):
        for i,value in enumerate(tree):
            if isinstance(value,(dict,list)):yield from candidates(value,path+(i,))
def json_candidates(tree,path=()):
    if isinstance(tree,dict):
        for k,v in tree.items():
            if isinstance(v,str) and k in JSON_TEXT and LANG.search(v):yield path+(k,),v
            elif isinstance(v,(dict,list)):yield from json_candidates(v,path+(k,))
    elif isinstance(tree,list):
        for i,v in enumerate(tree):
            if isinstance(v,(dict,list)):yield from json_candidates(v,path+(i,))
def extract(bundle,work,cfg=None):
    story_only=getattr(cfg,'STORY_ONLY',True)
    minimum=getattr(cfg,'MIN_STORY_CHARACTERS',300)
    import json
    bundle=Path(bundle);raw=bundle.read_bytes();env=UnityPy.load(raw)
    rows=[];errors=[];types={};skipped=[]
    for obj in env.objects:
        kind=obj.type.name;types[kind]=types.get(kind,0)+1
        if kind not in ('MonoBehaviour','TextAsset'):continue
        try:
            if kind=='MonoBehaviour':
                found=list(candidates(obj.read_typetree()));mode='typetree'
                story=[(p,t) for p,t in found if p[:3]==('textMap','idToText','values')]
                if story_only:
                    if sum(len(t) for _,t in story)<minimum:
                        if found: skipped.append({'path_id':str(obj.path_id),'reason':'非剧情字段或整段剧情总长度不足'})
                        continue
                    found=story
            else:
                item=obj.read();text=item.m_Script
                if isinstance(text,bytes):text=text.decode('utf-8')
                if not LANG.search(text):continue
                try:tree=json.loads(text)
                except json.JSONDecodeError:tree=None
                if isinstance(tree,dict) and ('skeleton' in tree or 'bones' in tree):
                    skipped.append({'path_id':str(obj.path_id),'reason':'Spine动画JSON'});continue
                if tree is not None:
                    if story_only:
                        skipped.append({'path_id':str(obj.path_id),'reason':'未知JSON结构，默认不作为剧情自动翻译'});continue
                    found=list(json_candidates(tree));mode='textasset_json'
                elif '.png' in text and ('bounds:' in text or 'size:' in text):
                    skipped.append({'path_id':str(obj.path_id),'reason':'atlas资源数据'});continue
                elif sum(ord(c)<32 and c not in '\n\r\t' for c in text)/max(len(text),1)>.01:
                    skipped.append({'path_id':str(obj.path_id),'reason':'疑似二进制'});continue
                else:
                    if story_only and (len(text)<getattr(cfg,'MIN_PLAIN_TEXT_CHARACTERS',600) or len(LANG.findall(text))/max(len(text),1)<getattr(cfg,'MIN_JAPANESE_RATIO',0.15)):
                        skipped.append({'path_id':str(obj.path_id),'reason':'纯文本过短或日文比例不足'});continue
                    found=[((),text)];mode='textasset'
            for path,text in found:
                rows.append({'id':str(len(rows)),'asset':obj.assets_file.name,'path_id':str(obj.path_id),'mode':mode,'path':list(path),'source':text})
        except Exception as e:errors.append({'path_id':str(obj.path_id),'type':kind,'error':str(e)[:500]})
    result={'file':bundle.name,'source_sha256':digest(raw),'types':types,'rows':rows,'errors':errors,'skipped':skipped,'policy':{'story_only':story_only,'minimum_story_characters':minimum}}
    write_json(work/'extracted.json',result)
    log(f'{bundle.name} 提取完成：文案{len(rows)}，解析错误{len(errors)}，跳过{len(skipped)}项')
    for reason in sorted(set(x['reason'] for x in skipped)):log(bundle.name+' 跳过原因：'+reason)
    for error in errors[:3]:log(bundle.name+' 解析错误：'+str(error))
    return result
