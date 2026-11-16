import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).parent/'lib'))
import routing
from settings import Store

class RoutingTests(unittest.TestCase):
    def test_auxiliary_switch_validates_before_stop_and_never_changes_defaults(self):
        engine=Mock(active=True);engine.stop.return_value=True
        current=dict(source_id='main',target_id='old')
        updated=dict(source_id='main',target_id='bluetooth')
        with patch('audio_engine.devices',return_value=[dict(id='bluetooth',supported=True,rate=44100,channels=2)]),patch('routing._set_default') as default:
            self.assertTrue(routing.prepare_auxiliary_switch(engine,current,updated))
            engine.stop.assert_called_once();default.assert_not_called()
        engine.reset_mock()
        with patch('audio_engine.devices',return_value=[]):
            with self.assertRaisesRegex(ValueError,'未连接'):routing.prepare_auxiliary_switch(engine,current,updated)
        engine.stop.assert_not_called()
        with self.assertRaisesRegex(ValueError,'主音频'):routing.prepare_auxiliary_switch(engine,current,{**updated,'source_id':'other'})
        engine.stop.assert_not_called()
    def test_auxiliary_reselection_does_not_restart_worker(self):
        engine=Mock(active=True);cfg=dict(source_id='main',target_id='bluetooth')
        self.assertFalse(routing.prepare_auxiliary_switch(engine,cfg,cfg))
        engine.stop.assert_not_called()
    def test_two_playback_roles_change_without_communications(self):
        defaults={0:'old',1:'old-media',2:'voice'};calls=[]
        def setter(device,role):defaults[role]=device;calls.append((device,role))
        with patch('audio_engine.devices',return_value=[dict(id='new',supported=True)]),patch('routing.default_output',side_effect=lambda role:defaults[role]),patch('routing._set_default',side_effect=setter):
            result=routing.sync_main_output('new')
            self.assertTrue(result['changed']);self.assertEqual(calls,[('new',0),('new',1)])
            self.assertEqual(defaults[2],'voice')
            routing.sync_main_output('new');self.assertEqual(len(calls),2)
    def test_second_role_failure_rolls_back_first(self):
        defaults={0:'old',1:'old-media'}
        def setter(device,role):
            if role==1:raise OSError('device refused')
            defaults[role]=device
        with patch('audio_engine.devices',return_value=[dict(id='new',supported=True)]),patch('routing.default_output',side_effect=lambda role:defaults[role]),patch('routing._set_default',side_effect=setter):
            with self.assertRaisesRegex(RuntimeError,'device refused'):routing.sync_main_output('new')
        self.assertEqual(defaults,{0:'old',1:'old-media'})
    def test_missing_device_does_not_mutate_defaults(self):
        with patch('audio_engine.devices',return_value=[]),patch('routing._set_default') as setter:
            with self.assertRaises(ValueError):routing.sync_main_output('missing')
            setter.assert_not_called()

class PresetTests(unittest.TestCase):
    def test_create_delete_persists_without_changing_live_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(directory);store.current['gain']=9
            store.add_preset('我的预设');self.assertEqual(Store(directory).presets['我的预设']['gain'],9)
            store.current['gain']=11
            store.delete_preset('我的预设')
            loaded=Store(directory);self.assertEqual(loaded.presets,{});self.assertEqual(loaded.current['gain'],11)
    def test_duplicates_rejected_but_old_builtin_names_are_available(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(directory);store.add_preset('one')
            with self.assertRaises(ValueError):store.add_preset('one')
            store.add_preset('脚步频段试听');store.delete_preset('脚步频段试听')
            store.add_preset('当前设置');store.current['gain']=12
            self.assertEqual(store.presets['当前设置']['gain'],8)

if __name__=='__main__':unittest.main()
