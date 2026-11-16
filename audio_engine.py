"""Audio worker independent from the GUI; native shared-mode output only."""
import ctypes, threading, time
from collections import deque
import numpy as np
import soundcard as sc
from scipy.signal import sosfilt,sosfreqz
from band_filter import compile_bands,band_signature,band_response,BandProcessor
from equalizer import design_eq
from settings import validate
from native_wasapi import NativePlayer,NativeRecorder,mf
from resampling import StreamingResampler
from audio_scheduling import AudioScheduling
from spatial import SpatialProcessor
from config import (TARGET_RATE_HZ,SUPPORTED_SOURCE_RATES_HZ,CHANNEL_COUNT,SAMPLE_BITS,
    BANDPASS_ORDER,DECIMATOR_TAPS,DECIMATOR_CUTOFF_HZ,PACKET_POLL_SECONDS,
    STOP_TIMEOUT_SECONDS,PEAK_IDLE_SECONDS,AUDIO_MUTEX_NAME,EQ_HEADROOM_DB,SPECTRUM_HISTORY_PACKETS,AUDIO_SCHEDULER_TASK,
    SUPPORTED_DEVICE_RATES_HZ,EQ_SCAN_POINTS,FILTER_BAND_SCAN_POINTS,PLOT_MIN_FREQUENCY_HZ,PLOT_MAX_FREQUENCY_HZ)

def device_format(speaker):
    ptr=speaker._audio_client();fmt=mf._ffi.new('WAVEFORMATEXTENSIBLE**')
    try:
        mf._com.check_error(ptr[0][0].lpVtbl.GetMixFormat(ptr[0],fmt))
        f=fmt[0][0].Format
        sub=fmt[0][0].SubFormat
        return dict(rate=int(f.nSamplesPerSec),channels=int(f.nChannels),
                    float32=f.wBitsPerSample==SAMPLE_BITS and (sub.Data1,sub.Data2,sub.Data3)==(0x100000,0x80,0xaa00))
    finally:
        if fmt[0]!=mf._ffi.NULL:mf._ole32.CoTaskMemFree(fmt[0])
        mf._com.release(ptr)

def compatibility(fmt):
    if not fmt.get('float32'):return '当前混音格式不是 float32'
    if fmt.get('channels')!=CHANNEL_COUNT:return f"当前为 {fmt.get('channels','未知')} 声道，需要立体声"
    if fmt.get('rate') not in SUPPORTED_DEVICE_RATES_HZ:return f"暂不支持 {fmt.get('rate','未知')} Hz"
    return ''

def device_icon(speaker):
    # Windows PKEY_AudioEndpoint_FormFactor, not a role or device-name guess.
    ptr=speaker._device_ptr();store=mf._ffi.new('IPropertyStore**')
    try:
        mf._com.check_error(ptr[0][0].lpVtbl.OpenPropertyStore(ptr[0],0,store))
        key=mf._ffi.new('PROPERTYKEY*',[[0x1da5d803,0xd492,0x4edd,[0x8c,0x23,0xe0,0xc0,0xff,0xee,0x7f,0x0e]],0])
        # PROPVARIANT has an 8-byte header and a two-pointer union on Win64.
        storage=mf._ffi.new('BYTE[]',8+2*mf._ffi.sizeof('void*'))
        value=mf._ffi.cast('PROPVARIANT*',storage)
        try:
            mf._com.check_error(store[0][0].lpVtbl.GetValue(store[0],key,value))
            if value[0].vt!=19:return 'wave'
            form=int(mf._ffi.cast('DWORD*',mf._ffi.addressof(value[0],'data'))[0])
            return {1:'speaker',2:'line',3:'headphones',5:'headphones',7:'digital',8:'digital',9:'monitor'}.get(form,'wave')
        finally:mf._ole32.PropVariantClear(value)
    except (RuntimeError,OSError):return 'wave'
    finally:
        if store[0]!=mf._ffi.NULL:mf._com.release(store)
        mf._com.release(ptr)

