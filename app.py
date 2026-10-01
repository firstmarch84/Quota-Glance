import ctypes
import json
import os
import pathlib
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox
from datetime import datetime
from core import Codex, DATA, ROOT
from tray import Tray
from bridge import ExtensionQuota
from providers import create_adapters, selected
import startup

BG = '#10141e'
CARD = '#1a2130'
TEXT = '#f0f3fa'
MUTED = '#98a6bf'
ACCENT = '#91b4ff'
FONT = 'Noto Sans KR'
ACCOUNTS = [('codex','Codex','연결된 로컬 계정','#69dbc0'),
            ('claude','Claude','내 계정','#efb68e')]


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.tk.call('tk','scaling',1.333333)
        self.root.option_add('*Font', (FONT, 10))
        self.root.title('Quota Glance · AI 사용 한도')
        self.root.configure(bg=BG)
        self.root.geometry(f'458x{min(700, self.root.winfo_screenheight()-100)}')
        self.root.minsize(440,560)
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.busy = set()
        self.settings_path = DATA / 'settings.json'
        try:
            self.settings = json.loads(self.settings_path.read_text(encoding='utf-8'))
        except (ValueError,OSError):
            self.settings = {}
        self.top = tk.BooleanVar(value=self.settings.get('topmost',False))
        self.auto = tk.BooleanVar(value=startup.status()['enabled'])
        self.root.attributes('-topmost',self.top.get())
        self.accounts = [account for account in ACCOUNTS if account[0] in selected(self.settings)]
        self.adapters = create_adapters(self.settings)
        self.states = {key:{'rows':[],'updated':None,'error':'첫 사용량을 확인하고 있습니다'} for key,_,_,_ in self.accounts}
        self.widgets = {}
        self.build()
        self.tray = Tray(lambda action:self.events.put(('action',action)))
        self.root.protocol('WM_DELETE_WINDOW',self.hide)
        self.root.after(100,self.drain)
        self.root.after(300,self.refresh)
        self.root.after(60000,self.periodic)
        self.root.after(1000,self.tick)
        if 'claude' in self.adapters:
            self.root.after(5000,self.poll_extension)
        if 'claude' in self.adapters and '--smoke' not in __import__('sys').argv:
            self.root.after(2000,self.wake_chrome)
        self.root.bind('<Control-r>',lambda e:self.refresh())
        if '--startup' in __import__('sys').argv:
            import logging
            logging.info('App ready: window visible, tray=%s', getattr(self.tray,'ready',False))
        if '--hidden' in __import__('sys').argv:
            self.root.after(1500,self.hide)
        if '--smoke' in __import__('sys').argv:
            self.root.after(12000,self.smoke)
        if 'claude' in self.adapters and '--connect-claude' in __import__('sys').argv:
            self.root.after(1000,self.connection_help)

    def label(self,parent,text,size=10,color=TEXT,**kw):
        return tk.Label(parent,text=text,font=(FONT,size),fg=color,bg=parent.cget('bg'),**kw)

    def button(self,parent,text,command,primary=False):
        return tk.Button(parent,text=text,command=command,font=(FONT,9),bg='#2a3954' if primary else '#263044',
                         fg=TEXT,activebackground='#364967',activeforeground=TEXT,relief='flat',bd=0,padx=10,pady=7,cursor='hand2',takefocus=True)

    def build(self):
        head = tk.Frame(self.root,bg=BG)
        head.pack(fill='x',padx=22,pady=(20,4))
        self.label(head,'QUOTA GLANCE',9,ACCENT).pack(anchor='w')
        line = tk.Frame(head,bg=BG)
        line.pack(fill='x',pady=(5,0))
        self.label(line,'AI 사용 한도',22).pack(side='left')
        self.button(line,'↻ 갱신',self.refresh).pack(side='right')
        self.summary = self.label(head,' · '.join(a[1] for a in self.accounts)+' 잔여 한도',10,MUTED)
        self.summary.pack(anchor='w',pady=(6,10))
        toolbar = tk.Frame(self.root,bg=BG)
        toolbar.pack(fill='x',padx=18,pady=(0,10))
        for label,var,cmd in [('항상 위에',self.top,self.toggle_top),('윈도우 시작 시 실행',self.auto,self.toggle_auto)]:
            tk.Checkbutton(toolbar,text=label,variable=var,command=cmd,bg=BG,fg=MUTED,selectcolor=CARD,
                           activebackground=BG,activeforeground=TEXT,font=(FONT,9),bd=0).pack(side='left',padx=(0,12))
        viewport = tk.Frame(self.root,bg=BG)
        viewport.pack(fill='both',expand=True)
        self.canvas = tk.Canvas(viewport,bg=BG,highlightthickness=0)
        scroll = tk.Scrollbar(viewport,command=self.canvas.yview,width=10)
        scroll.pack(side='right',fill='y')
        self.canvas.pack(side='left',fill='both',expand=True)
        self.canvas.configure(yscrollcommand=scroll.set)
        content = tk.Frame(self.canvas,bg=BG)
        win = self.canvas.create_window((0,0),window=content,anchor='nw')
        content.bind('<Configure>',lambda e:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>',lambda e:self.canvas.itemconfigure(win,width=e.width))
        self.root.bind_all('<MouseWheel>',lambda e:self.canvas.yview_scroll(int(-e.delta/120),'units'))
        for key,name,sub,color in self.accounts:
            card = tk.Frame(content,bg=CARD,padx=15,pady=12,highlightbackground='#2a3448',highlightthickness=1)
            card.pack(fill='x',padx=(20,10),pady=(0,10))
            header = tk.Frame(card,bg=CARD)
            header.pack(fill='x')
            self.label(header,'●',12,color).pack(side='left',padx=(0,8))
            self.label(header,name,12).pack(side='left')
            self.label(header,sub,9,MUTED).pack(side='left',padx=8)
            self.button(header,'연결 확인' if key=='codex' else '연결 설정',lambda k=key:self.connect(k)).pack(side='right')
            body = tk.Frame(card,bg=CARD)
            body.pack(fill='x',pady=(10,0))
            status = self.label(card,'대기 중',9,MUTED,anchor='w',justify='left',wraplength=340)
            status.pack(fill='x',pady=(6,0))
            self.widgets[key] = {'body':body,'status':status,'color':color}
            self.render(key)
        footer = tk.Frame(self.root,bg=BG)
        footer.pack(fill='x',padx=22,pady=(6,16))
        self.label(footer,'약 1분마다 갱신 · 닫아도 트레이 유지',9,MUTED).pack(anchor='w')
        bottom = tk.Frame(footer,bg=BG)
        bottom.pack(fill='x',pady=(9,0))
        self.button(bottom,'사용 안내',self.help).pack(side='left')
        self.button(bottom,'트레이로 접기',self.hide).pack(side='right')

    @staticmethod
    def set_text(widget, text):
        if widget.cget('text') != text:
            widget.configure(text=text)

    def render(self,key):
        w = self.widgets[key]
        state = self.states[key]
        rows = state['rows']
        if key=='codex':
            rows = [row for row in rows if row.get('bucket')=='codex'] or rows
        # Keep existing widgets. Rebuild only when the number of windows changes.
        if w.get('row_count') != len(rows):
            for child in w['body'].winfo_children():
                child.destroy()
            w['row_count'] = len(rows)
            w['row_widgets'] = []
            if not rows:
                self.label(w['body'],'—  연결 후 잔여 한도를 표시합니다',10,MUTED).pack(anchor='w',pady=3)
            for row in rows:
                line = tk.Frame(w['body'],bg=CARD)
                line.pack(fill='x',pady=(0,3))
                label = self.label(line,'',9,MUTED,wraplength=230,justify='left')
                label.pack(side='left')
                amount = self.label(line,'',12,w['color'])
                amount.pack(side='right')
                bar = tk.Canvas(w['body'],height=5,bg='#30394a',highlightthickness=0)
                bar.pack(fill='x',pady=(0,6))
                rect = bar.create_rectangle(0,0,0,5,fill=w['color'],outline='')
                reset = self.label(w['body'],'',8,MUTED,wraplength=330,justify='left')
                reset.pack(anchor='w',pady=(0,4))
                item = {'label':label,'amount':amount,'bar':bar,'rect':rect,'reset':reset,'remaining':0}
                bar.bind('<Configure>',lambda e,item=item:item['bar'].coords(item['rect'],0,0,e.width*item['remaining']/100,5))
                w['row_widgets'].append(item)
        for row,item in zip(rows,w['row_widgets']):
            remaining = row['remaining']
            color = '#ff998c' if remaining<=10 else '#ebcc86' if remaining<=25 else w['color']
            if state['error']:
                color = MUTED
            self.set_text(item['label'],row['label'])
            self.set_text(item['amount'],f'{remaining:g}% 남음')
            if item['amount'].cget('fg') != color:
                item['amount'].configure(fg=color)
                item['bar'].itemconfigure(item['rect'],fill=color)
            if item['remaining'] != remaining:
                item['remaining'] = remaining
                item['bar'].coords(item['rect'],0,0,item['bar'].winfo_width()*remaining/100,5)
            reset = row.get('reset')
            if isinstance(reset,(int,float)):
                try:
                    text = datetime.fromtimestamp(reset).strftime('%m/%d %H:%M 초기화')
                except (ValueError,OSError,OverflowError):
                    text = ''
            else:
                text = row.get('resetText','')
            self.set_text(item['reset'],text)
        self.status(key)

    def status(self,key):
        state = self.states[key]
        age = time.time()-state['updated'] if state['updated'] else None
        if state['error']:
            text = state['error']
            if state['rows']:
                text = '이전 수치 · ' + text
        else:
            source = '공식 한도' if key=='codex' else 'Chrome 확장 · 자동 확인'
            text = f"{source} · {datetime.fromtimestamp(state['updated']).strftime('%H:%M')} 확인"
            if age and age>150:
                text = '업데이트 지연 · ' + text
        self.set_text(self.widgets[key]['status'],text)

    def refresh(self):
        if 'claude' in self.adapters:
            self.adapters['claude'].request_refresh()
        for key in self.adapters:
            self.refresh_one(key)

    def refresh_one(self,key):
        if key in self.busy or self.stop.is_set():
            return
        self.busy.add(key)
        def work():
            try:
                result = self.adapters[key].fetch()
                self.events.put(('result',key,result,None))
            except Exception as e:
                message = str(e) if isinstance(e,RuntimeError) else '연결 실패 · 네트워크와 로그인 상태를 확인하세요'
                self.events.put(('result',key,None,message))
        threading.Thread(target=work,daemon=True).start()

    def connect(self,key):
        if key == 'claude':
            self.connection_help()
            return
        if key=='codex':
            self.refresh_one(key)
            details = '\n'.join(f"{r['label']}: {r['remaining']:g}% 남음" for r in self.states[key]['rows'])
            messagebox.showinfo('Codex 연결','이 PC의 Codex CLI 로그인 계정에서 공식 사용 한도를 조회합니다.\n\n'+details+'\n\n로그인되지 않았다면 터미널에서 codex login을 실행한 뒤 갱신하세요.',parent=self.root)
            return
    def drain(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event[0]=='result':
                    _,key,rows,error = event
                    self.busy.discard(key)
                    self.states[key]['error'] = error
                    if rows is not None:
                        observed = self.adapters[key].received if key!='codex' else time.time()
                        self.states[key].update(rows=rows,updated=observed)
                    self.render(key)
                elif event[0]=='connected':
                    key = event[1]
                    self.refresh_one(key)
                elif event[0]=='action':
                    {'show':self.show,'refresh':self.refresh,'quit':self.quit}[event[1]]()
                    if self.stop.is_set():
                        return
        except queue.Empty:
            pass
        self.root.after(150,self.drain)

    def periodic(self):
        self.refresh()
        self.root.after(60000,self.periodic)

    def poll_extension(self):
        self.refresh_one('claude')
        self.root.after(5000,self.poll_extension)

    def tick(self):
        count = sum(bool(s['rows']) and not s['error'] and time.time()-(s['updated'] or 0)<150 for s in self.states.values())
        self.set_text(self.summary,f'{count} / {len(self.accounts)} 계정 수치 확인 · 사용 한도 기준')
        for key in self.states:
            if key not in self.busy:
                self.status(key)
        self.root.after(1000,self.tick)

    def toggle_top(self):
        self.root.attributes('-topmost',self.top.get())
        self.settings['topmost'] = self.top.get()
        self.settings_path.write_text(json.dumps(self.settings),encoding='utf-8')

    def startup_path(self):
        return pathlib.Path(os.environ['APPDATA'])/'Microsoft/Windows/Start Menu/Programs/Startup/Quota Glance.lnk'

    def toggle_auto(self):
        try:
            if self.auto.get():
                startup.enable()
            else:
                self.startup_path().unlink(missing_ok=True)
            self.auto.set(startup.status()['enabled'])
        except Exception as error:
            self.auto.set(startup.status()['enabled'])
            messagebox.showerror('설정 실패',str(error) if isinstance(error,RuntimeError) else '자동 시작 바로가지를 저장할 수 없습니다.',parent=self.root)

    def hide(self):
        if getattr(self.tray,'ready',False):
            self.root.withdraw()
        else:
            self.root.iconify()

    def show(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def help(self):
        if 'claude' not in self.adapters:
            messagebox.showinfo('사용 안내',
                'Codex 전용 모드입니다. 앱만 실행하면 로그인된 Codex CLI로 조회합니다.\n'
                'Chrome과 Claude 확장은 필요하지 않습니다.\n\n'
                '다른 서비스를 추가하려면 앱을 종료하고 설치 스크립트를\n'
                '-Providers both로 다시 실행하세요.\n'
                '트레이 우클릭 → 종료로 완전히 종료합니다.',parent=self.root)
            return
        messagebox.showinfo('사용 안내',
            '1. Quota Glance 앱을 켭니다.\n'
            '2. Claude 연결 설정에서 확장을 최초 한 번 연결하세요.\n'
            '3. 작업은 평소처럼 Codex·Claude 데스크톱에서 하세요.\n\n'
            '확장 1.4.0이 사용량 탭을 자동으로 준비합니다.\n'
            'Chrome 백그라운드 실행을 허용하면 앱 실행 시 연결합니다.\n'
            '로그인이 만료되면 연결 설정 → 사용량 열기를 누르세요.\n\n'
            '로그인 만료·사용량 미인식·수신 중단 시 상태를 표시합니다.\n'
            '오래된 수치는 회색으로 표시합니다.\n'
            '닫으면 트레이 유지, 트레이 우클릭 → 종료로 끝냅니다.',parent=self.root)

    def connection_help(self):
        popup = tk.Toplevel(self.root)
        popup.title('Claude · 자동 연결 설정')
        popup.configure(bg=CARD)
        popup.geometry('570x400')
        self.label(popup,'일반 Chrome에서 한 번 연결',15).pack(anchor='w',padx=20,pady=18)
        self.label(popup,
            '1. chrome://extensions에서 Quota Glance 확장을 새로고침하세요.\n'
            '   버전 1.4.0과 확장 사용 상태를 확인하세요.\n'
            '2. 확장이 없다면 개발자 모드 → 압축해제된 확장 로드에서\n'
            '   아래 확장 폴더를 선택하세요.\n'
            '3. 최초 연결 시 확장에 연결 코드를 붙여넣고 앱 연결을 누르세요.\n\n'
            '이후 앱 실행 시 사용량 창을 자동으로 최소화해 준비합니다.\n'
            'Chrome 백그라운드 앱 실행이 허용되어 있어야 합니다.\n'
            '로그인/사람 확인이 필요할 때만 아래 사용량 열기를 누르세요.',
            10,MUTED,justify='left').pack(anchor='w',padx=20)
        actions = tk.Frame(popup,bg=CARD)
        actions.pack(fill='x',padx=20,pady=15)
        def copy(value):
            self.root.clipboard_clear()
            self.root.clipboard_append(value)
        self.button(actions,'확장 폴더 복사',lambda:copy(str(ROOT/'extension'))).pack(side='left')
        self.button(actions,'연결 코드 복사',lambda:copy(self.adapters['claude'].token)).pack(side='left',padx=8)
        self.button(actions,'사용량 열기',lambda:self.wake_chrome(False)).pack(side='left')

    def wake_chrome(self, background=True):
        def work():
            try:
                self.adapters['claude'].connect(background=background)
            except Exception as error:
                self.events.put(('result','claude',None,str(error) if isinstance(error,RuntimeError) else 'Chrome 시작 실패 · 연결 설정 확인'))
        threading.Thread(target=work,daemon=True).start()

    def smoke(self):
        from tkinter import font as tkfont
        report = {'font':tkfont.Font(family=FONT,size=10).actual('family'),'tray_ready':getattr(self.tray,'ready',False),'accounts':self.states,'window':self.root.winfo_geometry()}
        (ROOT/'output').mkdir(exist_ok=True)
        (ROOT/'output/smoke.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        try:
            from capture import capture_window
            capture_window(self.root,ROOT/'output/preview.png')
        except Exception:
            pass
        self.quit()

    def quit(self):
        if self.stop.is_set():
            return
        self.stop.set()
        self.tray.close()
        def cleanup():
            for adapter in self.adapters.values():
                if '--smoke' not in __import__('sys').argv or isinstance(adapter,Codex):
                    adapter.close()
        threading.Thread(target=cleanup,daemon=False).start()
        self.root.destroy()


if __name__=='__main__':
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
    # Lock is owned by the OS and released after crashes as well as normal exits.
    kernel = ctypes.windll.kernel32
    kernel.CreateMutexW.restype = ctypes.c_void_p
    mutex = kernel.CreateMutexW(None,False,'Local\\QuotaGlanceApp')
    if kernel.GetLastError()==183:
        # A second shortcut click restores the running window, including hidden Tk windows.
        user = ctypes.windll.user32
        user.FindWindowW.restype = ctypes.c_void_p
        user.FindWindowW.argtypes = [ctypes.c_wchar_p,ctypes.c_wchar_p]
        user.ShowWindow.argtypes = [ctypes.c_void_p,ctypes.c_int]
        user.SetForegroundWindow.argtypes = [ctypes.c_void_p]
        hwnd = user.FindWindowW(None,'Quota Glance · AI 사용 한도')
        if hwnd:
            user.ShowWindow(hwnd,9)
            user.SetForegroundWindow(hwnd)
    else:
        App().root.mainloop()
