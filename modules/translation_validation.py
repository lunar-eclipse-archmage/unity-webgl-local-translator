"""部署前的任务状态与文本校验，不调用API。"""
import re
from .common import read_json, digest
REFUSAL = re.compile(r'(?:我|我们)?(?:无法|不能|不便|不予).{0,16}(?:翻译|提供这类内容)|可以(?:协助|帮助).{0,20}(?:非露骨|删去露骨|剧情概述)|I (?:cannot|can\'t|am unable to) (?:translate|provide)', re.I)
def validate_task(work):
    if (work/'blocked.json').exists():
        raise ValueError('任务有blocked.json，禁止打包/部署；人工修正完成后先核对任务状态')
    if (work/'pending.json').exists() and read_json(work/'pending.json').get('rows'):
        raise ValueError('任务仍有pending条目，禁止打包/部署')
    extracted=read_json(work/'extracted.json')
    translated=read_json(work/'translated.json')
    if extracted['source_sha256']!=translated['source_sha256']:
        raise ValueError('提取版本与译文版本不同')
    source={r['id']:r for r in extracted['rows']}
    rows=translated['rows']
    if len(source)!=len(extracted['rows']) or len(rows)!=len(source) or {r['id'] for r in rows}!=set(source):
        raise ValueError('译文ID集合不完整或重复')
    for r in rows:
        original=source[r['id']]
        if any(r.get(k)!=original.get(k) for k in ('source','asset','path_id','mode','path')):
            raise ValueError('译文定位或原文变化：'+r['id'])
        value=r.get('translation')
        if not isinstance(value,str) or not value.strip():raise ValueError('空译文：'+r['id'])
        if REFUSAL.search(value) and not REFUSAL.search(r['source']):
            raise ValueError('疑似API拒绝说明：'+r['id']+'；请核对译文')
    return translated

def translation_hash(work):
    return digest((work/'translated.json').read_bytes())
