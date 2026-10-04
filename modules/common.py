import hashlib,json,os,threading,time,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LOCK=threading.Lock()
def digest(data):return hashlib.sha256(data).hexdigest()
def read_json(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def write_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=path.parent)
    temp=Path(name)
    with os.fdopen(fd,'w',encoding='utf-8') as f:
        json.dump(value,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
    os.replace(temp,path)
def log(message):
    import local
    if not getattr(local,"LOG_ENABLED",True):return
    line=time.strftime('%H:%M:%S')+' '+message
    with LOCK:
        print(line,flush=True)
        (ROOT/'work').mkdir(exist_ok=True)
        with (ROOT/'work/pipeline.log').open('a',encoding='utf-8') as f:f.write(line+'\n')
def work_for(path):
    path=Path(path);return ROOT/'work'/ (path.name+'_'+digest(path.read_bytes())[:12])

class TaskLock:
    """OS-level lock released automatically on process exit."""
    def __init__(self, path): self.path=Path(path)
    def __enter__(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.stream=self.path.open('a+b')
        self.stream.seek(0);self.stream.write(b'0');self.stream.flush();self.stream.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.stream.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.stream.close();raise RuntimeError('任务正在由其他进程处理：'+str(self.path)) from None
        return self
    def __exit__(self,*args): self.stream.close()

def warn_override_path(root, relative):
    full=Path(root)/Path(relative)
    if len(str(full))>=180:
        log('Overrides完整路径较长（'+str(len(str(full)))+'字符）；建议使用短根目录。DevTools可能生成longurls映射，请核对实际覆盖路径。')
