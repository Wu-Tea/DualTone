"""Read-only, in-memory digital loopback comparison with matched DSP.

Measures transport lag against a DSP-matched source reference. The known filter
group delay is in the reference; this is not an acoustic measurement. Rejects
discontinuous capture, unreliable timestamps and weak correlation.
"""
import sys,time,json,argparse,threading
from pathlib import Path
ROOT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'lib'))
import numpy as np
import soundcard as sc
from scipy.signal import firwin,lfilter,sosfilt,correlate,correlation_lags
from native_wasapi import NativeRecorder,NativePlayer,mf
from audio_engine import device_format,compile_dsp
from config import TARGET_RATE_HZ,DECIMATOR_TAPS,DECIMATOR_CUTOFF_HZ,PACKET_POLL_SECONDS
from settings import Store,save_json
from resampling import StreamingResampler
from config import AUDIO_TIMESTAMP_MAX_SKEW_SECONDS

MEASUREMENT_SECONDS=4
MAX_RELATIVE_LAG_SECONDS=.2
MIN_CORRELATION=.8
PROBE_PEAK_AMPLITUDE=.008
PROBE_CHUNK_SECONDS=.05
PROBE_SEED=104729
def measure(cfg,probe=False):
    source=sc.get_speaker(cfg['source_id']);target=sc.get_speaker(cfg['target_id'])
    rate=device_format(source)['rate'];target_rate=device_format(target)['rate'];samples={'source':[],'target':[]}
    stop=threading.Event();probe_errors=[]
    def test_signal():
        mf._com.check_error(mf._ole32.CoInitializeEx(mf._ffi.NULL,0))
        try:
            rng=np.random.default_rng(PROBE_SEED)
            with NativePlayer(sc.get_speaker(source.id)._audio_client(),rate,False) as out:
                while not stop.is_set():
                    mono=rng.uniform(-PROBE_PEAK_AMPLITUDE,PROBE_PEAK_AMPLITUDE,(round(rate*PROBE_CHUNK_SECONDS),1))
                    out.play(np.repeat(mono,2,axis=1).astype(np.float32),stop_event=stop)
        except InterruptedError:pass
        except Exception as exc:probe_errors.append(str(exc))
        finally:mf._ole32.CoUninitialize()
    worker=threading.Thread(target=test_signal,daemon=True) if probe else None
    if worker:worker.start()
    try:
        with NativeRecorder(sc.get_microphone(source.id,include_loopback=True)._audio_client(),rate,True) as a, NativeRecorder(sc.get_microphone(target.id,include_loopback=True)._audio_client(),target_rate,True) as b:
            until=time.monotonic()+MEASUREMENT_SECONDS
            while time.monotonic()<until:
                for name,cap in [('source',a),('target',b)]:
                    packet=cap.read_packet()
                    if packet is not None and len(packet):samples[name].append((cap.last_packet_time,packet.copy(),cap.last_packet_flags,cap.last_packet_received))
                time.sleep(PACKET_POLL_SECONDS)
            discontinuities={'source':a.discontinuities,'target':b.discontinuities}
    finally:
        stop.set()
        if worker:worker.join(timeout=2)
    if probe_errors:raise RuntimeError(probe_errors)
    a,b=samples['source'],samples['target']
    if not a or not b:raise ValueError('No audio packets to measure')
    for name,rows in samples.items():
        if any(abs(row[0]-row[3])>AUDIO_TIMESTAMP_MAX_SKEW_SECONDS or row[2]&4 for row in rows):
            raise ValueError(f'{name} 设备时间戳异常；未使用主机接收时间冒充音频时间戳，本次不报告延迟。')
    x=np.concatenate([v[1] for v in a]);y=np.concatenate([v[1] for v in b])
    x=StreamingResampler(rate,TARGET_RATE_HZ).process(x)
    dsp=compile_dsp(cfg)
    from band_filter import BandProcessor
    x=BandProcessor(dsp['band']).process(x)
    if cfg['eq_enabled']:x=sosfilt(dsp['eq']['sos'],x,axis=0)
    from spatial import SpatialProcessor
    x=SpatialProcessor(dsp['settings']).process(x)
    x=StreamingResampler(TARGET_RATE_HZ,target_rate).process(x)
    channel=int(np.argmax(np.sum(y*y,axis=0)));x=x[:,channel];y=y[:,channel]
    if np.max(abs(x))<1e-6 or np.max(abs(y))<1e-6:raise ValueError('Audio too quiet to measure')
    c=correlate(y,x,method='fft');lags=correlation_lags(len(y),len(x));offset=b[0][0]-a[0][0]
    mask=abs(lags/target_rate+offset)<MAX_RELATIVE_LAG_SECONDS
    if not np.any(mask):
        raise ValueError(f'两路设备的 QPC 时间戳无法关联（起点差 {offset:.3f} 秒）；本次不报告延迟。')
    lag=int(lags[mask][np.argmax(abs(c[mask]))])
    if lag>=0:xx=x[:min(len(x),len(y)-lag)];yy=y[lag:lag+len(xx)]
    else:yy=y[:min(len(y),len(x)+lag)];xx=x[-lag:-lag+len(yy)]
    coefficient=float(abs(np.dot(xx,yy))/np.sqrt(np.dot(xx,xx)*np.dot(yy,yy)))
    errors={k:sum(bool(row[2]&4) for row in rows) for k,rows in samples.items()}
    # Detect packet gaps that concatenation must not silently erase.
    gaps={k:max((abs(rows[i+1][0]-rows[i][0]-len(rows[i][1])/(rate if k=='source' else target_rate)) for i in range(len(rows)-1)),default=0)*1000 for k,rows in samples.items()}
    reliable=coefficient>=MIN_CORRELATION and not any(discontinuities.values()) and not any(errors.values()) and max(gaps.values())<2
    return dict(method='WASAPI QPC + matched-DSP correlation',reliable=reliable,transport_lag_ms=round((lag/target_rate+offset)*1000,3),correlation=round(coefficient,4),
                discontinuities=discontinuities,timestamp_errors=errors,max_timestamp_gap_ms=gaps,
                note='Digital transport estimate; excludes matched filter group delay and unmeasured acoustic/device processing.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data-dir',type=Path,default=ROOT/'release'/'DualTone'/'data');p.add_argument('--out',type=Path);p.add_argument('--probe',action='store_true');args=p.parse_args()
    result=measure(Store(args.data_dir).current,args.probe)
    if args.out:save_json(args.out,result)
    print(json.dumps(result,indent=2))
