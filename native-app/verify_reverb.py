"""Wet-only causality, bounded decay, streaming, transitions and config migration."""
import json,subprocess,tempfile,unittest,time,ctypes
from ctypes import wintypes
from pathlib import Path
import numpy as np
from verify_native import ROOT,driver

CFG=dict(effect_mode='reverb',eq_enabled=False,band_enabled=False,gain=100)
def render(segments,cfg=None,samples=False):
    return driver(dict(command='render',settings={**CFG,**(cfg or {})},segments=segments,samples=samples))['result']

class ReverbTests(unittest.TestCase):
    def test_gui_mode_and_controls_update_cli_state(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'qa') as tmp:
            def call(*args):
                p=subprocess.run([str(ROOT/'dist/DualToneCLI.exe'),'--data-dir',tmp,*args],capture_output=True,timeout=15)
                r=json.loads(p.stdout);self.assertTrue(r['ok'],r);return r['result']
            proc=subprocess.Popen([str(ROOT/'dist/DualTone.exe'),'--data-dir',tmp,'--details','--quit-after','30'],creationflags=subprocess.CREATE_NO_WINDOW)
            user=ctypes.WinDLL('user32',use_last_error=True)
            callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
            user.EnumWindows.argtypes=[callback,wintypes.LPARAM]
            user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
            user.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
            user.PostMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
            handles=[]; editors=[]
            @callback
            def collect(hwnd,_):
                pid=wintypes.DWORD();user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
                title=ctypes.create_unicode_buffer(256);user.GetWindowTextW(hwnd,title,256)
                if pid.value==proc.pid and title.value=='DualTone':handles.append(hwnd)
                if pid.value==proc.pid and title.value=='DualTone · 声音调节':editors.append(hwnd)
                return True
            try:
                for _ in range(60):
                    if call('status')['running']:break
                    time.sleep(.1)
                # IPC is ready before Slint has created its visible HWND.
                for _ in range(50):
                    user.EnumWindows(collect,0)
                    if handles and editors:break
                    time.sleep(.1)
                self.assertTrue(handles)
                hwnd=handles[0]
                def click(x,y):
                    point=x|(y<<16)
                    for msg,key in [(0x200,0),(0x201,1),(0x202,0)]:user.PostMessageW(hwnd,msg,key,point)
                    time.sleep(.2)
                click(330,324);
                hwnd=editors[0];self.assertEqual(call('get')['effect_mode'],'reverb')
                click(210,128);self.assertGreater(call('get')['reverb_size'],60)
                click(530,128);self.assertGreater(call('get')['reverb_decay'],2.5)
                click(748,128);self.assertLess(call('get')['reverb_brightness'],30)
                size=call('get')['reverb_size']
                hwnd=handles[0];click(100,324);self.assertEqual(call('get')['effect_mode'],'space')
                self.assertEqual(call('get')['reverb_size'],size)
            finally:
                if proc.poll() is None:call('shutdown');proc.wait(timeout=10)

    def test_wet_only_and_stereo_tail(self):
        r=render([dict(frames=48000*3,signal='impulse')])
        self.assertGreater(r['first_frame'],900) # No copied dry impulse at frame zero.
        energy=np.asarray(r['energy_100ms'])
        self.assertGreater(energy[:,0].sum(),0)
        self.assertGreater(energy[:,1].sum(),0) # Left-only input reaches both wet channels.
        self.assertGreater(energy[2:8].sum(),1e-8)
        self.assertLess(energy[-5:].sum(),energy[:5].sum()*1e-5)
        self.assertLessEqual(r['peak'],1)

    def test_decay_and_size_controls_are_effective(self):
        signal=[dict(frames=48000*4,signal='impulse')]
        short=render(signal,dict(reverb_decay=.3))
        long=render(signal,dict(reverb_decay=3))
        self.assertGreater(np.asarray(long['energy_100ms'])[10:20].sum(),np.asarray(short['energy_100ms'])[10:20].sum()*100)
        small=render(signal,dict(reverb_size=0))
        large=render(signal,dict(reverb_size=100))
        self.assertGreater(large['first_frame'],small['first_frame']*2)

    def test_packet_boundaries_and_unrelated_edits_preserve_tail(self):
        a=render([dict(frames=24000,signal='impulse',chunk=24000)],samples=True)['samples']
        b=render([dict(frames=24000,signal='impulse',chunk=37)],samples=True)['samples']
        np.testing.assert_array_equal(a,b)
        baseline=render([dict(frames=24000,signal='impulse')],samples=True)['samples']
        patched=render([dict(frames=4800,signal='impulse'),dict(frames=19200,patch={'spatial_strength':10})],samples=True)['samples']
        np.testing.assert_array_equal(baseline,patched)

    def test_live_edits_and_extremes_are_bounded_and_pause_is_silent(self):
        for brightness in (0,100):
            r=render([dict(frames=48000,signal='noise'),dict(frames=48000,signal='noise',patch={'reverb_size':0,'reverb_decay':.2}),dict(frames=4800,patch={'effect_mode':'space'}),dict(frames=48000,patch={'effect_mode':'reverb'})],dict(reverb_size=100,reverb_decay=4,reverb_brightness=brightness))
            self.assertLessEqual(r['peak'],1)
        r=render([dict(frames=9600,signal='impulse'),dict(frames=9600,paused=True)],samples=True)
        self.assertEqual(max(abs(x) for x in r['samples'][19200:]),0)

    def test_validation_migration_and_preset_roundtrip(self):
        for patch in ({'effect_mode':'chorus'},{'reverb_decay':0},{'reverb_size':101},{'reverb_brightness':True}):
            self.assertFalse(driver(dict(command='validate',settings=patch),False)['ok'])
        with tempfile.TemporaryDirectory(dir=ROOT/'qa') as tmp:
            directory=Path(tmp);old={'version':2,'current':{'gain':12},'presets':{'旧预设':{'gain':8}}}
            original=json.dumps(old).encode();(directory/'settings.json').write_bytes(original)
            def call(*args,ok=True):
                p=subprocess.run([str(ROOT/'dist/DualToneCLI.exe'),'--data-dir',tmp,*args],capture_output=True,timeout=15)
                r=json.loads(p.stdout);self.assertEqual(r['ok'],ok,r);return r.get('result')
            cfg=call('get');self.assertEqual(cfg['effect_mode'],'space');self.assertEqual(cfg['gain'],12)
            patch={'effect_mode':'reverb','reverb_size':72,'reverb_decay':2.3,'reverb_brightness':21}
            call('set','--json',json.dumps(patch));call('preset-add','混响')
            self.assertEqual((directory/'settings.v2.backup.json').read_bytes(),original)
            self.assertEqual(json.loads((directory/'settings.json').read_text(encoding="utf-8"))['version'],4)
            call('set','--json','{"effect_mode":"space"}');call('preset','混响')
            for k,v in patch.items():self.assertEqual(call('get')[k],v)
            f=str(directory/'export.json');call('export',f);call('import',f)
            self.assertEqual(json.loads(Path(f).read_text(encoding="utf-8"))['version'],4)
            call('preset','旧预设');self.assertEqual(call('get')['effect_mode'],'space')

if __name__=='__main__':unittest.main(verbosity=2)
