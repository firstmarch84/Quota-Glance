"""Read-only quota adapters. Never send prompts or estimate missing quotas."""
import json
import os
import pathlib
import queue
import subprocess
import threading
import time
import urllib.request
from urllib.parse import urlsplit
import websocket

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / '.runtime'
DATA.mkdir(exist_ok=True)
NO_WINDOW = 0x08000000 if os.name == 'nt' else 0


def is_usage_page(url, provider):
    parsed = urlsplit(url)
    return provider == 'claude' and parsed.hostname == 'claude.ai' and parsed.path.rstrip('/') == '/settings/usage'


def is_challenge_title(title):
    return any(marker in title.lower() for marker in ('just a moment', '잠시만 기다리', 'security verification', '보안 확인', 'verify you are human'))


def normalize_codex(payload):
    buckets = payload.get('rateLimitsByLimitId')
    if not isinstance(buckets, dict) or not buckets:
        one = payload.get('rateLimits')
        buckets = {'codex': one} if isinstance(one, dict) else {}
    rows = []
    for key, bucket in sorted(buckets.items(), key=lambda item: (item[0] != 'codex', item[0])):
        if not isinstance(bucket, dict):
            continue
        for kind in ('primary', 'secondary'):
            window = bucket.get(kind)
            if not isinstance(window, dict):
                continue
            used = window.get('usedPercent')
            if isinstance(used, bool) or not isinstance(used, (int, float)) or not 0 <= used <= 100:
                continue
            mins = window.get('windowDurationMins')
            label = '주간' if mins == 10080 else (f'{mins // 60}시간' if isinstance(mins, int) and mins % 60 == 0 else f'{mins}분' if mins else kind)
            if len(buckets) > 1:
                label = f"{bucket.get('limitName') or key} · {label}"
            rows.append({'label': label, 'remaining': round(100 - used, 1), 'reset': window.get('resetsAt'), 'bucket': key})
    return rows


