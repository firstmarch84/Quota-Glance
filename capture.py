"""Capture only our own window for development verification."""
import ctypes as c
from ctypes import wintypes as w
from PIL import Image

def capture_window(root,path):
    u,g = c.windll.user32,c.windll.gdi32
    u.GetParent.restype = w.HWND
    u.GetParent.argtypes = [w.HWND]
    hwnd = u.GetParent(root.winfo_id())
    u.GetWindowDC.restype = w.HDC
    u.GetWindowDC.argtypes = [w.HWND]
    g.CreateCompatibleDC.restype = w.HDC
    g.CreateCompatibleDC.argtypes = [w.HDC]
    g.CreateCompatibleBitmap.restype = w.HBITMAP
    g.CreateCompatibleBitmap.argtypes = [w.HDC,c.c_int,c.c_int]
    g.SelectObject.restype = w.HANDLE
    g.SelectObject.argtypes = [w.HDC,w.HANDLE]
    g.DeleteObject.argtypes = [w.HANDLE]
    g.DeleteDC.argtypes = [w.HDC]
    u.ReleaseDC.argtypes = [w.HWND,w.HDC]
    u.PrintWindow.argtypes = [w.HWND,w.HDC,w.UINT]
    rect = w.RECT()
    u.GetWindowRect.argtypes = [w.HWND,c.POINTER(w.RECT)]
    u.GetWindowRect(hwnd,c.byref(rect))
    width,height = rect.right-rect.left,rect.bottom-rect.top
    dc = u.GetWindowDC(hwnd)
    mem = g.CreateCompatibleDC(dc)
    bmp = g.CreateCompatibleBitmap(dc,width,height)
    old = g.SelectObject(mem,bmp)
    class BI(c.Structure):
        _fields_ = [('size',w.DWORD),('width',w.LONG),('height',w.LONG),('planes',w.WORD),('bits',w.WORD),('compression',w.DWORD),('sizeImage',w.DWORD),('x',w.LONG),('y',w.LONG),('used',w.DWORD),('important',w.DWORD)]
    try:
        if not u.PrintWindow(hwnd,mem,2):
            raise RuntimeError('PrintWindow failed')
        g.SelectObject(mem,old)
        info = BI(c.sizeof(BI),width,-height,1,32,0,0,0,0,0,0)
        buf = c.create_string_buffer(width*height*4)
        g.GetDIBits.argtypes = [w.HDC,w.HBITMAP,w.UINT,w.UINT,c.c_void_p,c.c_void_p,w.UINT]
        g.GetDIBits(mem,bmp,0,height,buf,c.byref(info),0)
        Image.frombuffer('RGB',(width,height),buf,'raw','BGRX',0,1).save(path)
    finally:
        g.SelectObject(mem,old)
        g.DeleteObject(bmp)
        g.DeleteDC(mem)
        u.ReleaseDC(hwnd,dc)
