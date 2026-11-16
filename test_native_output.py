"""Regression: never submit more WASAPI frames than provided by the source."""
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).parent/'lib'))
import numpy as np
from native_wasapi import NativePlayer,mf

class FakeOutput(NativePlayer):
    def __init__(self,capacity):
        self.capacity=capacity
        self.storage=mf._ffi.new('BYTE[]',capacity*8)
        self.requested=[]
        self.released=[]
        self.audio=[]
    def _render_available_frames(self):return self.capacity
    def _render_buffer(self,count):
        self.requested.append(count)
        return mf._ffi.new('BYTE**',self.storage)
    def _render_release(self,count):
        self.released.append(count)
        self.audio.append(np.frombuffer(mf._ffi.buffer(self.storage,count*8),dtype=np.float32).copy().reshape(-1,2))

class PacketTests(unittest.TestCase):
    def test_short_packet_does_not_fill_remaining_capacity(self):
        out=FakeOutput(1056)
        data=np.arange(960,dtype=np.float32).reshape(480,2)
        out.play(data)
        self.assertEqual(out.requested,[480])
        self.assertEqual(out.released,[480])
        np.testing.assert_array_equal(np.concatenate(out.audio),data)
    def test_packet_split_preserves_every_stereo_frame(self):
        out=FakeOutput(120)
        data=np.arange(1000,dtype=np.float32).reshape(500,2)
        out.play(data)
        self.assertEqual(out.released,[120,120,120,120,20])
        np.testing.assert_array_equal(np.concatenate(out.audio),data)
    def test_empty_packet_submits_nothing(self):
        out=FakeOutput(1056)
        out.play(np.empty((0,2),np.float32))
        self.assertEqual(out.released,[])

if __name__=='__main__':unittest.main()