class Codex:
    def __init__(self):
        self.process = None
        self.seq = 0
        self.responses = queue.Queue()

    def locate(self):
        base = pathlib.Path(os.environ.get('APPDATA', '')) / 'npm/node_modules/@openai/codex'
        matches = list(base.glob('node_modules/@openai/codex-*/vendor/**/codex.exe'))
        if matches:
            return str(matches[0])
        import shutil
        binary = shutil.which('codex.exe')
        if binary:
            return binary
        raise RuntimeError('Codex CLI 설치가 필요합니다')

    def _start(self):
        self.responses = queue.Queue()
        self.process = subprocess.Popen([self.locate(), 'app-server'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, text=True, encoding='utf-8', creationflags=NO_WINDOW)
        process, responses = self.process, self.responses
        def read():
            try:
                for line in process.stdout:
                    try:
                        responses.put(json.loads(line))
                    except ValueError:
                        pass
            finally:
                responses.put({'closed': True})
        threading.Thread(target=read, daemon=True).start()
        self._rpc('initialize', {'clientInfo': {'name': 'quota_glance', 'title': 'Quota Glance', 'version': '1.0.0'}})
        self.process.stdin.write(json.dumps({'method': 'initialized'}) + '\n')
        self.process.stdin.flush()

    def _rpc(self, method, params=None):
        self.seq += 1
        request = {'id': self.seq, 'method': method}
        if params is not None:
            request['params'] = params
        self.process.stdin.write(json.dumps(request) + '\n')
        self.process.stdin.flush()
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            try:
                value = self.responses.get(timeout=max(.1, deadline - time.monotonic()))
            except queue.Empty:
                break
            if value.get('closed'):
                raise RuntimeError('Codex 연결이 종료되었습니다')
            if value.get('id') == self.seq:
                if 'error' in value:
                    raise RuntimeError('Codex 조회 실패 · 로그인/네트워크를 확인하세요')
                return value.get('result', {})
        raise RuntimeError('Codex 응답 시간 초과')

    def fetch(self):
        try:
            if self.process is None or self.process.poll() is not None:
                self._start()
            payload = self._rpc('account/rateLimits/read')
            rows = normalize_codex(payload)
            if not rows:
                raise RuntimeError('구독 한도 없음 · Codex 로그인 확인')
            return rows
        except Exception:
            self.close()
            raise

    def close(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
        self.process = None


# Deliberately conservative: explicit used/remaining percentages in a usage
# section only. A percentage in a chat message must never become a quota.
EXTRACT = r'''(() => {
 const visible = e => !!(e.getClientRects().length) && getComputedStyle(e).visibility !== 'hidden';
 const dialog = [...document.querySelectorAll('[role="dialog"], dialog')].find(e => visible(e) && /usage|사용\s*한도|사용량/i.test(e.innerText));
 const isClaudeUsage = location.hostname === 'claude.ai' && /^\/settings\/usage\/?$/.test(location.pathname);
 let section = location.hostname === 'claude.ai' ? (dialog || (isClaudeUsage ? document.querySelector('main') : null)) : null;
 if (!section) return [];
 const lines = section.innerText.split('\n').map(s => s.trim()).filter(Boolean);
 const rows = [];
 for (let i=0; i<lines.length; i++) {
   const line = lines[i];
   let m = line.match(/^(\d{1,3}(?:\.\d+)?)\s*%\s*(used|remaining|left|사용됨|사용|남음|남았습니다|남은)(?:\s.*)?$/i);
   let reverse = line.match(/^(사용량|사용됨|사용|남은\s*한도|남음|remaining|used)\s*[:：]?\s*(\d{1,3}(?:\.\d+)?)\s*%$/i);
   if (!m && !reverse) continue;
   const n = Number(m ? m[1] : reverse[2]);
   if (n < 0 || n > 100) continue;
   const direction = m ? m[2] : reverse[1];
   const prev = lines.slice(Math.max(0,i-4),i);
   const isLabel = s => /session|week|hour|세션|주간|이번\s*주|시간|all models|모든\s*모델|sonnet|pro|thinking/i.test(s) && !/reset|초기화|재설정|갱신/i.test(s) && s.length<90;
   const label = [...prev].reverse().find(isLabel);
   if (!label) continue;
   const before = prev.slice(prev.lastIndexOf(label)+1);
   const after = [];
   for (const s of lines.slice(i+1,i+4)) { if (isLabel(s) || /%/.test(s)) break; after.push(s); }
   const nearby = [...before,...after].find(s => /reset|초기화|재설정|갱신|첫.*시작/i.test(s) && !/^(제한 초기화|reset limits)$/i.test(s));
   rows.push({label, remaining: /remaining|left|남/i.test(direction) ? n : 100-n, resetText: nearby || ''});
 }
 return rows.slice(0,8);
})()'''


class BrowserQuota:
    def __init__(self, key, provider):
        self.key, self.provider = key, provider
        self.profile = DATA / ('browser-' + key)
        self.process = None
        self.port = None
        self.lock = threading.Lock()
        self.url = 'https://claude.ai/settings/usage' if provider == 'claude' else 'https://gemini.google.com/app'
        self.enabled = self.profile.exists()
        self.last_reload = 0
        self.challenge = False

    def start(self, visible=False):
        if self.port:
            try:
                self.targets()
                return
            except Exception:
                self.port = None
        chrome = pathlib.Path(os.environ.get('PROGRAMFILES', 'C:/Program Files')) / 'Google/Chrome/Application/chrome.exe'
        if not chrome.exists():
            chrome = pathlib.Path(os.environ.get('PROGRAMFILES(X86)', 'C:/Program Files (x86)')) / 'Microsoft/Edge/Application/msedge.exe'
        if not chrome.exists():
            raise RuntimeError('Chrome 또는 Edge가 필요합니다')
        self.profile.mkdir(exist_ok=True)
        active = self.profile / 'DevToolsActivePort'
        if active.exists():
            try:
                self.port = int(active.read_text().splitlines()[0])
                self.targets()
                self.enabled = True
                return
            except Exception:
                self.port = None
                active.unlink(missing_ok=True)
        args = [str(chrome), f'--user-data-dir={self.profile}', '--remote-debugging-port=0',
                '--remote-debugging-address=127.0.0.1', '--no-first-run', '--no-default-browser-check',
                '--disable-background-timer-throttling', '--disable-renderer-backgrounding', self.url]
        si = subprocess.STARTUPINFO()
        si.dwFlags = subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 1 if visible else 6
        self.process = subprocess.Popen(args, startupinfo=si, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            if active.exists():
                try:
                    self.port = int(active.read_text().splitlines()[0])
                    self.targets()
                    self.enabled = True
                    return
                except Exception:
                    pass
            time.sleep(.1)
        raise RuntimeError('사용량 브라우저를 시작하지 못했습니다')

    def targets(self):
        with urllib.request.urlopen(f'http://127.0.0.1:{self.port}/json/list', timeout=3) as response:
            return json.load(response)

    def target(self):
        from urllib.parse import urlsplit
        host = 'claude.ai' if self.provider == 'claude' else 'gemini.google.com'
        pages = [p for p in self.targets() if p.get('type') == 'page' and urlsplit(p.get('url', '')).hostname == host]
        return next((p for p in pages if '/usage' in p['url']), pages[0] if pages else None)

    def call(self, target, method, params=None):
        ws = websocket.create_connection(target['webSocketDebuggerUrl'], timeout=5, suppress_origin=True,
                                         http_no_proxy=['127.0.0.1', 'localhost'])
        try:
            ws.send(json.dumps({'id': 1, 'method': method, 'params': params or {}}))
            deadline = time.monotonic() + 6
            while time.monotonic() < deadline:
                value = json.loads(ws.recv())
                if value.get('id') == 1:
                    if value.get('error'):
                        raise RuntimeError('브라우저 읽기 실패')
                    return value.get('result', {})
            raise RuntimeError('브라우저 응답 시간 초과')
        finally:
            ws.close()

    def connect(self):
        with self.lock:
            self.start(visible=True)
            target = self.target()
            if not target:
                target = next((p for p in self.targets() if p.get('type') == 'page'), None)
            if target:
                self.call(target, 'Page.bringToFront')
                result = self.call(target, 'Browser.getWindowForTarget', {'targetId': target['id']})
                if 'windowId' in result:
                    self.call(target, 'Browser.setWindowBounds', {'windowId': result['windowId'], 'bounds': {'windowState': 'normal'}})

    def fetch(self):
        with self.lock:
            if not self.enabled:
                raise RuntimeError('계정 연결을 눌러 로그인하세요')
            self.start()
            target = self.target()
            if not target:
                raise RuntimeError('브라우저에서 로그인을 완료하세요')
            self.challenge = is_challenge_title(target.get('title', ''))
            if self.challenge:
                raise RuntimeError('사람 확인 대기 · 새로고침 중지 · 연결 도움말 확인')
            # Gemini settings panel is read as displayed; no guessing of internal APIs.
            result = self.call(target, 'Runtime.evaluate', {'expression': EXTRACT, 'returnByValue': True})
            rows = result.get('result', {}).get('value')
            if not isinstance(rows, list) or not rows:
                hint = '설정 → 사용 한도를 열어 두세요' if self.provider == 'gemini' else '로그인 후 설정 → 사용량을 확인하세요'
                raise RuntimeError(hint + ' · 수치 미확인')
            # Refresh only a recognized, authenticated usage screen. Never reload
            # login pages (including returnTo URLs) or unrecognized challenge pages.
            if is_usage_page(target['url'], self.provider):
                now = time.time()
                if self.last_reload and now - self.last_reload > 55:
                    self.call(target, 'Page.reload')
                    self.last_reload = now
                    time.sleep(2)
                    fresh = self.target()
                    self.challenge = bool(fresh and is_challenge_title(fresh.get('title', '')))
                    if self.challenge:
                        raise RuntimeError('사람 확인 대기 · 새로고침 중지 · 연결 도움말 확인')
                    if not fresh or not is_usage_page(fresh['url'], self.provider):
                        raise RuntimeError('로그인이 필요합니다 · 계정 연결을 확인하세요')
                    result = self.call(fresh, 'Runtime.evaluate', {'expression': EXTRACT, 'returnByValue': True})
                    rows = result.get('result', {}).get('value')
                    if not isinstance(rows, list) or not rows:
                        raise RuntimeError('새 사용량 수치 대기 · 다음 확인까지 이전 값 유지')
                elif not self.last_reload:
                    self.last_reload = now
            return rows

    def close(self):
        # Close only this application's dedicated browser profile.
        try:
            target = self.target() if self.port else None
            if target:
                self.call(target, 'Browser.close')
        except Exception:
            pass
