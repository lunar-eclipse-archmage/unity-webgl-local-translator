import hashlib, json, re, time, threading, hmac
from modules.common import TaskLock
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import unquote
import UnityPy
ROOT = Path(__file__).resolve().parents[1] / 'output'
ROOT.mkdir(exist_ok=True)
LOG_LOCK = threading.Lock()
def log(message):
    import local
    if not getattr(local,"LOG_ENABLED",True):return
    line=time.strftime('%H:%M:%S')+' '+message
    with LOG_LOCK:
        print(line, flush=True)
        with (ROOT/'server.log').open('a',encoding='utf-8') as f: f.write(line+'\n')
MAX = 128 * 1024 * 1024
CJK = re.compile(r'[\u3040-\u30ff\u3400-\u9fff]')
def strings(v, path=''):
    if isinstance(v, str):
        if CJK.search(v): yield {'field': path, 'text': v}
    elif isinstance(v, dict):
        for k, x in v.items():
            if k != 'm_Name': yield from strings(x, path + '/' + str(k))
    elif isinstance(v, list):
        for i, x in enumerate(v): yield from strings(x, path + '/' + str(i))
def inspect(data, progress=lambda x: None):
    started=time.monotonic()
    progress("开始UnityPy加载")
    env = UnityPy.load(data)
    progress(f"加载完成，耗时 {time.monotonic()-started:.2f}s；开始遍历资源")
    rows, errors, types = [], [], {}
    scanned=0
    for obj in env.objects:
        scanned+=1
        if scanned%1000==0: progress(f"已遍历 {scanned} 个资源；文本 {len(rows)}；错误 {len(errors)}")
        kind = obj.type.name
        types[kind] = types.get(kind, 0) + 1
        if kind not in ('TextAsset', 'MonoBehaviour'): continue
        try:
            if kind == 'TextAsset':
                item = obj.read()
                value = item.m_Script
                if isinstance(value, bytes): value = value.decode('utf-8')
                # TextAsset may contain binary data; exclude control-heavy content.
                if value and sum(ord(c)<32 and c not in '\n\r\t' for c in value)/len(value) < .01:
                    rows.append({'asset': obj.assets_file.name, 'path_id': obj.path_id, 'type': kind, 'name': item.m_Name, 'field': 'm_Script', 'text': value})
            else:
                for row in strings(obj.read_typetree()):
                    rows.append({'asset': obj.assets_file.name, 'path_id': obj.path_id, 'type': kind, **row})
        except Exception as e:
            errors.append({'path_id': obj.path_id, 'type': kind, 'error': str(e)[:300]})
    return {'status': '发现文本' if rows else ('无法完全确认' if errors else '未发现可读取文本'), 'count':len(rows), 'types':types, 'texts':rows, 'errors':errors}
