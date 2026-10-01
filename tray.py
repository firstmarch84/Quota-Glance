"""Small native Windows tray; no shell or background console."""
import ctypes as c
from ctypes import wintypes as w
import threading


class Tray:
    def __init__(self, callback):
        self.callback = callback
        self.hwnd = None
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        u, s, k = c.windll.user32, c.windll.shell32, c.windll.kernel32
        LRESULT = c.c_ssize_t
        WNDPROC = c.WINFUNCTYPE(LRESULT, w.HWND, w.UINT, w.WPARAM, w.LPARAM)
        class WC(c.Structure):
            _fields_ = [('style', w.UINT), ('proc', WNDPROC), ('clsExtra', c.c_int), ('wndExtra', c.c_int),
                        ('instance', w.HINSTANCE), ('icon', w.HICON), ('cursor', w.HANDLE), ('bg', w.HBRUSH),
                        ('menu', w.LPCWSTR), ('name', w.LPCWSTR)]
        class NID(c.Structure):
            _fields_ = [('size', w.DWORD), ('hwnd', w.HWND), ('id', w.UINT), ('flags', w.UINT),
                        ('message', w.UINT), ('icon', w.HICON), ('tip', w.WCHAR*128), ('state', w.DWORD),
                        ('stateMask', w.DWORD), ('info', w.WCHAR*256), ('version', w.UINT),
                        ('title', w.WCHAR*64), ('infoFlags', w.DWORD)]
        u.DefWindowProcW.restype = LRESULT
        u.DefWindowProcW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
        u.CreateWindowExW.restype = w.HWND
        u.CreateWindowExW.argtypes = [w.DWORD,w.LPCWSTR,w.LPCWSTR,w.DWORD,c.c_int,c.c_int,c.c_int,c.c_int,w.HWND,w.HMENU,w.HINSTANCE,c.c_void_p]
        k.GetModuleHandleW.restype = w.HMODULE
        u.LoadIconW.restype = w.HICON
        u.LoadIconW.argtypes = [w.HINSTANCE, c.c_void_p]
        u.CreatePopupMenu.restype = w.HMENU
        u.AppendMenuW.argtypes = [w.HMENU,w.UINT,c.c_size_t,w.LPCWSTR]
        u.TrackPopupMenu.argtypes = [w.HMENU,w.UINT,c.c_int,c.c_int,c.c_int,w.HWND,c.c_void_p]
        u.DestroyMenu.argtypes = [w.HMENU]
        u.SetForegroundWindow.argtypes = [w.HWND]
        u.PostMessageW.argtypes = [w.HWND,w.UINT,w.WPARAM,w.LPARAM]
        u.DestroyWindow.argtypes = [w.HWND]
        s.Shell_NotifyIconW.argtypes = [w.DWORD, c.POINTER(NID)]
        self.nid = None
        def proc(hwnd, msg, wp, lp):
            if msg == 0x8001:
                if lp == 0x202:
                    self.callback('show')
                elif lp == 0x205:
                    menu = u.CreatePopupMenu()
                    for number, text in [(1,'Quota Glance 열기'),(2,'새로고침'),(3,'종료')]:
                        u.AppendMenuW(menu, 0, number, text)
                    point = w.POINT()
                    u.GetCursorPos(c.byref(point))
                    u.SetForegroundWindow(hwnd)
                    cmd = u.TrackPopupMenu(menu, 0x100, point.x, point.y, 0, hwnd, None)
                    u.DestroyMenu(menu)
                    if cmd:
                        self.callback({1:'show',2:'refresh',3:'quit'}[cmd])
            elif msg == 0x0010:
                if self.nid:
                    s.Shell_NotifyIconW(2, c.byref(self.nid))
                u.DestroyWindow(hwnd)
                return 0
            elif msg == 0x0002:
                u.PostQuitMessage(0)
                return 0
            return u.DefWindowProcW(hwnd, msg, wp, lp)
        self.proc = WNDPROC(proc)
        wc = WC(0,self.proc,0,0,k.GetModuleHandleW(None),None,None,None,None,'QuotaGlanceTray')
        u.RegisterClassW(c.byref(wc))
        self.hwnd = u.CreateWindowExW(0,wc.name,'',0,0,0,0,0,None,None,wc.instance,None)
        nid = NID()
        nid.size, nid.hwnd, nid.id, nid.flags = c.sizeof(NID),self.hwnd,1,7
        nid.message, nid.icon, nid.tip = 0x8001,u.LoadIconW(None,32516),'Quota Glance · AI 사용 한도'
        self.nid = nid
        self.ready = bool(s.Shell_NotifyIconW(0,c.byref(nid)))
        msg = w.MSG()
        while u.GetMessageW(c.byref(msg),None,0,0)>0:
            u.TranslateMessage(c.byref(msg))
            u.DispatchMessageW(c.byref(msg))

    def close(self):
        if self.hwnd:
            c.windll.user32.PostMessageW(self.hwnd,0x0010,0,0)
