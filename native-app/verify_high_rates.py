"""High-rate conversion: timing, stereo integrity and alias rejection."""
import unittest,subprocess,json
import numpy as np
from verify_native import driver,ROOT
from config import SUPPORTED_DEVICE_RATES_HZ

class HighRateTests(unittest.TestCase):
    def test_schema_and_generated_supported_rates_agree(self):
        r=json.loads(subprocess.check_output([str(ROOT/'dist/DualToneCLI.exe'),'--data-dir',str(ROOT/'qa/schema-high-rate'),'schema']))['result']
        self.assertEqual(r['audio_formats']['sample_rates_hz'],list(SUPPORTED_DEVICE_RATES_HZ))
        self.assertTrue(r['audio_formats']['independent_device_rates'])

    def test_384k_decimation_preserves_audio_and_rejects_aliases(self):
        source=384000;target=48000;frames=source//10;t=np.arange(frames)/source
        levels={}
        for frequency in (1000,20000,30000,60000):
            wave=.25*np.sin(2*np.pi*frequency*t)
            samples=np.column_stack((wave,-wave))
            result=driver(dict(command='resample',source=source,target=target,packets=[samples.ravel().tolist()]))['result']
            actual=np.array(result['samples']).reshape(-1,2)
            self.assertEqual(len(actual),target//10)
            np.testing.assert_allclose(actual[:,0],-actual[:,1],atol=1e-14)
            levels[frequency]=np.sqrt(np.mean(actual[1000:,0]**2))
        reference=.25/np.sqrt(2)
        for frequency in (1000,20000):
            self.assertLess(abs(20*np.log10(levels[frequency]/reference)),.25)
        for frequency in (30000,60000):
            self.assertLess(20*np.log10(levels[frequency]/reference),-50)
        # Raw one-in-eight sample deletion aliases 30 kHz to 18 kHz at full level.
        raw=.25*np.sin(2*np.pi*30000*t)[::8]
        self.assertGreater(np.sqrt(np.mean(raw**2)),levels[30000]*100)

    def test_high_rate_duration_and_packet_boundary_invariance(self):
        samples=np.random.default_rng(381).normal(0,.1,(8193,2))
        for source,target in ((384000,48000),(48000,384000),(352800,48000),(48000,352800)):
            with self.subTest(source=source,target=target):
                def convert(packets):return np.array(driver(dict(command='resample',source=source,target=target,packets=[x.ravel().tolist() for x in packets]))['result']['samples']).reshape(-1,2)
                whole=convert([samples]);chunked=convert(np.split(samples,[1,7,9,64,480,513,4001]))
                self.assertEqual(len(whole),(len(samples)*target+source-1)//source)
                np.testing.assert_array_equal(whole,chunked)
                self.assertTrue(np.isfinite(whole).all())
if __name__=='__main__':unittest.main(verbosity=2)
