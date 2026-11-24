"""Transport delay, clock drift, configuration lifecycle, GUI persistence."""
import json, subprocess, tempfile, unittest
import numpy as np
from pathlib import Path
from verify_native import ROOT, driver

class SyncTests(unittest.TestCase):
    def test_delay_is_stereo_causal_and_packet_independent(self):
        samples=np.zeros((52000,2));samples[0]=[.25,-.5]
        for ms in (0, .5, 37, 1000):
            with self.subTest(ms=ms):
                def run(chunks):
                    return np.array(driver(dict(command='delay',delay_ms=ms,segments=[dict(samples=p.ravel().tolist()) for p in chunks]))['result']['samples']).reshape(-1,2)
                whole=run([samples]);split=run(np.array_split(samples,51))
                np.testing.assert_array_equal(whole,split)
                expected=np.zeros_like(samples);expected[round(ms*48)]=[.25,-.5]
                np.testing.assert_array_equal(whole,expected)

    def test_live_delay_crossfade_is_bounded(self):
        block=np.ones((9600,2))*.1
        result=driver(dict(command='delay',delay_ms=0,segments=[dict(samples=block.ravel().tolist(),delay_ms=d) for d in (0,100,20,0)]))['result']['samples']
        np.testing.assert_allclose(result,.1,atol=1e-14)

    def test_ten_minute_device_clock_drift_is_bounded(self):
        for speed in (.999,1,1.001):
            with self.subTest(speed=speed):
                r=driver(dict(command='clock-queue',speed=speed,packets=60000))['result']
                self.assertEqual(r['underruns'],0,r)
                self.assertLess(r['largest_ms'],60,r)
                self.assertLess(abs(r['correction_ppm']-(speed-1)*1e6),100,r)

    def test_validation_and_feedback_prevention(self):
        for patch in ({'routing_mode':'bad'},{'main_delay_ms':-1},{'main_delay_ms':1001},{'main_delay_ms':True},
                      {'routing_mode':'sync','input_id':'same','source_id':'same'}):
            self.assertFalse(driver(dict(command='validate',settings=patch),False)['ok'])
        d=driver(dict(command='validate',settings={}))['result']
        self.assertEqual(d['routing_mode'],'direct');self.assertEqual(d['main_delay_ms'],0)

    def test_migration_preset_and_import_preserve_routing(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'qa') as tmp:
            directory=ROOT/'qa'/tmp
            current=driver(dict(command='validate',settings={}))['result']
            for key in ('input_id','routing_mode','main_delay_ms'):current.pop(key)
            original=json.dumps(dict(version=3,current=current,presets={})).encode()
            (directory/'settings.json').write_bytes(original)
            def call(*args,ok=True):
                p=subprocess.run([str(ROOT/'dist/DualToneCLI.exe'),'--data-dir',tmp,*args],capture_output=True,timeout=15)
                r=json.loads(p.stdout);self.assertEqual(r['ok'],ok,r);return r.get('result')
            call('set','--json','{"routing_mode":"sync","input_id":"virtual","main_delay_ms":40}',ok=False)
            call('preset-add','我的声音');call('export',str(directory/'preset.json'))
            call('set','--json','{"main_delay_ms":70,"gain":12}')
            call('preset','我的声音');self.assertEqual(call('get')['main_delay_ms'],70)
            call('import',str(directory/'preset.json'));self.assertEqual(call('get')['main_delay_ms'],70)
            self.assertEqual((directory/'settings.v3.backup.json').read_bytes(),original)
            self.assertEqual(json.loads((directory/'settings.json').read_text(encoding='utf-8'))['version'],4)
            call('preset-delete','我的声音');self.assertEqual(call('presets'),{})
            shot=directory/'gui.png'
            subprocess.run([str(ROOT/'dist/DualTone.exe'),'--data-dir',tmp,'--sync-settings','--screenshot',str(shot),'--quit-after','2.3'],timeout=15,check=True)
            visible=json.loads(shot.with_suffix('.json').read_text(encoding='utf-8'))
            self.assertFalse(visible['sync_mode']);self.assertEqual(visible['main_delay_ms'],70)

    def test_retired_sync_config_rolls_back_without_losing_audio_parameters(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'qa') as tmp:
            directory=Path(tmp)
            cfg=driver(dict(command='validate',settings=dict(routing_mode='sync',input_id='virtual',source_id='main',target_id='aux',main_delay_ms=90,gain=23.5,spatial_strength=45)))['result']
            original=json.dumps(dict(version=4,current=cfg,presets={'Old':cfg})).encode()
            (directory/'settings.json').write_bytes(original)
            def call(*args,ok=True):
                p=subprocess.run([str(ROOT/'dist/DualToneCLI.exe'),'--data-dir',tmp,*args],capture_output=True,timeout=15)
                r=json.loads(p.stdout);self.assertEqual(r['ok'],ok,r);return r.get('result')
            now=call('get')
            self.assertEqual(now['routing_mode'],'direct');self.assertEqual(now['main_delay_ms'],0)
            self.assertEqual((directory/'settings.json').read_bytes(),original)
            for k,v in cfg.items():
                if k not in ('routing_mode','main_delay_ms'):self.assertEqual(now[k],v)
            call('set','--json','{"gain":24}')
            self.assertEqual((directory/'settings.v4.backup.json').read_bytes(),original)
            self.assertEqual(json.loads((directory/'settings.json').read_text())['current']['routing_mode'],'direct')
            call('preset','Old');self.assertEqual(call('get')['routing_mode'],'direct')
            self.assertEqual(call('get')['gain'],23.5)
            call('set','--json','{"routing_mode":"sync"}',ok=False)
            self.assertEqual(call('schema')['routing']['modes'],['direct'])

if __name__=='__main__':unittest.main(verbosity=2)
