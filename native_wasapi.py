"""Native-format WASAPI packets, without auto-converter or synthetic silence.

Uses SoundCard's COM bindings with an explicit native stereo float32 contract.
No system mixer format, audio effects, or source rendering settings are changed.
"""
import time,ctypes,struct
import numpy as np
from soundcard import mediafoundation as mf
from config import PACKET_POLL_SECONDS,CHANNEL_COUNT,SAMPLE_BITS,AUDIO_EVENT_IDLE_TIMEOUT_MS,AUDIO_TIMESTAMP_MAX_SKEW_SECONDS

# Windows AUDCLNT_STREAMFLAGS constants, named as in the Windows SDK.
AUDCLNT_STREAMFLAGS_NOPERSIST=0x00080000
AUDCLNT_STREAMFLAGS_LOOPBACK=0x00020000
AUDCLNT_STREAMFLAGS_EVENTCALLBACK=0x00040000
AUDCLNT_BUFFERFLAGS_DATA_DISCONTINUITY=1
AUDCLNT_BUFFERFLAGS_SILENT=2
AUDCLNT_BUFFERFLAGS_TIMESTAMP_ERROR=4
PACKED_IEEE_FLOAT_SUBTYPE=(0x100000,0x80,0xaa00)

class AudioReadyEvent:
    """Auto-reset Windows event. No timer-resolution changes or busy waiting."""
    WAIT_OBJECT_0=0
    WAIT_TIMEOUT=258
    WAIT_FAILED=0xffffffff
    def __init__(self):
        self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        self.kernel.CreateEventW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_bool,ctypes.c_wchar_p]
        self.kernel.CreateEventW.restype=ctypes.c_void_p
        self.kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint32]
        self.kernel.WaitForSingleObject.restype=ctypes.c_uint32
        self.kernel.SetEvent.argtypes=[ctypes.c_void_p]
        self.kernel.CloseHandle.argtypes=[ctypes.c_void_p]
        self.handle=self.kernel.CreateEventW(None,False,False,None)
        if not self.handle:raise ctypes.WinError(ctypes.get_last_error())
    def wait(self,timeout_ms=AUDIO_EVENT_IDLE_TIMEOUT_MS):
        result=self.kernel.WaitForSingleObject(self.handle,timeout_ms)
        if result==self.WAIT_OBJECT_0:return True
        if result==self.WAIT_TIMEOUT:return False
        raise ctypes.WinError(ctypes.get_last_error())
    def close(self):
        if self.handle:self.kernel.CloseHandle(self.handle);self.handle=None

class NativeClient:
    def __init__(self, ptr, rate, loopback,event_driven=False):
        self._ptr=ptr
        self._ready_event=None
        self.samplerate=rate
        self.channelmap=[0,1]
        fmt=mf._ffi.new('WAVEFORMATEXTENSIBLE**')
        mf._com.check_error(ptr[0][0].lpVtbl.GetMixFormat(ptr[0],fmt))
        try:
            f=fmt[0][0].Format
            if f.nSamplesPerSec!=rate or f.nChannels!=CHANNEL_COUNT or f.wBitsPerSample!=SAMPLE_BITS:
                raise ValueError('Native stereo float32 mix format changed')
            # SoundCard's packed format declaration exposes the IEEE float GUID
            # shifted by two bytes; this is the same subtype check it uses.
            sub=fmt[0][0].SubFormat
            if (sub.Data1,sub.Data2,sub.Data3)!=PACKED_IEEE_FLOAT_SUBTYPE:
                raise ValueError('Mix format is not floating point')
            flags=AUDCLNT_STREAMFLAGS_NOPERSIST | (AUDCLNT_STREAMFLAGS_LOOPBACK if loopback else 0)
            if event_driven:flags|=AUDCLNT_STREAMFLAGS_EVENTCALLBACK
            mf._com.check_error(ptr[0][0].lpVtbl.Initialize(ptr[0],0,flags,0,0,fmt[0],mf._ffi.NULL))
            if event_driven:
                self._ready_event=AudioReadyEvent()
                try:
                    mf._com.check_error(ptr[0][0].lpVtbl.SetEventHandle(ptr[0],mf._ffi.cast('HANDLE',self._ready_event.handle)))
                except Exception:
                    self._ready_event.close();raise
        finally:
            mf._ole32.CoTaskMemFree(fmt[0])

class NativePlayer(NativeClient,mf._Player):
    def play(self,data,stop_event=None):
        # Submit exactly the frames supplied. SoundCard 0.4.6's player releases
        # the entire available buffer even if this packet is shorter, creating
        # an initial queue of unwritten frames. Packet forwarding must not do so.
        data=np.asarray(data,dtype=np.float32,order='C')
        if data.ndim!=2 or data.shape[1]!=2:
            raise ValueError('Expected a stereo audio packet')
        offset=0
        while offset<len(data):
            if stop_event is not None and stop_event.is_set():
                raise InterruptedError('Audio stopped')
            count=min(self._render_available_frames(),len(data)-offset)
            if count==0:
                time.sleep(PACKET_POLL_SECONDS)
                continue
            buffer=self._render_buffer(count)
            raw=data[offset:offset+count].tobytes()
            mf._ffi.memmove(buffer[0],raw,len(raw))
            self._render_release(count)
            offset+=count

class NativeRecorder(NativeClient,mf._Recorder):
    def wait_for_packet(self):
        if self._ready_event is None:raise RuntimeError('Capture stream was not initialized for audio-ready events')
        return self._ready_event.wait()
    def read_packet(self):
        if self._capture_available_frames()==0:
            return None
        data_ptr=mf._ffi.new('BYTE**')
        frame_ptr=mf._ffi.new('UINT32*')
        flag_ptr=mf._ffi.new('DWORD*')
        position=mf._ffi.new('UINT64*')
        timestamp=mf._ffi.new('UINT64*')
        mf._com.check_error(self._ppCaptureClient[0][0].lpVtbl.GetBuffer(
            self._ppCaptureClient[0],data_ptr,frame_ptr,flag_ptr,position,timestamp))
        data,n,flags=data_ptr[0],frame_ptr[0],flag_ptr[0]
        self.last_packet_time=timestamp[0]/10000000
        self.last_packet_received=time.perf_counter()
        self.last_packet_clock_skew_ms=(self.last_packet_time-self.last_packet_received)*1000
        self.last_packet_timestamp_valid=not (flags&AUDCLNT_BUFFERFLAGS_TIMESTAMP_ERROR) and abs(self.last_packet_clock_skew_ms)<=AUDIO_TIMESTAMP_MAX_SKEW_SECONDS*1000
        self.last_packet_position=position[0]
        self.last_packet_flags=flags
        try:
            if flags & AUDCLNT_BUFFERFLAGS_SILENT:
                result=np.zeros((n,2),dtype=np.float32)
            elif data!=mf._ffi.NULL:
                result=np.frombuffer(mf._ffi.buffer(data,n*8),dtype=np.float32).reshape(-1,2).copy()
            else:
                raise RuntimeError('Missing WASAPI packet data')
            if flags & AUDCLNT_BUFFERFLAGS_DATA_DISCONTINUITY and not self._is_first_frame:
                self.discontinuities+=1
            self._is_first_frame=False
            return result
        finally:
            self._capture_release(n)
    def __enter__(self):
        self.discontinuities=0
        try:return super().__enter__()
        except Exception:
            if self._ready_event:self._ready_event.close()
            raise
    def __exit__(self,*args):
        try:return super().__exit__(*args)
        finally:
            if self._ready_event:self._ready_event.close()
