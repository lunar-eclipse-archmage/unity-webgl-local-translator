import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/"python_libs"))
# 采集服务与翻译模块分开；启动采集器不会调用API。
from collector.service import Handler,PoolServer,ROOT,log
if __name__=='__main__':
    import local
    if len(getattr(local,'LOCAL_SERVICE_TOKEN',''))<32:
        raise SystemExit('请先配置local.py中的LOCAL_SERVICE_TOKEN（至少32字符），并在油猴脚本填写同一值')
    log('采集服务：http://127.0.0.1:8765；3个检查线程；不调用翻译API')
    with PoolServer(('127.0.0.1',8765),Handler) as server:
        try:server.serve_forever()
        except KeyboardInterrupt:pass
