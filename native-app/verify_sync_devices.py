"""Opt-in real-device sync check. Brief low-volume noise; restores all defaults.
Requires the user's saved main/aux outputs and an existing VB-Audio endpoint.
Does not change endpoint format/volume or the user's configuration.
"""
import json,sys,time,threading,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT.parent),str(ROOT.parent/'lib')]
import numpy as np
import soundcard as sc
from scipy.signal import correlate, correlation_lags, butter, sosfilt
from routing import default_output,_set_default
from native_wasapi import NativeRecorder,NativePlayer,mf
from audio_engine import device_format

cli=ROOT/'dist/DualToneCLI.exe'
user=ROOT.parent/'release/DualTone-Native/data/settings.json'
original=user.read_bytes();cfg=json.loads(original)['current']
before=[default_output(i) for i in range(3)]
rows=json.loads(subprocess.check_output([str(cli),'devices']))['result']
virtual=next(r for r in rows if 'VB-Audio Hi-Fi Cable' in r['name'])['id']
assert len({virtual,cfg['source_id'],cfg['target_id']})==3
cfg.update(routing_mode='sync',input_id=virtual,main_delay_ms=0,eq_enabled=False,
           band_enabled=False,spatial_strength=0,effect_mode='space',gain=20)
reports=[]
with tempfile.TemporaryDirectory(dir=ROOT/'qa') as tmp:
    (Path(tmp)/'settings.json').write_text(json.dumps(dict(version=4,current=cfg,presets={})),encoding='utf-8')
    def call(*args,ok=True):
        p=subprocess.run([str(cli),'--data-dir',tmp,*args],capture_output=True,timeout=15)
        r=json.loads(p.stdout);assert r['ok']==ok,r
        return r.get('result',r)
    def running():
        for _ in range(50):
            state=call('status')['audio']
            if state['state']=='running':return state
            if state['state']=='error':raise AssertionError(state)
            time.sleep(.1)
        raise AssertionError('startup timeout')
    def measurement(delay):
        call('set','--json',json.dumps(dict(main_delay_ms=delay)))
        time.sleep(.4)
        recordings={};errors=[];ready=[threading.Event(),threading.Event()]
        def record(index,device):
            mf._com.check_error(mf._ole32.CoInitializeEx(mf._ffi.NULL,0))
            try:
                mic=sc.get_microphone(device,include_loopback=True);rate=device_format(mic)['rate']
                chunks=[];first=None
                with NativeRecorder(mic._audio_client(),rate,True) as recorder:
                    ready[index].set();end=time.monotonic()+3.5
                    while time.monotonic()<end:
                        packet=recorder.read_packet()
                        if packet is None:time.sleep(.001);continue
                        if first is None:first=recorder.last_packet_received-len(packet)/rate
                        chunks.append(packet)
                    recordings[index]=(np.concatenate(chunks)[:,0],rate,first,recorder.discontinuities)
            except Exception as e:errors.append(str(e));ready[index].set()
            finally:mf._ole32.CoUninitialize()
        threads=[threading.Thread(target=record,args=(i,cfg[k])) for i,k in enumerate(('source_id','target_id'))]
        for t in threads:t.start()
        for event in ready:assert event.wait(5)
        time.sleep(.3)
        speaker=sc.get_speaker(virtual);rate=device_format(speaker)['rate']
        noise=np.random.default_rng(831).uniform(-.008,.008,(int(rate*1.8),2))
        noise=sosfilt(butter(3,[500,4000],fs=rate,btype='bandpass',output='sos'),noise,axis=0).astype(np.float32)
        with NativePlayer(speaker._audio_client(),rate,False) as output:output.play(noise)
        for t in threads:t.join(timeout=6);assert not t.is_alive()
        assert not errors,errors
        a,ra,ta,da=recordings[0];b,rb,tb,db=recordings[1]
        assert ra==rb==48000,'This local test expects 48 kHz outputs'
        cc=correlate(a,b,mode='full',method='fft');lags=correlation_lags(len(a),len(b))
        index=np.argmax(cc);offset=lags[index]/ra+(ta-tb)
        coherence=cc[index]/np.sqrt(np.dot(a,a)*np.dot(b,b))
        state=call('status')['audio'];assert state['state']=='running',state
        assert state['main_underruns']==state['auxiliary_underruns']==0,state
        assert coherence>.5,(coherence,state)
        reports.append(dict(delay_ms=delay,observed_main_later_ms=offset*1000,correlation=float(coherence),
                            capture_discontinuities=[da,db],audio={k:state[k] for k in ('main_queue_ms','queue_ms','main_underruns','auxiliary_underruns','discontinuities','dsp_max_ms','capture_packet_ms','synthetic_packets')}))
    try:
        call('start');running()
        assert [default_output(i) for i in range(2)]==[virtual,virtual]
        assert default_output(2)==before[2]
        measurement(0);measurement(80)
        delta=reports[1]['observed_main_later_ms']-reports[0]['observed_main_later_ms']
        assert abs(delta-80)<20,(delta,reports)
        # Pause remains auxiliary-only; mode and delay can change live.
        call('pause','on');assert call('status')['audio']['state']=='running'
        call('pause','off');call('set','--json','{"effect_mode":"reverb"}')
        time.sleep(.3);assert call('status')['audio']['state']=='running'
        call('set','--json','{"routing_mode":"direct"}',ok=False)
        call('stop');assert [default_output(i) for i in range(3)]==before
        # A user changes a default during playback: cleanup must respect it.
        call('start');running();_set_default(cfg['target_id'],0)
        changed=[default_output(i) for i in range(3)]
        call('stop')
        expected=[before[i] if changed[i]==virtual else changed[i] for i in range(3)]
        assert [default_output(i) for i in range(3)]==expected
        for i in range(2):_set_default(before[i],i)
        # Invalid endpoint fails before changing system routing.
        call('set','--json','{"input_id":"nonexistent-endpoint"}')
        call('start');time.sleep(.3);assert call('status')['audio']['state']=='error'
        assert [default_output(i) for i in range(3)]==before
    finally:
        call('shutdown')
        for role in range(3):
            if default_output(role)!=before[role]:_set_default(before[role],role)
assert user.read_bytes()==original
report=dict(runs=reports,delay_delta_ms=delta,defaults_restored=True,user_override_preserved=True,
            startup_failure_restored=True,user_configuration_unchanged=True)
(ROOT/'qa/sync-devices.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
