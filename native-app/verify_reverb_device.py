"""Low-level real-route reverb check; never delays or reroutes the main stream."""
import sys,json,time,subprocess,tempfile,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT.parent),str(ROOT.parent/'lib')]
import numpy as np,soundcard as sc
from routing import default_output
from native_wasapi import NativePlayer,mf
from audio_engine import device_format

before=[default_output(i) for i in range(3)]
user=ROOT.parent/'release/DualTone-Native/data/settings.json'
original=user.read_bytes();cfg=json.loads(original)['current']
assert before[:2]==[cfg['source_id']]*2,'Main output must already match the saved source.'
cfg.update(effect_mode='reverb',reverb_size=40,reverb_decay=1.2,reverb_brightness=40,
           band_enabled=False,eq_enabled=False,gain=8)
cli=ROOT/'dist/DualToneCLI.exe'
with tempfile.TemporaryDirectory(dir=ROOT/'qa') as tmp:
    directory=Path(tmp);(directory/'settings.json').write_text(json.dumps(dict(version=3,current=cfg,presets={})),encoding='utf-8')
    def call(*args):
        p=subprocess.run([str(cli),'--data-dir',tmp,*args],capture_output=True,timeout=15)
        r=json.loads(p.stdout)
        if not r['ok']:raise RuntimeError(r)
        return r['result']
    reports=[];errors=[]
    def burst():
        mf._com.check_error(mf._ole32.CoInitializeEx(mf._ffi.NULL,0))
        try:
            source=sc.get_speaker(cfg['source_id']);rate=device_format(source)['rate']
            data=np.random.default_rng(74).uniform(-.005,.005,(int(rate*.6),2)).astype(np.float32)
            with NativePlayer(source._audio_client(),rate,False) as output:output.play(data)
        except Exception as e:errors.append(str(e))
        finally:mf._ole32.CoUninitialize()
    try:
        call('start');time.sleep(.5)
        assert call('status')['audio']['state']=='running'
        thread=threading.Thread(target=burst);thread.start();thread.join(timeout=4)
        assert not thread.is_alive() and not errors,errors
        for _ in range(18):
            reports.append(call('status')['audio']);time.sleep(.1)
        assert all(r['state']=='running' for r in reports)
        assert any(r['output_peak']>1e-8 for r in reports),'No wet output after the burst'
        idle=[r for r in reports if r['input_peak']<1e-10]
        tail_verified=any(r['output_peak']>1e-8 for r in idle)
        # Live mode switching stays on the same endpoints.
        call('set','--json','{"effect_mode":"space"}')
        time.sleep(.1);assert call('status')['audio']['state']=='running'
        call('set','--json','{"effect_mode":"reverb"}')
        rejected=subprocess.run([str(cli),'--data-dir',tmp,'latency'],capture_output=True,timeout=10)
        assert not json.loads(rejected.stdout)['ok'],'Reverb must not be reported as transport delay'
        report=dict(tail_with_idle_source_verified=tail_verified,synthetic_tail_packets_seen=any(r.get('reverb_tail') for r in reports),
                    source_rate=reports[0]['source_rate'],target_rate=reports[0]['target_rate'],
                    discontinuities=reports[-1]['discontinuities'],dsp_max_ms=reports[-1]['dsp_max_ms'],
                    samples=[{k:r.get(k) for k in ('input_peak','output_peak','reverb_tail','queue_ms')} for r in reports])
    finally:call('shutdown')
assert [default_output(i) for i in range(3)]==before
assert user.read_bytes()==original
report.update(default_outputs_unchanged=True,user_config_unchanged=True)
(ROOT/'qa/reverb-device.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
