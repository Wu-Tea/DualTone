"""Silent real-device validation; keeps Windows defaults and user data unchanged."""
import json,sys,subprocess,time,tempfile,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT.parent),str(ROOT.parent/'lib')]
from routing import default_output
from native_wasapi import NativePlayer,mf
from audio_engine import device_format
import soundcard as sc
import numpy as np
before=[default_output(i) for i in range(3)]
if before[0]!=before[1]:raise SystemExit('Playback defaults differ; skip test to avoid changing them.')
cli=ROOT/'dist/DualToneCLI.exe'
def run(directory,*args,ok=True):
    p=subprocess.run([str(cli),'--data-dir',str(directory),*args],capture_output=True,timeout=15)
    doc=json.loads(p.stdout)
    assert doc['ok']==ok,doc
    return doc
ROOT.joinpath('qa').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(dir=ROOT/'qa') as directory:
    ds=run(directory,'devices')['result']
    target=next(d for d in ds if 'Odyssey G65B' in d['name'] and d['id']!=before[0] and d['supported'])
    other=next((d for d in ds if 'Realtek' in d['name'] and d['id']!=before[0] and d['supported']),None)
    run(directory,'set','--json',json.dumps(dict(source_id=before[0],target_id=target['id'],gain=0)))
    reports=[]
    stop=threading.Event()
    def silence_clock():
        mf._com.check_error(mf._ole32.CoInitializeEx(mf._ffi.NULL,0))
        try:
            speaker=sc.get_speaker(before[0]);rate=device_format(speaker)['rate']
            with NativePlayer(speaker._audio_client(),rate,False) as output:
                while not stop.is_set():output.play(np.zeros((rate//100,2),np.float32),stop_event=stop)
        except InterruptedError:pass
        finally:mf._ole32.CoUninitialize()
    clock=threading.Thread(target=silence_clock);clock.start()
    try:
        run(directory,'start');time.sleep(3)
        state=run(directory,'status')['result'];assert state['audio']['state']=='running',state
        assert state['audio']['output_peak']==0,state
        reports.append(state)
        run(directory,'set','--json','{"target_id":"disconnected-test-device"}',ok=False)
        assert run(directory,'status')['result']['audio']['state']=='running'
        if other:
            run(directory,'set','--json',json.dumps(dict(target_id=other['id'])))
            time.sleep(3);state=run(directory,'status')['result'];assert state['audio']['state']=='running',state
            assert state['audio']['output_peak']==0,state
            reports.append(state)
    finally:
        run(directory,'shutdown');stop.set();clock.join(timeout=5)
    assert all(r['audio']['blocks']>0 for r in reports),'No real packets processed'
    assert [default_output(i) for i in range(3)]==before,'Windows defaults changed'
    (ROOT/'qa/native-device-validation.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps([dict(state=r['audio']['state'],source_rate=r['audio']['source_rate'],target_rate=r['audio']['target_rate'],blocks=r['audio']['blocks'],dsp_ms=r['audio'].get('dsp_ms'),queue_ms=r['audio']['queue_ms'],discontinuities=r['audio']['discontinuities']) for r in reports],indent=2))
    print('Muted routing, hot switching, missing-device rejection and unchanged Windows defaults verified.')
