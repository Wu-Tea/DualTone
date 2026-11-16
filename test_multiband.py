import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'lib'))
import numpy as np
from scipy.signal import butter,sosfilt,sosfreqz
from config import MAX_FILTER_BANDS,EQ_HEADROOM_DB
from settings import validate,merge_settings,Store
from band_filter import compile_bands,band_response,BandProcessor,band_signature
from audio_engine import compile_dsp

def row(low,high,gain=0,enabled=True):
    return dict(low=low,high=high,gain_db=gain,enabled=enabled)

class MultiBandTests(unittest.TestCase):
    def test_disabled_row_edit_does_not_reset_live_filters(self):
        cfg=validate({'bands':[row(700,1500)]})
        with_disabled=validate({'bands':[row(700,1500),row(2000,5000,0,False)]})
        self.assertEqual(band_signature(cfg),band_signature(with_disabled))
        self.assertEqual(compile_dsp(cfg)['preamp_db'],compile_dsp(with_disabled)['preamp_db'])

    def test_legacy_migration_preserves_response_and_original_file(self):
        legacy=dict(low=700,high=800,gain=10.5)
        cfg=validate(legacy)
        rng=np.random.default_rng(4);signal=rng.normal(0,.1,(4096,2))
        expected=sosfilt(butter(3,[700,800],btype='bandpass',fs=48000,output='sos'),signal,axis=0)
        np.testing.assert_array_equal(BandProcessor(compile_bands(cfg)).process(signal),expected)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'settings.json'
            original=json.dumps(dict(version=1,current=legacy,presets={'saved':legacy})).encode()
            path.write_bytes(original)
            store=Store(directory);self.assertEqual(store.current['bands'],[row(700,800)])
            store.save();self.assertEqual((Path(directory)/'settings.v1.backup.json').read_bytes(),original)
            self.assertEqual(json.loads(path.read_text())['version'],2)
            restored=Store(directory);self.assertEqual(restored.current,store.current)
            self.assertEqual(restored.presets['saved'],cfg)

    def test_legacy_patch_and_range_validation(self):
        cfg=validate({'bands':[row(150,350),row(2500,4500,-6)]})
        edited=merge_settings(cfg,{'low':200})
        self.assertEqual(edited['bands'],[row(200,350),row(2500,4500,-6)])
        self.assertEqual(cfg['bands'][0]['low'],150)
        for bands in ([],[row(0,800)],[row(800,700)],[row(100,1000,float('nan'))],
                      [row(100,1000,13)],[row(100,1000,0,'true')],[row(100,1000)]*(MAX_FILTER_BANDS+1)):
            with self.subTest(bands=bands),self.assertRaises(ValueError):validate({'bands':bands})

    def test_two_passbands_preserve_gap_and_relative_gain(self):
        cfg=validate({'bands':[row(150,350),row(2500,4500,-6)]})
        response=20*np.log10(abs(band_response(compile_bands(cfg),[230,1000,3350])))
        self.assertGreater(response[0],-.2);self.assertLess(response[1],-25)
        self.assertAlmostEqual(response[2],-6,delta=.25)

    def test_streaming_matches_whole_signal_without_frame_delay(self):
        compiled=compile_bands(validate({'bands':[row(150,350),row(2500,4500,-6)]}))
        signal=np.random.default_rng(5).normal(0,.1,(6017,2))
        whole=BandProcessor(compiled).process(signal)
        worker=BandProcessor(compiled)
        pieces=np.concatenate([worker.process(signal[i:i+137]) for i in range(0,len(signal),137)])
        np.testing.assert_array_equal(pieces,whole)
        self.assertEqual(len(pieces),len(signal))
        impulse=np.zeros((480,2));impulse[0]=1
        self.assertGreater(abs(BandProcessor(compiled).process(impulse)[0,0]),0)

    def test_disabled_rows_and_global_bypass(self):
        cfg=validate({'bands':[row(150,350,0,False)]})
        signal=np.ones((480,2))
        np.testing.assert_array_equal(BandProcessor(compile_bands(cfg)).process(signal),np.zeros_like(signal))
        cfg['band_enabled']=False
        self.assertIs(BandProcessor(compile_bands(cfg)).process(signal),signal)

    def test_overlap_eq_headroom_matches_total_response(self):
        dsp=compile_dsp({'bands':[row(300,3500,12),row(1000,4500,6)],'gains':[4.]*10})
        frequencies=np.geomspace(20,20000,50000)
        h=band_response(dsp['band'],frequencies)*sosfreqz(dsp['eq']['sos'],worN=frequencies,fs=48000)[1]
        self.assertLessEqual(20*np.log10(abs(h).max())+dsp['preamp_db'],-EQ_HEADROOM_DB+.001)

if __name__=='__main__':unittest.main()