class Handler(BaseHTTPRequestHandler):
    def answer(self, code, value):
        body=json.dumps(value, ensure_ascii=False).encode()
        self.send_response(code); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
    def authorized(self):
        import local
        token=getattr(local,'LOCAL_SERVICE_TOKEN','')
        supplied=self.headers.get('X-Local-Token','')
        if len(token)<32 or not hmac.compare_digest(token,supplied):
            self.close_connection=True
            self.answer(401,{'error':'本地服务认证失败；请配置至少32字符的LOCAL_SERVICE_TOKEN'})
            return False
        return True
    def do_HEAD(self):
        self.answer(405,{'error':'Unsupported HEAD'})
    def do_GET(self):
        if not self.authorized(): return
        if self.path == '/patches':
            from modules.local_bundles import manifest
            try:return self.answer(200,manifest())
            except Exception as e:
                log('本地清单失败：'+str(e))
                return self.answer(500,{'error':'本地bundle清单读取失败，请检查Overrides目录'})
        self.answer(200, {'status':'UnityPy collector running'})
    def do_POST(self):
        if not self.authorized(): return
        if self.path != '/inspect': return self.answer(404, {'error':'Unknown endpoint'})
        started=time.monotonic()
        task=re.sub(r'[^A-Za-z0-9_-]','_',self.headers.get('X-Task-ID','unknown'))[:80]
        name=re.sub(r'[^A-Za-z0-9._-]', '_', unquote(self.headers.get('X-Bundle-Name','unknown.bundle')))[:180]
        progress=lambda message: log(f'[{task}] {name} | {message}')
        progress('收到请求')
        try: size=int(self.headers.get('Content-Length','0'))
        except ValueError: return self.answer(400,{'error':'无效Content-Length'})
        if not 0<size<=MAX: return self.answer(413, {'error':'文件为空或超过128MiB'})
        self.connection.settimeout(180)
        data=self.rfile.read(size)
        progress(f"接收完成：{len(data)} 字节，耗时 {time.monotonic()-started:.2f}s")
        if len(data)!=size: return self.answer(400,{"error":"请求体长度不符"})
        name=re.sub(r'[^A-Za-z0-9._-]', '_', unquote(self.headers.get('X-Bundle-Name','unknown.bundle')))[:180]
        digest=hashlib.sha256(data).hexdigest()
        folder=ROOT / (name + '_' + digest[:12]); report=folder/'report.json'
        resource_lock=TaskLock(folder/'.resource.lock')
        try:
            resource_lock.__enter__()
            if report.exists():
                progress('复用已有检查报告')
                result=json.loads(report.read_text(encoding='utf-8'))
            else:
                result=inspect(data,progress); result.update(name=name, bytes=size, sha256=digest)
                progress(f"解析完成：类型 {result['types']}；文本 {result['count']}；错误 {len(result['errors'])}")
                for error in result['errors'][:5]: progress('解析错误 '+str(error))
                folder.mkdir(exist_ok=True)
                if result['count']:
                    (folder/name).write_bytes(data)
                    (folder/'texts.json').write_text(json.dumps(result['texts'], ensure_ascii=False, indent=2), encoding='utf-8')
                    (folder/'preview.txt').write_text('\n\n'.join(f"[{x['path_id']}] {x['field']}\n{x['text']}" for x in result['texts']),encoding='utf-8')
                report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            if result['count']:
                import os
                from urllib.parse import urlsplit
                inbox=ROOT.parent/'inbox'/digest[:12]
                inbox.mkdir(parents=True,exist_ok=True)
                bundle_path=inbox/name
                if not bundle_path.exists():
                    temporary=bundle_path.with_suffix('.tmp')
                    temporary.write_bytes(data);os.replace(temporary,bundle_path)
                relative=unquote(self.headers.get('X-Override-Path',''))
                parts=Path(relative.replace('\\','/')).parts
                if relative and '..' not in parts and ':' not in relative and not relative.startswith(('/', '\\')):
                    metadata=bundle_path.with_name(bundle_path.name+'.source.json')
                    if metadata.exists() and json.loads(metadata.read_text(encoding='utf-8')).get('override_path')!=relative:
                        return self.answer(409,{'error':'同一资源已有不同部署路径，请人工核对；原路径未覆盖'})
                    temporary=metadata.with_suffix('.tmp')
                    temporary.write_text(json.dumps({'override_path':relative},ensure_ascii=False),encoding='utf-8')
                    os.replace(temporary,metadata)
                progress('已保存到翻译inbox：'+str(bundle_path))
            progress('结果目录：'+str(folder))
            self.answer(200, {k:v for k,v in result.items() if k not in ('texts','errors')} | {'errors':len(result['errors']), 'saved':bool(result['count']), 'folder':str(folder)})
            progress(f"完成：{result['status']}；文本 {result['count']}；总耗时 {time.monotonic()-started:.2f}s")
        except Exception as e:
            progress('失败：'+repr(e))
            try: self.answer(422, {'error':str(e)[:500]})
            except OSError: progress('客户端已断开')
        finally:
            if hasattr(resource_lock,"stream") and not resource_lock.stream.closed: resource_lock.__exit__()
    def log_message(self, *args): pass
class PoolServer(HTTPServer):
    def __init__(self,*args):
        super().__init__(*args)
        self.slots=threading.BoundedSemaphore(12)
        self.pool=ThreadPoolExecutor(max_workers=3,thread_name_prefix='bundle')
    def process_request(self,request,address):
        if not self.slots.acquire(blocking=False):
            try: request.sendall(b'HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
            finally: self.shutdown_request(request)
            return
        self.pool.submit(self.worker,request,address)
    def worker(self,request,address):
        try: self.finish_request(request,address)
        except Exception: self.handle_error(request,address)
        finally:
            self.shutdown_request(request)
            self.slots.release()
    def server_close(self):
        super().server_close()
        self.pool.shutdown(wait=True)
if __name__=='__main__':
    print('服务已启动 http://127.0.0.1:8765；输出目录：',ROOT,flush=True)
    log('线程池并发数：3；详细日志：'+str(ROOT/'server.log'))
    with PoolServer(('127.0.0.1',8765),Handler) as server:
        try: server.serve_forever()
        except KeyboardInterrupt: pass
