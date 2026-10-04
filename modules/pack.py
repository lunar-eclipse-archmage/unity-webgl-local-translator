import json,os
from pathlib import Path
import UnityPy
from .common import read_json,write_json,digest,log
from .translate import protect,restore
from .translation_validation import validate_task,translation_hash
def set_value(tree,path,value):
    node=tree
    for key in path[:-1]:node=node[key]
    node[path[-1]]=value
def pack(bundle,work):
    raw=Path(bundle).read_bytes();translated=validate_task(work)
    if digest(raw)!=translated['source_sha256']:raise ValueError('原bundle已变化，拒绝回写')
    rows=translated['rows']
    if not rows:raise ValueError('无可翻译文案，不打包')
    for row in rows:
        if not isinstance(row.get('translation'),str) or (row['source'] and not row['translation']):raise ValueError('译文缺失或为空')
        # Check actual protected sequences again after any manual editing.
        _,source_marks=protect(row['source']);_,translated_marks=protect(row['translation'])
        if source_marks!=translated_marks:raise ValueError('译文标签/变量/换行与原文不同：'+row['id'])
    env=UnityPy.load(raw);orig=UnityPy.load(raw)
    groups={}
    for row in rows:groups.setdefault((row['asset'],row['path_id']),[]).append(row)
    expected={}
    for obj in env.objects:
        key=(obj.assets_file.name,str(obj.path_id))
        if key not in groups:continue
        entries=groups[key];mode=entries[0]['mode']
        if mode=='typetree':
            tree=obj.read_typetree()
            for row in entries:set_value(tree,row['path'],row['translation'])
            obj.save_typetree(tree);expected[key]=('tree',tree)
        else:
            item=obj.read()
            if mode=='textasset_json':
                text=item.m_Script.decode('utf-8') if isinstance(item.m_Script,bytes) else item.m_Script
                tree=json.loads(text)
                for row in entries:set_value(tree,row['path'],row['translation'])
                text=json.dumps(tree,ensure_ascii=False,separators=(',',':'))
            else:text=entries[0]['translation']
            item.m_Script=text;item.save();expected[key]=('text',text)
    if set(expected)!=set(groups):raise ValueError('未找到全部目标资源')
    output=work/Path(bundle).name;temp=output.with_suffix('.bundle.tmp');temp.write_bytes(env.file.save(packer='lz4'))
    rebuilt=UnityPy.load(temp.read_bytes());a={(o.assets_file.name,str(o.path_id)):o for o in orig.objects};b={(o.assets_file.name,str(o.path_id)):o for o in rebuilt.objects}
    if a.keys()!=b.keys():raise ValueError('资源ID集合变化')
    for key,obj in a.items():
        if key not in expected:
            if obj.get_raw_data()!=b[key].get_raw_data():raise ValueError('非目标资源变化：'+str(key))
        elif expected[key][0]=='tree':
            if expected[key][1]!=b[key].read_typetree():raise ValueError('回写字段验证失败：'+str(key))
        else:
            after=b[key].read().m_Script
            if isinstance(after,bytes):after=after.decode('utf-8')
            if after!=expected[key][1]:raise ValueError('TextAsset回写验证失败')
            before_tree=obj.read_typetree();after_tree=b[key].read_typetree()
            before_tree.pop('m_Script',None);after_tree.pop('m_Script',None)
            if before_tree!=after_tree:raise ValueError('TextAsset非文本字段变化')
    os.replace(temp,output)
    manifest={'file':output.name,'bytes':output.stat().st_size,'sha256':digest(output.read_bytes()),'fields':len(rows),'translation_sha256':translation_hash(work),'source_sha256':translated['source_sha256']}
    write_json(work/'packed.json',manifest);log(f'{output.name} 打包验证通过：{len(rows)}条；{manifest["bytes"]}字节')
    return output
