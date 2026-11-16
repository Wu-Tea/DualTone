"""A client scheduled late must still receive the server's buffered response."""
import ctypes,hashlib,json,subprocess,tempfile,time,unittest
from ctypes import wintypes
from pathlib import Path
ROOT=Path(__file__).resolve().parent

class PipeDelivery(unittest.TestCase):
    def test_response_survives_a_delayed_reader(self):
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
        kernel.CreateFileW.restype=wintypes.HANDLE
        kernel.WaitNamedPipeW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD]
        for name in ('ReadFile','WriteFile'):
            getattr(kernel,name).argtypes=[wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD),ctypes.c_void_p]
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        with tempfile.TemporaryDirectory(dir=ROOT/'qa') as tmp:
            pipe='\\\\.\\pipe\\DualTone-'+hashlib.sha256(str(Path(tmp).resolve()).casefold().encode()).hexdigest()[:24]
            proc=subprocess.Popen([str(ROOT/'dist/DualToneCLI.exe'),'--data-dir',tmp,'serve'],creationflags=subprocess.CREATE_NO_WINDOW)
            handle=None
            try:
                for _ in range(100):
                    if kernel.WaitNamedPipeW(pipe,50):break
                    time.sleep(.02)
                for command in ('get','schema','status'):
                    handle=kernel.CreateFileW(pipe,0xC0000000,0,None,3,0,None)
                    self.assertNotEqual(handle,ctypes.c_void_p(-1).value)
                    message=json.dumps(dict(version=1,command=command,arguments={})).encode()+b'\n'
                    written=wintypes.DWORD()
                    self.assertTrue(kernel.WriteFile(handle,message,len(message),ctypes.byref(written),None))
                    time.sleep(.1) # Deterministic regression: let the server finish before reading.
                    result=b''
                    while b'\n' not in result:
                        buffer=ctypes.create_string_buffer(4096);count=wintypes.DWORD()
                        ok=kernel.ReadFile(handle,buffer,4096,ctypes.byref(count),None)
                        self.assertTrue(ok,f'Buffered response lost: WinError {ctypes.get_last_error()}')
                        self.assertGreater(count.value,0)
                        result+=buffer.raw[:count.value]
                    self.assertTrue(json.loads(result)['ok'])
                    kernel.CloseHandle(handle);handle=None
                    self.assertTrue(kernel.WaitNamedPipeW(pipe,5000))
            finally:
                if handle is not None and handle!=ctypes.c_void_p(-1).value:kernel.CloseHandle(handle)
                subprocess.run([str(ROOT/'dist/DualToneCLI.exe'),'--data-dir',tmp,'shutdown'],capture_output=True,timeout=10)
                try:proc.wait(timeout=10)
                except subprocess.TimeoutExpired:proc.terminate();proc.wait(timeout=5)

if __name__=='__main__':unittest.main(verbosity=2)
