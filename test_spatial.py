import sys,unittest,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'lib'))
import numpy as np
from spatial import SpatialProcessor,mid_gain
from settings import validate,Store

class SpatialTests(unittest.TestCase):
    def test_legacy_original_is_exact_but_new_defaults_use_space(self):
        self.assertEqual(validate({})['spatial_mode'],'space')
        self.assertGreater(validate({})['spatial_strength'],0)
        cfg=validate({'gain':29.7,'spatial_mode':'original'})
        self.assertEqual(cfg['spatial_mode'],'space')
        self.assertEqual(cfg['spatial_strength'],0)
        data=np.random.default_rng(1).normal(size=(1000,2))
        np.testing.assert_array_equal(SpatialProcessor(cfg).process(data),data)

    def test_center_reduced_difference_retained_without_sample_delay(self):
        cfg=validate({'spatial_mode':'space','spatial_strength':100})
        center=np.zeros((128,2));center[7]=1
        actual=SpatialProcessor(cfg).process(center)
        np.testing.assert_allclose(actual,center*mid_gain(cfg),atol=1e-15)
        side=center*np.array([1,-1])
        np.testing.assert_array_equal(SpatialProcessor(cfg).process(side),side)
        self.assertEqual(np.argmax(abs(actual[:,0])),7)

    def test_peak_bound_channel_symmetry_no_input_mutation(self):
        data=np.random.default_rng(2).uniform(-1,1,(5000,2));saved=data.copy()
        for strength in (0,30,60,100):
            cfg=validate({'spatial_mode':'space','spatial_strength':strength})
            y=SpatialProcessor(cfg).process(data)
            self.assertLessEqual(float(abs(y).max()),float(abs(data).max())+1e-12)
            np.testing.assert_allclose(SpatialProcessor(cfg).process(data[:,::-1]),y[:,::-1])
        np.testing.assert_array_equal(data,saved)

    def test_transitions_are_chunk_invariant_and_return_to_exact_bypass(self):
        old=validate({'spatial_mode':'original'});new=validate({'spatial_mode':'space'})
        a=SpatialProcessor(old);b=SpatialProcessor(old)
        a.update(new);b.update(new)
        x=np.random.default_rng(3).normal(size=(2000,2))
        expected=a.process(x)
        actual=np.concatenate([b.process(x[:3]),b.process(x[3:47]),b.process(x[47:700]),b.process(x[700:])])
        np.testing.assert_allclose(expected,actual,atol=1e-12)
        b.update(old);b.process(x)
        np.testing.assert_array_equal(b.process(x),x)

    def test_presets_roundtrip_and_invalid_values(self):
        for patch in ({'spatial_mode':'5.1'},{'spatial_strength':101},{'spatial_strength':float('nan')}):
            with self.assertRaises(ValueError):validate(patch)
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(tmp);store.current=validate({'spatial_mode':'space','spatial_strength':72})
            store.add_preset('Space');store.save();loaded=Store(tmp)
            self.assertEqual(loaded.current,store.current)
            self.assertEqual(loaded.presets['Space'],store.current)

if __name__=='__main__':unittest.main()