def devices():
    result=[]
    for speaker in sc.all_speakers():
        try:
            fmt=device_format(speaker);reason=compatibility(fmt)
            result.append(dict(id=speaker.id,name=speaker.name,icon=device_icon(speaker),supported=not reason,reason=reason,**fmt))
        except (RuntimeError,OSError) as exc:
            result.append(dict(id=speaker.id,name=speaker.name,icon='wave',supported=False,reason='无法读取设备格式：'+str(exc)))
    return result

def compile_dsp(settings):
    cfg=validate(settings)
    eq=design_eq(cfg['gains'])
    band=compile_bands(cfg)
    frequencies=np.unique(np.concatenate([np.geomspace(PLOT_MIN_FREQUENCY_HZ,PLOT_MAX_FREQUENCY_HZ,EQ_SCAN_POINTS)]+[np.linspace(row['low'],row['high'],FILTER_BAND_SCAN_POINTS) for row in cfg['bands'] if cfg['band_enabled'] and row['enabled']]))
    response=band_response(band,frequencies)
    if cfg['eq_enabled']:response*=sosfreqz(eq['sos'],worN=frequencies,fs=TARGET_RATE_HZ)[1]
    peak_db=20*np.log10(max(float(np.max(abs(response))),1e-12))
    return dict(settings=cfg,eq=eq,band=band,preamp_db=-max(0.,peak_db)-EQ_HEADROOM_DB)

