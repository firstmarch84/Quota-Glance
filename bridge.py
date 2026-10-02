"""Local, paired extension receiver. No provider cookies or credentials."""
import hmac
import json
import math
import secrets
import threading
import time
import os
import pathlib
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from core import DATA

PORT = 48721
ACCOUNTS = ('claude',)


def validate_credits(credits):
    if not isinstance(credits, list) or len(credits) > 16:
        raise ValueError('invalid credits')
    result = []
    for item in credits:
        if not isinstance(item, dict) or type(item.get('available')) is not bool:
            raise ValueError('invalid credit')
        for field, maximum in [('label',120),('detail',200),('identity',500)]:
            if not isinstance(item.get(field), str) or not 0 < len(item[field]) <= maximum:
                raise ValueError('invalid credit field')
        result.append({key:item[key] for key in ('label','detail','identity','available')})
    return result


def validate_rows(rows):
    if not isinstance(rows, list) or len(rows) > 16:
        raise ValueError('invalid rows')
    result = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('invalid row')
        if row.get('kind') == 'resetCredit':
            label, detail = row.get('label'), row.get('resetText')
            if not isinstance(label, str) or not 0 < len(label) <= 120:
                raise ValueError('invalid label')
            if not isinstance(detail, str) or not 0 < len(detail) <= 200:
                raise ValueError('invalid reset credit')
            result.append({'kind': 'resetCredit', 'label': label, 'resetText': detail})
            continue
        value, label = row.get('remaining'), row.get('label')
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 100:
            raise ValueError('invalid percentage')
        if not isinstance(label, str) or not 0 < len(label) <= 120:
            raise ValueError('invalid label')
        reset = row.get('resetText', '')
        if not isinstance(reset, str) or len(reset) > 200:
            raise ValueError('invalid reset')
        result.append({'label': label, 'remaining': value, 'resetText': reset})
    return result


