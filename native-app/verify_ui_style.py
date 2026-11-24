"""Native UI persistence and redesigned preset lifecycle; no audio routing."""
import json, subprocess, tempfile, unittest, time, ctypes
from ctypes import wintypes
from pathlib import Path
from verify_native import ROOT

class StyleTests(unittest.TestCase):
    def test_preset_update_rename_delete_and_appearance(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'qa') as temp:
            def call(*args,ok=True):
                result=json.loads(subprocess.check_output([str(ROOT/'dist/DualToneCLI.exe'),'--data-dir',temp,*args]) if ok else subprocess.run([str(ROOT/'dist/DualToneCLI.exe'),'--data-dir',temp,*args],capture_output=True).stdout)
                self.assertEqual(result['ok'],ok,result);return result.get('result')
            call('set','--json','{"gain":10}')
            call('preset-add','原方案')
            call('set','--json','{"gain":21.5}')
            call('preset-update','原方案')
            self.assertEqual(call('presets')['原方案']['gain'],21.5)
            call('preset-rename','原方案','新方案')
            self.assertEqual(list(call('presets')),['新方案'])
            call('preset-add','另一个')
            call('preset-rename','新方案','另一个',ok=False)
            self.assertEqual(len(call('presets')),2)
            call('set','--json','{"gain":5}')
            call('preset','新方案');self.assertEqual(call('get')['gain'],21.5)
            call('preset-delete','新方案');self.assertNotIn('新方案',call('presets'))
            self.assertEqual(call('get')['gain'],21.5)
            before=(Path(temp)/'settings.json').read_bytes()
            self.assertEqual(call('appearance')['theme'],'dark')
            for mode in ('light','system','dark'):
                call('appearance',mode);self.assertEqual(call('appearance')['theme'],mode)
            call('appearance','invalid',ok=False)
            self.assertEqual((Path(temp)/'settings.json').read_bytes(),before)

    def test_gui_numeric_and_picker_keyboard(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'qa') as temp:
            def call(*args):
                p=subprocess.run([str(ROOT/'dist/DualToneCLI.exe'),'--data-dir',temp,*args],capture_output=True,timeout=10)
                result=json.loads(p.stdout);self.assertTrue(result['ok'],result);return result['result']
            call('set','--json','{"gain":10}');call('preset-add','A')
            call('set','--json','{"gain":20}');call('preset-add','B');call('preset','A')
            proc=subprocess.Popen([str(ROOT/'dist/DualTone.exe'),'--data-dir',temp,'--quit-after','30'],creationflags=subprocess.CREATE_NO_WINDOW)
            user=ctypes.WinDLL('user32',use_last_error=True)
            cb=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
            user.EnumWindows.argtypes=[cb,wintypes.LPARAM]
            user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
            user.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
            user.PostMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
            handles=[]
            @cb
            def collect(hwnd,_):
                pid=wintypes.DWORD();user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
                title=ctypes.create_unicode_buffer(128);user.GetWindowTextW(hwnd,title,128)
                if pid.value==proc.pid and title.value=='DualTone':handles.append(hwnd)
                return True
            try:
                for _ in range(80):
                    user.EnumWindows(collect,0)
                    if handles and call('status')['running']:break
                    time.sleep(.1)
                self.assertTrue(handles);hwnd=handles[0]
                user.SetForegroundWindow.argtypes=[wintypes.HWND]
                user.GetForegroundWindow.restype=wintypes.HWND
                user.SetForegroundWindow(hwnd);time.sleep(.2)
                self.assertEqual(user.GetForegroundWindow(),hwnd)
                user.keybd_event.argtypes=[wintypes.BYTE,wintypes.BYTE,wintypes.DWORD,ctypes.c_size_t]
                def click(x,y):
                    for msg,key in ((0x200,0),(0x201,1),(0x202,0)):user.PostMessageW(hwnd,msg,key,x|(y<<16))
                    time.sleep(.15)
                def key(code):
                    user.keybd_event(code,0,0,0);user.keybd_event(code,0,2,0);time.sleep(.05)
                # Numeric fields edit the same persisted value as the slider.
                click(340,272);key(0x24)
                for _ in range(8):key(0x2e)
                for code in (0x33,0x35,0xbe,0x35):key(code)
                key(0x0d);time.sleep(.2)
                self.assertEqual(call('get')['gain'],35.5)
                # Popup keyboard: A then Down selects B, Enter commits the preset.
                call('preset','A');time.sleep(.2);click(150,376)
                key(0x28);key(0x0d);time.sleep(.2)
                self.assertEqual(call('get')['gain'],20)
                # Escape must dismiss without changing the persisted value.
                click(150,376);key(0x26);key(0x1b);time.sleep(.2)
                self.assertEqual(call('get')['gain'],20)
            finally:
                if proc.poll() is None:call('shutdown');proc.wait(timeout=10)

if __name__=='__main__':unittest.main(verbosity=2)
