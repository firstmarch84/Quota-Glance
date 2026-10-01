"""Desktop/startup entry point: preserve errors that pythonw otherwise hides."""
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import runpy
import sys


def main():
    root = Path(__file__).resolve().parent
    data = root / '.runtime'
    data.mkdir(exist_ok=True)
    handler = RotatingFileHandler(data / 'startup.log', maxBytes=200000, backupCount=2, encoding='utf-8')
    logging.basicConfig(level=logging.INFO, handlers=[handler], format='%(asctime)s %(levelname)s %(message)s')
    logging.info('Launch pid=%s mode=%s', os.getpid(), 'windows-login' if '--startup' in sys.argv else 'manual')
    os.chdir(root)
    try:
        runpy.run_path(str(root / 'app.py'), run_name='__main__')
    except Exception:
        logging.exception('Quota Glance startup failed')
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, '앱 시작 중 오류가 발생했습니다. .runtime/startup.log를 확인하세요.', 'Quota Glance 시작 오류', 0x10)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
