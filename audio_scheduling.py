"""Thread-scoped Windows multimedia scheduling, without global timer changes."""
import ctypes
from config import AUDIO_SCHEDULER_TASK

AVRT_PRIORITY_HIGH=1

class AudioScheduling:
    def __init__(self):
        self.api=ctypes.WinDLL('avrt',use_last_error=True);self.handle=None;self.error=0
        self.api.AvSetMmThreadCharacteristicsW.argtypes=[ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_uint32)]
        self.api.AvSetMmThreadCharacteristicsW.restype=ctypes.c_void_p
        self.api.AvSetMmThreadPriority.argtypes=[ctypes.c_void_p,ctypes.c_int]
        self.api.AvSetMmThreadPriority.restype=ctypes.c_bool
        self.api.AvRevertMmThreadCharacteristics.argtypes=[ctypes.c_void_p]
        self.api.AvRevertMmThreadCharacteristics.restype=ctypes.c_bool
    def enter(self):
        index=ctypes.c_uint32()
        self.handle=self.api.AvSetMmThreadCharacteristicsW(AUDIO_SCHEDULER_TASK,ctypes.byref(index))
        if not self.handle:self.error=ctypes.get_last_error();return False
        if not self.api.AvSetMmThreadPriority(self.handle,AVRT_PRIORITY_HIGH):
            self.error=ctypes.get_last_error();self.close();return False
        return True
    def close(self):
        if self.handle:self.api.AvRevertMmThreadCharacteristics(self.handle);self.handle=None
