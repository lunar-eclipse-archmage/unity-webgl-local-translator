import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/"python_libs"))
"""显式重译指定work目录；不打包或部署。"""
import argparse
from pathlib import Path
import local as cfg
from modules.translate import translate

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='按当前模型和提示词重译指定work目录，不部署')
    parser.add_argument('work_dir', type=Path, help='包含extracted.json的任务目录')
    args = parser.parse_args()
    if not (args.work_dir / 'extracted.json').is_file():
        parser.error('目录中没有extracted.json')
    from modules.common import TaskLock
    with TaskLock(args.work_dir/'.task.lock'):
        translate(args.work_dir, cfg)
