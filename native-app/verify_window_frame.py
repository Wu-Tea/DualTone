"""Native caption contract; isolated GUI with no audio playback."""
import ctypes,json,subprocess,tempfile,time,unittest
from ctypes import wintypes
from pathlib import Path
from verify_native import ROOT

class FrameTests(unittest.TestCase):
    def test_caption_actions_resize_hit_tests_and_close_semantics(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'qa') as folder:
            proc=subprocess.Popen([str(ROOT/'dist/DualTone.exe'),'--data-dir',folder,'--details','--quit-after','40'])
            u=ctypes.WinDLL('user32');cb=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
            u.EnumWindows.argtypes=[cb,wintypes.LPARAM];u.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
            u.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
            u.SendMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM];u.SendMessageW.restype=ctypes.c_ssize_t
            u.PostMessageW.argtypes=u.SendMessageW.argtypes
            for fn in ('IsWindowVisible','IsZoomed','IsIconic'):getattr(u,fn).argtypes=[wintypes.HWND]
            u.GetClientRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
            u.ClientToScreen.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.POINT)]
            u.ShowWindow.argtypes=[wintypes.HWND,ctypes.c_int]
            u.FindWindowExW.argtypes=[wintypes.HWND,wintypes.HWND,wintypes.LPCWSTR,wintypes.LPCWSTR]
            u.FindWindowExW.restype=wintypes.HWND
            def command(*args):
                r=json.loads(subprocess.check_output([str(ROOT/'dist/DualToneCLI.exe'),'--data-dir',folder,*args]))
                self.assertTrue(r['ok'],r);return r['result']
            def tray_handle():
                child=None
                while True:
                    child=u.FindWindowExW(wintypes.HWND(-3),child,'DualToneNativeTray',None)
                    if not child:self.fail('Tray callback window missing')
                    pid=wintypes.DWORD();u.GetWindowThreadProcessId(child,ctypes.byref(pid))
                    if pid.value==proc.pid:return child
            windows={}
            @cb
            def collect(h,_):
                pid=wintypes.DWORD();u.GetWindowThreadProcessId(h,ctypes.byref(pid));title=ctypes.create_unicode_buffer(128);u.GetWindowTextW(h,title,128)
                if pid.value==proc.pid and u.IsWindowVisible(h):windows[title.value]=h
                return True
            def hit(h,x,y):
                point=wintypes.POINT(x,y);u.ClientToScreen(h,ctypes.byref(point))
                return u.SendMessageW(h,0x84,0,(point.x&65535)|((point.y&65535)<<16))
            def click(h,x,y):
                for msg,key in ((0x200,0),(0x201,1),(0x202,0)):u.PostMessageW(h,msg,key,x|(y<<16))
                time.sleep(.2)
            try:
                for _ in range(80):
                    u.EnumWindows(collect,0)
                    if 'DualTone' in windows and 'DualTone · 声音调节' in windows:break
                    time.sleep(.1)
                main=windows['DualTone'];editor=windows['DualTone · 声音调节'];time.sleep(.2)
                rect=wintypes.RECT();u.GetClientRect(main,ctypes.byref(rect))
                self.assertEqual(hit(main,120,18),2) # HTCAPTION
                self.assertEqual(hit(main,1,1),13) # HTTOPLEFT
                self.assertEqual(hit(main,rect.right-69,18),9) # HTMAXBUTTON / snap target
                # Subwindows minimize normally; the main caption must hide to tray.
                er=wintypes.RECT();u.GetClientRect(editor,ctypes.byref(er))
                click(editor,er.right-115,18);self.assertTrue(u.IsIconic(editor));u.ShowWindow(editor,9)
                command('set','--json','{"gain":17.5}')
                before=command('get');state=command('status')
                for _ in range(2):
                    click(main,rect.right-115,18)
                    self.assertFalse(u.IsWindowVisible(main));self.assertFalse(u.IsWindowVisible(editor))
                    self.assertIsNone(proc.poll());self.assertTrue(command('status')['running'])
                    self.assertEqual(command('get'),before)
                    self.assertEqual(command('status')['audio']['state'],state['audio']['state'])
                    # Exercise the same callback emitted by the notification icon.
                    u.PostMessageW(tray_handle(),0x8001,1,0x203);time.sleep(.3)
                    self.assertTrue(u.IsWindowVisible(main));self.assertFalse(u.IsIconic(main))
                click(main,220,527);self.assertTrue(u.IsWindowVisible(editor))
                u.PostMessageW(main,0xa1,9,0);u.PostMessageW(main,0xa2,9,0);time.sleep(.3)
                self.assertTrue(u.IsZoomed(main))
                u.PostMessageW(main,0xa1,9,0);u.PostMessageW(main,0xa2,9,0);time.sleep(.3)
                self.assertFalse(u.IsZoomed(main))
                u.PostMessageW(main,0xa3,2,0);time.sleep(.3);self.assertTrue(u.IsZoomed(main))
                u.ShowWindow(main,9)
                u.GetClientRect(editor,ctypes.byref(rect));click(editor,rect.right-23,18)
                self.assertFalse(u.IsWindowVisible(editor));self.assertIsNone(proc.poll())
                u.GetClientRect(main,ctypes.byref(rect));click(main,rect.right-23,18);proc.wait(timeout=8)
                self.assertEqual(proc.returncode,0)
            finally:
                if proc.poll() is None:
                    subprocess.run([str(ROOT/'dist/DualToneCLI.exe'),'--data-dir',folder,'shutdown'],capture_output=True);proc.wait(timeout=8)
if __name__=='__main__':unittest.main(verbosity=2)
