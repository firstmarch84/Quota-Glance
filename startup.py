"""Inspect and configure the current user's Windows login shortcut."""
import json
import subprocess
import sys
from core import ROOT


def command(*args):
    result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', str(ROOT / 'shortcut.ps1'), '-Startup', '-PythonPath', sys.executable, *args],
        capture_output=True, creationflags=0x08000000, timeout=15)
    if result.returncode:
        raise RuntimeError('자동 시작 바로가기를 확인하거나 저장하지 못했습니다')
    return result.stdout


def status():
    try:
        return json.loads(command('-Status'))
    except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired):
        return {'enabled': False, 'valid': False, 'disabled': False, 'error': True}


def enable():
    command()
    state = status()
    if state.get('disabled'):
        raise RuntimeError('Windows에서 시작 앱이 꺼져 있습니다. 설정 → 앱 → 시작 프로그램에서 Quota Glance를 켜주세요.')
    if not state.get('enabled'):
        raise RuntimeError('자동 시작 등록을 검증하지 못했습니다')
