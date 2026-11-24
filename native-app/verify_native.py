"""Numerical and protocol parity with the existing Python implementation."""
import json,sys,subprocess,tempfile,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT.parent),str(ROOT.parent/'lib')]
import numpy as np
from scipy.signal import sosfilt,sosfreqz
from audio_engine import compile_dsp
from band_filter import BandProcessor,band_response
from spatial import SpatialProcessor
from resampling import StreamingResampler
from settings import validate
from control import pipe_name

REVERB_DEFAULTS=dict(routing_mode="direct",input_id="",main_delay_ms=0.0,effect_mode="space",reverb_size=40.0,reverb_decay=1.2,reverb_brightness=40.0)

def native_defaults(cfg):
    return {**validate(cfg),**REVERB_DEFAULTS}

def driver(doc,ok=True):
    p=subprocess.run([str(ROOT/'build/test_driver.exe')],input=json.dumps(doc).encode(),capture_output=True,timeout=30)
    r=json.loads(p.stdout)
    if ok:assert p.returncode==0,r
    return r

class NativeParity(unittest.TestCase):
    def test_dsp_matches_reference(self):
        samples=np.random.default_rng(44).normal(0,.1,(4096,2));freq=np.geomspace(20,20000,400)
        cases=[{},dict(band_enabled=False),dict(gains=[10.5,8,4,.5,.5,3.5,7,10.5,7.5,-8]),
               dict(bands=[dict(low=150,high=350,gain_db=0,enabled=True),dict(low=2500,high=4500,gain_db=-6,enabled=True)]),
               dict(bands=[dict(low=700,high=800,gain_db=0,enabled=True)]),dict(bands=[dict(low=50,high=16000,gain_db=0,enabled=True)]),
               dict(bands=[dict(low=700,high=3500,gain_db=0,enabled=False)]),dict(spatial_mode='original'),dict(eq_enabled=False)]
        for cfg in cases:
            with self.subTest(cfg=cfg):
                cfg=validate(cfg);d=compile_dsp(cfg)
                result=driver(dict(command='dsp',settings=cfg,samples=samples.ravel().tolist(),frequencies=freq.tolist()))['result']
                native_eq=np.array(result['eq']);native_eq=native_eq[:,0]+1j*native_eq[:,1]
                native_band=np.array(result['band']);native_band=native_band[:,0]+1j*native_band[:,1]
                np.testing.assert_allclose(native_band,band_response(d['band'],freq),atol=1e-8)
                np.testing.assert_allclose(abs(native_eq),abs(sosfreqz(d['eq']['sos'],worN=freq,fs=48000)[1]),rtol=3e-4,atol=3e-4)
                x=BandProcessor(d['band']).process(samples)
                if cfg['eq_enabled']:x=sosfilt(d['eq']['sos'],x,axis=0)
                x=SpatialProcessor(cfg).process(x)*cfg['gain']/100*10**(d['preamp_db']/20)
                np.testing.assert_allclose(np.array(result['samples']).reshape(-1,2),x,atol=2e-6)
                self.assertAlmostEqual(result['preamp_db'],d['preamp_db'],places=3)
    def test_all_rate_pairs_packet_boundaries(self):
        samples=np.random.default_rng(4).normal(0,.1,(3000,2));packets=np.split(samples,[1,8,55,1015,1020,1331])
        for rate in (44100,48000,88200,96000,176400,192000):
            for a,b in ((rate,48000),(48000,rate)):
                with self.subTest(source=a,target=b):
                    r=driver(dict(command='resample',source=a,target=b,packets=[x.ravel().tolist() for x in packets]))['result']
                    ref=StreamingResampler(a,b);expected=np.concatenate([ref.process(x) for x in packets])
                    np.testing.assert_allclose(np.array(r['samples']).reshape(-1,2),expected,atol=1e-12)
    def test_validation_and_legacy(self):
        for cfg in ({},{'spatial_mode':'original'},{'low':300,'high':3000},{'bands':None},{'gain':20.25}):
            self.assertEqual(driver(dict(command='validate',settings=cfg))['result'],native_defaults(cfg))
        for cfg in ({'gain':True},{'gain':101},{'gains':[0]*9},{'low':0},{'bands':[]},{'unknown':2},{'eq_enabled':1}):
            self.assertFalse(driver(dict(command='validate',settings=cfg),False)['ok'])
    def test_existing_pipe_namespace(self):
        p=str((ROOT/'qa/中文配置').resolve())
        self.assertEqual(driver(dict(command='pipe',directory=p))['result'],'\\\\.\\pipe\\'+pipe_name(p))
    def test_preset_ui_selection_is_owned_by_configuration(self):
        # A ComboBox model update must not turn "no match" into preset zero:
        # the same index controls the delete action in both windows.
        (ROOT/'qa').mkdir(exist_ok=True)
        for kind,expected in [('empty',-1),('matched',0),('modified',-1)]:
            with self.subTest(kind=kind),tempfile.TemporaryDirectory(dir=ROOT/'qa') as temp:
                directory=Path(temp);current=validate({});preset=validate({})
                if kind=='modified':current['gain']=9
                presets={} if kind=='empty' else {'我的预设':preset}
                (directory/'settings.json').write_text(json.dumps(dict(version=2,current=current,presets=presets)),encoding='utf-8')
                shot=directory/'ui.png'
                p=subprocess.run([str(ROOT/'dist/DualTone.exe'),'--data-dir',temp,'--details','--screenshot',str(shot),'--quit-after','2.2'],creationflags=subprocess.CREATE_NO_WINDOW,timeout=15)
                self.assertEqual(p.returncode,0)
                state=json.loads(shot.with_suffix('.json').read_text(encoding='utf-8'))
                self.assertEqual(state['preset_index'],expected,state)
                self.assertEqual(state['editor_preset_index'],expected,state)
    def test_cli_gui_shared_state(self):
        (ROOT/'qa').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'qa') as temp:
            def call(*args,ok=True):
                p=subprocess.run([str(ROOT/'dist/DualToneCLI.exe'),'--data-dir',temp,*args],capture_output=True,timeout=15)
                r=json.loads(p.stdout);self.assertEqual(r['ok'],ok,r);return r
            self.assertFalse(call('status')['result']['running']);self.assertEqual(call('get')['result'],native_defaults({}))
            call('set','--json','{"gain":7.5,"spatial_strength":49}')
            proc=subprocess.Popen([str(ROOT/'dist/DualTone.exe'),'--data-dir',temp,'--quit-after','60'],creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                deadline=time.monotonic()+15
                while not call('status')['result']['running']:
                    self.assertIsNone(proc.poll())
                    if time.monotonic()>deadline:self.fail('native GUI failed to start')
                    time.sleep(.1)
                call('set','--json','{"gain":6.25,"low":300,"high":3000}')
                self.assertEqual(call('get')['result']['gain'],6.25)
                call('set','--json','{"gain":101}',ok=False)
                call('preset-add','原生预设');call('set','--json','{"gain":9}');call('preset','原生预设')
                self.assertEqual(call('get')['result']['gain'],6.25)
                call('preset-delete','原生预设');self.assertEqual(call('presets')['result'],{})
                call('pause','on');self.assertTrue(call('status')['result']['paused']);call('pause','off')
                f=str(Path(temp)/'preset.json');call('export',f);call('import',f)
                call('shutdown');proc.wait(timeout=10)
                self.assertEqual(call('get')['result']['gain'],6.25)
            finally:
                if proc.poll() is None:proc.terminate();proc.wait(timeout=5)

if __name__=='__main__':unittest.main(verbosity=2)
