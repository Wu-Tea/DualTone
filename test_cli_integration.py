"""Real separate-process CLI/GUI protocol tests, with isolated config storage."""
import json,subprocess,sys,tempfile,time,unittest
from pathlib import Path
ROOT=Path(__file__).parent

class CliTests(unittest.TestCase):
    def test_gui_and_cli_share_state(self):
        with tempfile.TemporaryDirectory(dir=ROOT,prefix='qa-cli-') as tmp:
            def cli(*args,ok=True):
                p=subprocess.run([sys.executable,str(ROOT/'cli.py'),'--data-dir',tmp,*args],capture_output=True,timeout=20)
                data=json.loads(p.stdout.decode('utf-8'))
                self.assertEqual(p.returncode,0 if ok else 1,data);self.assertEqual(data['ok'],ok);return data
            self.assertFalse(cli('status')['result']['running'])
            self.assertEqual(cli('presets')['result'],{})
            cli('set','--json','{"gain":7.5}')
            self.assertEqual(cli('get')['result']['gain'],7.5)
            gui=subprocess.Popen([sys.executable,str(ROOT/'app.py'),'--data-dir',tmp,'--quit-after','90'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                deadline=time.monotonic()+12
                while not cli('status')['result']['running']:
                    self.assertIsNone(gui.poll(),gui.communicate() if gui.poll() is not None else '')
                    if time.monotonic()>deadline:self.fail('GUI control endpoint did not start')
                result=cli('set','--json','{"gain":6.25,"low":850,"high":3200}')
                self.assertEqual(result['result']['gain'],6.25)
                cli('set','--json','{"low":8000,"high":3000}',ok=False)
                self.assertEqual(cli('get')['result']['low'],850)
                bands=[dict(low=150,high=350,gain_db=0,enabled=True),dict(low=2500,high=4500,gain_db=-6,enabled=True)]
                cli('set','--json',json.dumps({'bands':bands}))
                self.assertEqual(cli('get')['result']['bands'],bands)
                cli('set','--json','{"low":200}')
                self.assertEqual(cli('get')['result']['bands'][1],bands[1])
                self.assertEqual(cli('schema')['result']['filter_bands']['max_count'],8)
                cli('set','--json','{"spatial_mode":"space","spatial_strength":60}')
                self.assertEqual(cli('get')['result']['spatial_mode'],'space')
                self.assertEqual(cli('schema')['result']['spatial']['added_buffer_frames'],0)
                cli('set','--json','{"spatial_mode":"original"}')
                cli('pause','on');self.assertTrue(cli('status')['result']['paused'])
                self.assertEqual(cli('get')['result']['gain'],6.25)
                cli('pause','off');cli('set','--json','{"gain":8,"low":700,"high":3500}')
                path=str(Path(tmp)/'export.json');cli('export',path)
                self.assertEqual(json.loads(Path(path).read_text(encoding='utf-8'))['settings']['low'],700)
                cli('set','--json','{"gain":9}');cli('import',path)
                self.assertEqual(cli('get')['result']['gain'],8)
                cli('preset-add','测试预设');self.assertIn('测试预设',cli('presets')['result'])
                cli('preset-delete','测试预设');self.assertNotIn('测试预设',cli('presets')['result'])
                self.assertIn('main',cli('effects')['result'])
                cli('shutdown');gui.communicate(timeout=8)
                self.assertFalse(cli('status')['result']['running'])
                self.assertEqual(cli('get')['result']['gain'],8)
            finally:
                if gui.poll() is None:
                    try:cli('shutdown');gui.communicate(timeout=8)
                    except Exception:gui.terminate();gui.communicate(timeout=5)

if __name__=='__main__':unittest.main()
