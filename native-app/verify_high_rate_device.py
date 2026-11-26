"""Silent real-device run at existing formats; never changes formats/defaults."""
import sys,json,time,subprocess,tempfile,threading,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT.parent),str(ROOT.parent/'lib')]
import numpy as np,soundcard as sc
from native_wasapi import NativePlayer,mf
from routing import default_output
from audio_engine import device_format
parser=argparse.ArgumentParser();parser.add_argument('--seconds',type=int,default=60);args=parser.parse_args()
cli=ROOT/'dist/DualToneCLI.exe';before=[default_output(i) for i in range(3)]
assert before[0]==before[1], 'Do not reroute differing default roles'
original=(ROOT.parent/'release/DualTone-Native/data/settings.json').read_bytes()
rows=json.loads(subprocess.check_output([str(cli),'devices']))['result']
source=next(r for r in rows if r['id']==before[0]);assert source['supported'],source
assert 'CX31993' in source['name'], 'Test only the user-selected physical main'
targets=[r for r in rows if 'Odyssey G65B' in r['name'] and r['supported']];assert len(targets)==1
target=targets[0];assert source['rate']!=target['rate']
stop=threading.Event();errors=[]
def silence_clock():
    mf._com.check_error(mf._ole32.CoInitializeEx(mf._ffi.NULL,0))
    try:
        speaker=sc.get_speaker(source['id']);rate=device_format(speaker)['rate']
        with NativePlayer(speaker._audio_client(),rate,False) as output:
            while not stop.is_set():output.play(np.zeros((rate//100,2),np.float32),stop_event=stop)
    except InterruptedError:pass
    except Exception as ex:errors.append(str(ex))
    finally:mf._ole32.CoUninitialize()
with tempfile.TemporaryDirectory(dir=ROOT/'qa') as folder:
    def call(*a):
        doc=json.loads(subprocess.check_output([str(cli),'--data-dir',folder,*a]));assert doc['ok'],doc;return doc['result']
    call('set','--json',json.dumps(dict(source_id=source['id'],target_id=target['id'],gain=0)))
    clock=threading.Thread(target=silence_clock);clock.start();reports=[]
    try:
        call('start');time.sleep(.5)
        for i in range(args.seconds):
            time.sleep(1);r=call('status')['audio'];reports.append(r)
            assert r['state']=='running',r
            assert r['source_rate']==source['rate'] and r['target_rate']==target['rate'],r
            assert r['output_peak']==0,r
            if i%15==14:print(json.dumps(dict(seconds=i+1,blocks=r['blocks'],queue_ms=r['queue_ms'],discontinuities=r['discontinuities'])),flush=True)
    finally:
        call('shutdown');stop.set();clock.join(timeout=5)
    assert not errors,errors
    assert reports[-1]['blocks']>100
assert [default_output(i) for i in range(3)]==before
assert (ROOT.parent/'release/DualTone-Native/data/settings.json').read_bytes()==original
result=dict(seconds=args.seconds,source_rate=source['rate'],target_rate=target['rate'],blocks=reports[-1]['blocks'],
    queue_min_ms=min(r['queue_ms'] for r in reports),queue_max_ms=max(r['queue_ms'] for r in reports),
    discontinuities=reports[-1]['discontinuities'],dsp_max_ms=reports[-1]['dsp_max_ms'],
    timestamp_valid=reports[-1]['source_timestamp_valid'],defaults_unchanged=True,settings_unchanged=True)
(ROOT/'qa/high-rate-device.json').write_text(json.dumps(dict(summary=result,samples=reports),indent=2),encoding='utf-8')
print(json.dumps(result),flush=True)
