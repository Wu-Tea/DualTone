import sys,json,tempfile,unittest,os
# QTest.qWait holds the Python GIL; a threaded QQuickPaintedItem renderer
# would wait for that GIL while qWait waits for the renderer. Real app.exec
# releases it. Use Qt's basic render loop only in this in-process test.
os.environ['QSG_RENDER_LOOP']='basic'
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'lib'))
import numpy as np
from scipy.signal import sosfreqz
from band_filter import band_response
from settings import Store,DEFAULT,validate
from equalizer import FREQUENCIES,IMAGE_GAINS
from audio_engine import compile_dsp,Engine

class SettingsTests(unittest.TestCase):
    def test_roundtrip_and_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Store(tmp);a.current=validate({**DEFAULT,'gain':11,'gains':list(IMAGE_GAINS)})
            a.presets['试听']=a.current.copy();a.save();b=Store(tmp)
            self.assertEqual(a.current,b.current);self.assertEqual(a.presets,b.presets)
            path=Path(tmp)/'export.json';a.export(path,a.current)
            self.assertEqual(a.current,b.import_file(path))
    def test_corrupt_file_preserved(self):
        for text in ('[]','not json','{"version":1,"current":{"gain":NaN}}'):
            with self.subTest(text=text),tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'settings.json';path.write_text(text)
                store=Store(tmp);self.assertTrue(store.load_failed);store.save()
                self.assertEqual(path.read_text(),text)
    def test_invalid_settings(self):
        for cfg in ({'gain':float('nan')},{'gain':101},{'low':1000,'high':500},
                    {'gains':[0]*9},{'gains':[float('inf')]*10},{'eq_enabled':'true'},{'unknown':2}):
            with self.subTest(cfg=cfg),self.assertRaises(ValueError):validate(cfg)
    def test_screenshot_curve(self):
        dsp=compile_dsp({**DEFAULT,'gains':list(IMAGE_GAINS),'band_enabled':False})
        _,h=sosfreqz(dsp['eq']['sos'],worN=FREQUENCIES,fs=48000)
        np.testing.assert_allclose(20*np.log10(abs(h)),IMAGE_GAINS,atol=.15)
        self.assertLessEqual(dsp['eq']['preamp_db']+dsp['eq']['peak_db'],-1)
    def test_supplement_band(self):
        dsp=compile_dsp(DEFAULT)
        h=band_response(dsp['band'],[80,1500,12000])
        db=20*np.log10(abs(h))
        self.assertLess(db[0],-50);self.assertGreater(db[1],-.1);self.assertLess(db[2],-40)
        self.assertEqual(dsp['settings']['gain'],8)
    def test_no_feedback(self):
        dsp=compile_dsp({**DEFAULT,'source_id':'same','target_id':'same'})
        with self.assertRaises(ValueError):Engine().start(dsp)