class Engine:
    def __init__(self):
        self.thread=None
        self.stop_event=threading.Event()
        self.dsp=None
        self.analysis_enabled=False
        self.analysis_packets=deque(maxlen=SPECTRUM_HISTORY_PACKETS)
        self.status=dict(state='stopped',message='准备就绪',input_peak=0.,output_peak=0.,
                         queue_ms=0.,discontinuities=0,blocks=0,uptime=0.)
    @property
    def active(self):return bool(self.thread and self.thread.is_alive())
    def update(self,compiled):self.dsp=compiled
    def start(self,compiled):
        if self.active:raise ValueError('音频正在运行，请先停止再切换设备。')
        cfg=compiled['settings']
        if not cfg['source_id'] or not cfg['target_id']:raise ValueError('请先选择两个设备。')
        if cfg['source_id']==cfg['target_id']:raise ValueError('主设备和补声设备必须不同，避免音频回路。')
        self.dsp=compiled;self.stop_event.clear()
        self.analysis_packets.clear()
        self.status=dict(state='starting',message='正在连接音频设备…',input_peak=0.,output_peak=0.,queue_ms=0.,discontinuities=0,blocks=0,uptime=0.)
        self.thread=threading.Thread(target=self._run,daemon=True,name='DualTone-Audio')
        self.thread.start()
    def stop(self):
        self.stop_event.set()
        if self.thread:self.thread.join(timeout=STOP_TIMEOUT_SECONDS)
        return not self.active
    def _run(self):
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateMutexW.restype=ctypes.c_void_p
        kernel.CloseHandle.argtypes=[ctypes.c_void_p]
        handle=kernel.CreateMutexW(None,False,AUDIO_MUTEX_NAME)
        if not handle or ctypes.get_last_error()==183:
            if handle:kernel.CloseHandle(handle)
            self.status.update(state='error',message='已有试听工具占用补声。请关闭旧窗口后重试。')
            return
        com_ready=False;scheduling=AudioScheduling()
        try:
            scheduled=scheduling.enter()
            self.status.update(scheduler=AUDIO_SCHEDULER_TASK if scheduled else 'normal',scheduler_error=scheduling.error)
            mf._com.check_error(mf._ole32.CoInitializeEx(mf._ffi.NULL,0));com_ready=True
            cfg=self.dsp['settings']
            source_speaker=sc.get_speaker(cfg['source_id'])
            target=sc.get_speaker(cfg['target_id'])
            sf,tf=device_format(source_speaker),device_format(target)
            if compatibility(sf):raise ValueError('主音频：'+compatibility(sf))
            if compatibility(tf):raise ValueError('副音频：'+compatibility(tf))
            source=sc.get_microphone(cfg['source_id'],include_loopback=True)
            rate=sf['rate']
            output_rate=tf['rate']
            input_resampler=StreamingResampler(rate,TARGET_RATE_HZ)
            output_resampler=StreamingResampler(TARGET_RATE_HZ,output_rate)
            current=None;eqzi=None;band_processor=BandProcessor(None)
            spatial_processor=SpatialProcessor(cfg)
            output=NativePlayer(target._audio_client(),output_rate,False)
            capture=NativeRecorder(source._audio_client(),rate,True,event_driven=True)
            with output,capture:
                started=last_audio=time.monotonic()
                self.status.update(state='running',message='正在补声',source_rate=rate,target_rate=output_rate,processing_rate=TARGET_RATE_HZ,wakeup_mode='WASAPI audio-ready event')
                self.status['buffer_capacity_ms']=output.buffersize/output_rate*1000
                while not self.stop_event.is_set():
                    packet=capture.read_packet()
                    now=time.monotonic();self.status['uptime']=now-started
                    if packet is None or not len(packet):
                        if now-last_audio>PEAK_IDLE_SECONDS:self.status.update(input_peak=0.,output_peak=0.)
                        # Threading.Event.wait(.0005) overslept ~15 ms on this
                        # machine. Wait for WASAPI's packet-ready signal instead.
                        capture.wait_for_packet();continue
                    last_audio=now
                    processing_started=time.perf_counter()
                    input_peak=float(np.max(abs(packet)))
                    packet=input_resampler.process(packet)
                    if not len(packet):continue
                    analysis_input=packet
                    dsp=self.dsp
                    if dsp is not current:
                        # Gain and bypass changes retain filter memory.
                        if current is None or dsp['eq']['gains']!=current['eq']['gains']:
                            eqzi=np.zeros((len(dsp['eq']['sos']),2,2))
                        old_band=None if current is None else band_signature(current['settings'])
                        new_band=band_signature(dsp['settings'])
                        if new_band!=old_band:
                            band_processor=BandProcessor(dsp['band'])
                        spatial_processor.update(dsp['settings'])
                        current=dsp
                    packet=band_processor.process(packet)
                    filtered,eqzi=sosfilt(dsp['eq']['sos'],packet,axis=0,zi=eqzi)
                    if dsp['settings']['eq_enabled']:packet=filtered
                    packet=spatial_processor.process(packet)
                    preamp=dsp['preamp_db']
                    rendered=packet*(dsp['settings']['gain']/100)*10**(preamp/20)
                    output_packet=output_resampler.process(rendered).astype(np.float32)
                    processing_ms=(time.perf_counter()-processing_started)*1000
                    output.play(output_packet,stop_event=self.stop_event)
                    if self.analysis_enabled:self.analysis_packets.append((analysis_input,rendered))
                    self.status.update(input_peak=input_peak,output_peak=float(np.max(abs(rendered))),
                                       queue_ms=output.currentpadding/output_rate*1000,discontinuities=capture.discontinuities,
                                       source_timestamp_valid=capture.last_packet_timestamp_valid,
                                       source_clock_skew_ms=capture.last_packet_clock_skew_ms,
                                       dsp_ms=processing_ms,dsp_max_ms=max(self.status.get('dsp_max_ms',0),processing_ms),
                                       blocks=self.status['blocks']+1)
            self.status.update(state='stopped',message='补声已停止',input_peak=0.,output_peak=0.,queue_ms=0.)
        except InterruptedError:
            self.status.update(state='stopped',message='补声已停止',input_peak=0.,output_peak=0.,queue_ms=0.)
        except Exception as exc:
            self.status.update(state='error',message=f'补声已停止：{exc}',input_peak=0.,output_peak=0.,queue_ms=0.)
        finally:
            scheduling.close()
            if com_ready:mf._ole32.CoUninitialize()
            kernel.CloseHandle(handle)
