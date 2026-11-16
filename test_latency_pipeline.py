import sys,unittest,threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'lib'))
import numpy as np
from scipy.signal import firwin,freqz,upfirdn
from resampling import StreamingResampler,decimator_taps
from audio_engine import compatibility
from config import DECIMATOR_TAPS,DECIMATOR_CUTOFF_HZ

class ResamplingTests(unittest.TestCase):
    def test_irregular_packets_match_continuous_reference(self):
        data=np.random.default_rng(2).normal(size=(5000,2))
        for source,target in ((96000,48000),(48000,96000),(44100,48000),(48000,44100),(192000,48000),(48000,192000),(88200,48000),(48000,176400)):
            with self.subTest(source=source,target=target):
                stream=StreamingResampler(source,target);pieces=[];index=0
                for size in (1,7,47,960,5,311,2048,1621):
                    pieces.append(stream.process(data[index:index+size]));index+=size
                expected_count=(len(data)*stream.up+stream.down-1)//stream.down
                expected=upfirdn(stream.taps,data,up=stream.up,down=stream.down,axis=0)[:expected_count]
                actual=np.concatenate(pieces)
                self.assertEqual(len(actual),expected_count)
                np.testing.assert_allclose(actual,expected,atol=1e-12)
                self.assertLessEqual(len(stream.history),stream.memory_frames+stream.down)
    def test_same_rate_has_no_buffer(self):
        x=np.ones((17,2));stream=StreamingResampler(48000,48000)
        self.assertIs(stream.process(x),x)
    def test_minimum_phase_preserves_magnitude_and_reduces_delay(self):
        linear=firwin(DECIMATOR_TAPS,DECIMATOR_CUTOFF_HZ,fs=96000)
        minimum=decimator_taps(96000);f=np.geomspace(20,20000,2000)
        a=freqz(linear,worN=f,fs=96000)[1];b=freqz(minimum,worN=f,fs=96000)[1]
        self.assertLess(np.max(abs(20*np.log10(abs(b/a)))),.001)
        self.assertLess(np.argmax(abs(minimum)),np.argmax(abs(linear)))
        stop=np.linspace(26000,48000,2000)
        response=freqz(minimum,worN=stop,fs=96000)[1]
        self.assertLess(np.max(20*np.log10(np.maximum(abs(response),1e-12))),-45)
    def test_both_roles_accept_native_rates(self):
        for rate in (44100,48000,88200,96000,176400,192000):
            self.assertEqual(compatibility(dict(rate=rate,channels=2,float32=True)),'')
        self.assertIn('声道',compatibility(dict(rate=48000,channels=4,float32=True)))

class SchedulingTests(unittest.TestCase):
    def test_registration_is_thread_scoped_and_released(self):
        from audio_scheduling import AudioScheduling
        result=[]
        def work():
            s=AudioScheduling()
            try:result.append((s.enter(),s.error))
            finally:s.close();result.append(s.handle)
        thread=threading.Thread(target=work);thread.start();thread.join(timeout=3)
        self.assertFalse(thread.is_alive());self.assertEqual(result,[(True,0),None])

if __name__=='__main__':unittest.main()