class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app import QApplication,QQuickStyle
        from unittest.mock import patch
        QQuickStyle.setStyle('FluentWinUI3')
        cls.app=QApplication.instance() or QApplication([])
        routing_patch=patch('ui_model.sync_main_output')
        routing_patch.start();cls.addClassCleanup(routing_patch.stop)
    def test_body_retention_is_direct_and_modes_are_gone(self):
        from app import create_window
        from PySide6.QtTest import QTest
        from PySide6.QtCore import Qt,QPointF
        def find(item,name):
            if item.objectName()==name:return item
            for child in item.childItems():
                result=find(child,name)
                if result:return result
        with tempfile.TemporaryDirectory() as tmp:
            panel,qml,window=create_window(self.app,tmp)
            try:
                QTest.qWait(150)
                strength=find(window.contentItem(),'bodyRetention')
                self.assertTrue(strength.isEnabled())
                self.assertIsNone(find(window.contentItem(),'spatialMode_original'))
                self.assertIsNone(find(window.contentItem(),'spatialMode_space'))
                self.assertEqual(panel.engine.dsp['settings']['spatial_mode'],'space')
                previous=panel.bodyRetention
                strength.forceActiveFocus();QTest.keyClick(window,Qt.Key_Right);QTest.qWait(200)
                self.assertGreater(panel.bodyRetention,previous)
                self.assertLess(panel.settings['spatial_strength'],60)
                for width in (440,420):
                    window.setWidth(width);QTest.qWait(80)
                    for name in ('bodyRetention','presetCombo','targetCombo'):
                        item=find(window.contentItem(),name);position=item.mapToScene(QPointF())
                        self.assertGreaterEqual(position.x(),0)
                        self.assertLessEqual(position.x()+item.width(),width)
                        self.assertLessEqual(position.y()+item.height(),window.height())
                    window.grabWindow().save(str(Path(__file__).parent/f'body-retention-{width}.png'))
                panel.setBodyRetention(100);QTest.qWait(200)
                self.assertEqual(panel.engine.dsp['settings']['spatial_strength'],0)
                panel.setBodyRetention(panel.minimumBodyRetention);QTest.qWait(200)
                self.assertAlmostEqual(panel.engine.dsp['settings']['spatial_strength'],100)
            finally:
                panel.close();window.close();qml.deleteLater();QTest.qWait(50)
    def test_multiband_controls_and_compact_layout(self):
        from app import create_window
        from PySide6.QtTest import QTest
        from PySide6.QtCore import Qt,QPointF
        def find(item,name):
            if item.objectName()==name:return item
            for child in item.childItems():
                result=find(child,name)
                if result:return result
        with tempfile.TemporaryDirectory() as tmp:
            panel,qml,window=create_window(self.app,tmp)
            window.setProperty('details',True);QTest.qWait(100)
            editor=next(v for v in self.app.allWindows() if v.objectName()=='editorWindow')
            try:
                panel.addFilterBand();QTest.qWait(150)
                self.assertFalse(panel.filterBands[1]['enabled'])
                panel.editFilterBand(1,'enabled',True)
                gain=find(editor.contentItem(),'rangeGain1')
                gain.forceActiveFocus();QTest.keyClick(editor,Qt.Key_A,Qt.ControlModifier)
                for key in (Qt.Key_Minus,Qt.Key_6):QTest.keyClick(editor,key)
                QTest.keyClick(editor,Qt.Key_Return);QTest.qWait(150)
                self.assertEqual(panel.filterBands[1]['gain_db'],-6)
                self.assertEqual(panel.engine.dsp['settings']['bands'],panel.filterBands)
                for _ in range(6):panel.addFilterBand()
                QTest.qWait(150)
                self.assertEqual(len(panel.filterBands),8)
                self.assertFalse(find(editor.contentItem(),'addFilterBand').property('enabled'))
                for width,height in ((940,690),(820,650)):
                    editor.setWidth(width);editor.setHeight(height);QTest.qWait(100)
                    for name in ('lowFrequency','highFrequency','rangeGain0'):
                        field=find(editor.contentItem(),name);pos=field.mapToItem(editor.contentItem(),QPointF())
                        self.assertGreaterEqual(pos.x(),0);self.assertLessEqual(pos.x()+field.width(),width)
                        self.assertGreaterEqual(pos.y(),0);self.assertLessEqual(pos.y()+field.height(),height)
                    editor.grabWindow().save(str(Path(__file__).parent/f'multiband-{width}.png'))
                panel.deleteFilterBand(0);QTest.qWait(150)
                self.assertEqual(panel.filterBands[0]['gain_db'],-6)
                self.assertEqual(find(editor.contentItem(),'lowFrequency').property('text'),'2000')
                while len(panel.filterBands)>1:panel.deleteFilterBand(1)
                panel.deleteFilterBand(0);self.assertEqual(len(panel.filterBands),1)
            finally:
                panel.close();editor.close();window.close();qml.deleteLater();QTest.qWait(50)
    def test_eq_columns_do_not_resize_with_numeric_text(self):
        from app import create_window
        from PySide6.QtTest import QTest
        from PySide6.QtCore import QPointF
        def find(item,name):
            if item.objectName()==name:return item
            for child in item.childItems():
                result=find(child,name)
                if result:return result
        with tempfile.TemporaryDirectory() as tmp:
            panel,qml,window=create_window(self.app,tmp)
            window.setProperty('details',True);QTest.qWait(100)
            editor=next(v for v in self.app.allWindows() if v.objectName()=='editorWindow')
            fields=[find(editor.contentItem(),'bandValue'+str(i)) for i in range(10)]
            def geometry():
                return np.array([(f.mapToItem(editor.contentItem(),QPointF()).x(),f.width()) for f in fields])
            try:
                for width in (940,820):
                    editor.setWidth(width)
                    panel.control_set({'gains':[0.0]*10});QTest.qWait(100)
                    baseline=geometry()
                    for value in (9.5,10.0,12.0,-0.5,-12.0):
                        gains=[0.0]*10;gains[0]=value
                        panel.control_set({'gains':gains});QTest.qWait(100)
                        with self.subTest(window_width=width,value=value):
                            np.testing.assert_allclose(geometry(),baseline,atol=.01,rtol=0)
                    # An unfinished edit must not redistribute the columns either.
                    fields[0].setProperty('text','-12.');QTest.qWait(100)
                    np.testing.assert_allclose(geometry(),baseline,atol=.01,rtol=0)
            finally:
                panel.close();editor.close();window.close();qml.deleteLater();QTest.qWait(50)
    def test_preset_choices_are_saved_values_not_current_state_placeholder(self):
        from app import create_window
        from PySide6.QtTest import QTest
        with tempfile.TemporaryDirectory() as tmp:
            panel,qml,window=create_window(self.app,tmp)
            try:
                self.assertEqual(panel.presets,[])
                self.assertEqual(panel.presetName,'')
                self.assertEqual(panel.presetPlaceholder,'尚无预设')
                panel.control_set({'gain':7})
                panel.control_add_preset('A')
                self.assertEqual(panel.presets,['A']);self.assertEqual(panel.presetName,'A')
                panel.control_set({'gain':11})
                self.assertEqual(panel.presetName,'');self.assertFalse(panel.canDeletePreset)
                self.assertEqual(panel.presetPlaceholder,'未保存为预设')
                panel.control_add_preset('B')
                panel.usePreset('A');self.assertEqual(panel.control_get()['gain'],7)
                panel.usePreset('B');self.assertEqual(panel.control_get()['gain'],11)
                panel.control_delete_preset('B')
                self.assertEqual(panel.control_get()['gain'],11);self.assertEqual(panel.presetName,'')
                panel.control_delete_preset('A');self.assertEqual(panel.presets,[])
            finally:
                panel.close();window.close();qml.deleteLater();QTest.qWait(50)
    def test_invalid_frequency_does_not_remain_as_an_unapplied_value(self):
        from app import create_window
        from PySide6.QtTest import QTest
        from PySide6.QtCore import Qt
        def find(item,name):
            if item.objectName()==name:return item
            for child in item.childItems():
                result=find(child,name)
                if result:return result
        with tempfile.TemporaryDirectory() as tmp:
            panel,qml,window=create_window(self.app,tmp)
            window.setProperty('details',True);QTest.qWait(100)
            editor=next(v for v in self.app.allWindows() if v.objectName()=='editorWindow')
            low=find(editor.contentItem(),'lowFrequency');high=find(editor.contentItem(),'highFrequency')
            try:
                low.forceActiveFocus();QTest.keyClick(editor,Qt.Key_A,Qt.ControlModifier)
                QTest.keyClick(editor,Qt.Key_0);QTest.keyClick(editor,Qt.Key_Tab);QTest.qWait(160)
                self.assertEqual(panel.control_get()['low'],700)
                self.assertEqual(low.property('text'),'700')
                low.forceActiveFocus();QTest.keyClick(editor,Qt.Key_A,Qt.ControlModifier)
                QTest.keyClick(editor,Qt.Key_Backspace);QTest.keyClick(editor,Qt.Key_Return);QTest.qWait(160)
                self.assertEqual(low.property('text'),'700')
                high.forceActiveFocus();QTest.keyClick(editor,Qt.Key_A,Qt.ControlModifier)
                for key in (Qt.Key_8,Qt.Key_0,Qt.Key_0):QTest.keyClick(editor,key)
                QTest.keyClick(editor,Qt.Key_Return);QTest.qWait(160)
                self.assertEqual(panel.control_get()['high'],800)
                self.assertEqual(panel.engine.dsp['settings']['high'],800)
                # External updates must keep the display binding after a rejected edit.
                panel.control_set({'low':300});QTest.qWait(100)
                self.assertEqual(low.property('text'),'300')
            finally:
                panel.close();editor.close();window.close();qml.deleteLater();QTest.qWait(50)
    def test_controls_persistence_and_layout(self):
        from app import create_window
        from PySide6.QtTest import QTest
        from PySide6.QtCore import Qt,QObject
        def find(item,name):
            if item.objectName()==name:return item
            for child in item.childItems():
                found=find(child,name)
                if found:return found
        with tempfile.TemporaryDirectory() as tmp:
            panel,qml,w=create_window(self.app,tmp);QTest.qWait(200)
            w.setProperty('details',True);QTest.qWait(100)
            editor=next(v for v in self.app.allWindows() if v.objectName()=='editorWindow')
            value=find(editor.contentItem(),'bandValue6')
            self.assertEqual(value.property('text'),'0.0')
            value.forceActiveFocus()
            QTest.keyClick(editor,Qt.Key_A,Qt.ControlModifier)
            for key in (Qt.Key_4,Qt.Key_Period,Qt.Key_0):QTest.keyClick(editor,key)
            QTest.keyClick(editor,Qt.Key_Return);QTest.qWait(160)
            self.assertEqual(panel.control_get()['gains'][6],4)
            panel.control_set({'gains':list(IMAGE_GAINS),'band_enabled':False})
            panel.control_add_preset('测试曲线')
            panel.usePreset('测试曲线')
            self.assertEqual(panel.control_get()['gains'],list(IMAGE_GAINS))
            self.assertEqual(value.property('text'),'7.0')
            self.assertFalse(panel.control_get()['band_enabled'])
            panel.toggleMute();self.assertEqual(panel.engine.dsp['settings']['gain'],0)
            self.assertEqual(panel.control_get()['gain'],8)
            panel.toggleMute();panel.control_set({k:v for k,v in DEFAULT.items() if k not in ('source_id','target_id')})
            panel.control_set({'gain':9.125})
            self.assertEqual(panel.control_get()['gain'],9.125)
            # Roles are symmetric; 96 kHz endpoints are valid auxiliary choices.
            real=[d for d in panel.device_rows if d['supported']]
            if len(real)>=2:
                panel.control_set(dict(source_id=real[0]['id'],target_id=real[1]['id']))
                self.assertEqual({r['id'] for r in panel.sources},{r['id'] for r in panel.targets})
                panel.swapRoutes()
                self.assertEqual(panel.control_get()['source_id'],real[1]['id'])
                self.assertEqual(panel.control_get()['target_id'],real[0]['id'])
            plot=find(editor.contentItem(),'detailPlot')
            plot.selectAt(plot.px(2000),plot.py(0));plot.dragTo(plot.py(6));QTest.qWait(160)
            self.assertEqual(panel.control_get()['gains'][6],6)
            plot.adjustSelected(.5);QTest.qWait(160)
            self.assertEqual(panel.control_get()['gains'][6],6.5)
            plot.resetSelected();QTest.qWait(160)
            self.assertEqual(panel.control_get()['gains'][6],0)
            panel.control_set({'eq_enabled':False});plot.dragTo(plot.py(8))
            self.assertEqual(panel.control_get()['gains'][6],0)
            self.assertTrue(panel.control_get()['band_enabled'])
            panel.setVisible(False);self.assertFalse(panel.engine.analysis_enabled)
            panel.close();editor.close();w.close();qml.deleteLater();QTest.qWait(50)
            self.assertEqual(Store(tmp).current['gain'],9.125)
    def test_spectrum_tracks_gain_without_stereo_cancellation(self):
        from ui_model import AudioPlot
        from types import SimpleNamespace
        from config import SPECTRUM_FFT_FRAMES,TARGET_RATE_HZ
        mono=np.sin(2*np.pi*1500*np.arange(SPECTRUM_FFT_FRAMES)/TARGET_RATE_HZ)
        stereo=np.column_stack((mono,-mono))
        engine=SimpleNamespace(analysis_packets=[(stereo,stereo*.1)],active=True,status={'input_peak':1.})
        plot=AudioPlot();plot.analyze(engine)
        a,b=plot.spectra
        peak=int(np.argmax(a));self.assertAlmostEqual(a[peak],0,places=3)
        self.assertAlmostEqual(a[peak]-b[peak],20,places=6)
        engine.active=False;plot.analyze(engine);self.assertEqual(plot.spectra,[])

if __name__=='__main__':unittest.main()