class ExtensionQuota:
    def __init__(self, port=PORT, auto_open=True):
        token_path = DATA / 'bridge-key.txt'
        if not token_path.exists():
            token_path.write_text(secrets.token_urlsafe(32), encoding='ascii')
        self.token = token_path.read_text(encoding='ascii').strip()
        self.lock = threading.Lock()
        self.rows, self.received, self.error = [], 0, None
        self.channels = {key: {'rows': [], 'received': 0, 'error': None} for key in ACCOUNTS}
        self.server = None
        self.start_error = None
        self.paired_at = 0
        self.extension_version = None
        self.auto_open = auto_open
        self.credits = {}
        self.reset_command = None
        self.reset_result = None
        self.reset_attempts = {}
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def setup(self):
                super().setup()
                self.connection.settimeout(5)

            def reply(self, code, extra=None):
                self.send_response(code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(json.dumps({'ok': code == 200, **(extra or {})}).encode())

            def do_POST(self):
                if self.headers.get('Host') != f'127.0.0.1:{owner.port}':
                    return self.reply(403)
                auth = self.headers.get('Authorization', '')
                if not hmac.compare_digest(auth, 'Bearer ' + owner.token):
                    return self.reply(401)
                if self.path not in ('/pair', '/quota', '/credits', '/reset-result'):
                    return self.reply(404)
                try:
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 < size <= 32768:
                        return self.reply(413)
                    body = json.loads(self.rfile.read(size))
                    if not isinstance(body, dict):
                        raise ValueError()
                    if self.path == '/pair':
                        with owner.lock:
                            owner.paired_at = time.time()
                            version = body.get('version')
                            owner.extension_version = version if isinstance(version, str) and len(version) < 30 else None
                            problems = {
                                'sleeping': 'Chrome이 사용량 탭을 정지했습니다 · 자동 복구 대기 / Chrome 성능 설정 확인',
                                'reader': '확장 읽기 응답 없음 · 확장과 사용량 탭을 한 번 새로고침하세요',
                                'blocked': 'Claude 사람 확인 필요 · 사용량 페이지에서 직접 확인하세요',
                            }
                            if body.get('problem') in problems:
                                owner.error = problems[body['problem']]
                                owner.channels['claude']['error'] = owner.error
                            command = owner.reset_command if body.get('resetPoll') is True else None
                            if command:
                                owner.reset_command = None
                            if command and time.time() - command.pop('created') > 60:
                                command = None
                        return self.reply(200, {'autoOpen': owner.auto_open, 'resetCommand': command})
                    if self.path == '/credits':
                        account = body.get('account')
                        if account not in ('claude','codex'):
                            raise ValueError('invalid account')
                        credits = validate_credits(body.get('credits'))
                        with owner.lock:
                            tab_id = body.get('tabId')
                            if tab_id is not None and (type(tab_id) is not int or tab_id<0):
                                raise ValueError('invalid tab')
                            owner.credits[account] = {'items':credits, 'received':time.time(), 'tabId':tab_id}
                    if self.path == '/reset-result':
                        message = body.get('message')
                        if not isinstance(message,str) or len(message)>200 or type(body.get('ok')) is not bool:
                            raise ValueError('invalid result')
                        with owner.lock:
                            if owner.reset_result and owner.reset_result['id'] == body.get('id'):
                                owner.reset_result.update(done=True,ok=body['ok'],message=message)
                    if self.path == '/quota':
                        account = body.get('account', 'claude')
                        if account not in ACCOUNTS:
                            raise ValueError('invalid account')
                        rows = validate_rows(body.get('rows'))
                        with owner.lock:
                            channel = owner.channels[account]
                            if rows:
                                channel.update(rows=rows, received=time.time(), error=None)
                            else:
                                channel['error'] = '브라우저 사용량 화면 대기 · 로그인/페이지 확인'
                            if account == 'claude':
                                owner.rows, owner.received, owner.error = channel['rows'], channel['received'], channel['error']
                except (ValueError, TypeError):
                    return self.reply(400)
                self.reply(200)

        try:
            self.server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
            self.port = self.server.server_address[1]
            self.server.daemon_threads = True
            threading.Thread(target=self.server.serve_forever, daemon=True).start()
        except OSError:
            self.start_error = '연결 포트를 사용할 수 없습니다 · 다른 앱 인스턴스를 종료하세요'

    def fetch(self, account='claude'):
        with self.lock:
            channel = self.channels[account] if account != 'claude' else {'rows':self.rows, 'received':self.received, 'error':self.error}
            if self.start_error:
                raise RuntimeError(self.start_error)
            if channel['error']:
                raise RuntimeError(channel['error'])
            if not channel['rows']:
                if self.paired_at and not self.extension_version:
                    raise RuntimeError('확장 업데이트 필요 · 연결 설정을 확인하세요')
                if time.time() - self.paired_at < 90:
                    raise RuntimeError('확장 연결됨 · 사용량 준비 중 / 로그인 확인')
                raise RuntimeError('확장 연결 대기 · 연결 설정에서 최초 연결하세요')
            if time.time() - channel['received'] > 150:
                raise RuntimeError('수신 중단 · Chrome 백그라운드 실행 / 연결 설정 확인')
            return [dict(row) for row in channel['rows']]

    def request_refresh(self):
        pass  # The extension owns the one-minute page refresh cadence.

    def credit_snapshot(self, account):
        with self.lock:
            snapshot = self.credits.get(account, {'items':[], 'received':0})
            return {'items':[dict(item) for item in snapshot['items']], 'received':snapshot['received']}

    def reveal_credit(self, account, identity, consume=False):
        with self.lock:
            snapshot = self.credits.get(account)
            if not snapshot or time.time()-snapshot['received'] > 90:
                raise RuntimeError('초기화권 정보가 오래되었습니다. 사용량 화면을 열어 다시 확인하세요.')
            matches = [item for item in snapshot['items'] if item['identity']==identity]
            if len(matches)!=1:
                raise RuntimeError('초기화권 목록이 변경되었습니다. 다시 선택하세요.')
            if consume:
                if not matches[0]['available']:
                    raise RuntimeError('지금 사용할 수 없는 초기화권입니다.')
                if snapshot.get('tabId') is None:
                    raise RuntimeError('확장 1.7.0과 사용량 탭을 새로고침하세요.')
                if time.time()-self.reset_attempts.get((account,identity),0)<120:
                    raise RuntimeError('이미 사용을 요청한 초기화권입니다. 공식 사용량에서 결과를 확인하세요. 재시도는 2분 후 가능합니다.')
            if self.reset_result and not self.reset_result['done'] and time.time()-self.reset_result['created'] < 60:
                raise RuntimeError('이전 선택을 처리 중입니다. 잠시 기다려 주세요.')
            request_id = secrets.token_hex(12)
            self.reset_command = {'id':request_id,'action':'use' if consume else 'reveal','account':account,'identity':identity,'created':time.time(),'tabId':snapshot.get('tabId')}
            if consume:
                self.reset_attempts[(account,identity)] = time.time()
            self.reset_result = {'id':request_id,'done':False,'created':time.time()}
            return request_id

    def credit_result(self, request_id):
        with self.lock:
            if self.reset_result and self.reset_result['id']==request_id:
                return dict(self.reset_result)
            return None

    def connect(self, background=False, account='claude'):
        candidates = [pathlib.Path(os.environ.get(name, default)) / 'Google/Chrome/Application/chrome.exe'
                      for name, default in [('PROGRAMFILES', 'C:/Program Files'), ('LOCALAPPDATA', ''), ('PROGRAMFILES(X86)', 'C:/Program Files (x86)')]]
        chrome = next((path for path in candidates if path.is_file()), None)
        if not chrome:
            raise RuntimeError('Chrome 설치가 필요합니다')
        urls = {'claude':'https://claude.ai/settings/usage','codex':'https://chatgpt.com/settings/usage?tab=overview'}
        args = [str(chrome), '--no-startup-window'] if background else [str(chrome), urls[account]]
        subprocess.Popen(args, creationflags=0x08000000 if os.name == 'nt' else 0)

    def close(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
