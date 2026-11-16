"""Streaming decimation coefficients shared by playback and measurement."""
from scipy.signal import firwin,minimum_phase,upfirdn
from functools import lru_cache
import math
import numpy as np
from config import (DECIMATOR_TAPS,DECIMATOR_CUTOFF_HZ,DECIMATOR_PHASE,TARGET_RATE_HZ,
                    RESAMPLER_TAPS_PER_PHASE,RESAMPLER_CUTOFF_NYQUIST_FRACTION,CHANNEL_COUNT)

def decimator_taps(source_rate):
    if source_rate==TARGET_RATE_HZ:return None
    taps=firwin(DECIMATOR_TAPS,DECIMATOR_CUTOFF_HZ,fs=source_rate)
    if DECIMATOR_PHASE=='minimum':
        # Retain length and magnitude/alias rejection; half=True would weaken
        # the stopband. Only the unnecessary linear-phase delay is removed.
        return minimum_phase(taps,half=False)
    if DECIMATOR_PHASE=='linear':return taps
    raise ValueError('Unknown decimator phase policy')

@lru_cache(maxsize=32)
def rate_filter(source_rate,target_rate):
    divisor=math.gcd(source_rate,target_rate)
    up,down=target_rate//divisor,source_rate//divisor
    if up==down:return up,down,np.ones(1)
    if source_rate==96000 and target_rate==48000:
        taps=decimator_taps(source_rate)
    else:
        phases=max(up,down)
        linear=firwin(RESAMPLER_TAPS_PER_PHASE*phases+1,RESAMPLER_CUTOFF_NYQUIST_FRACTION/phases)
        taps=minimum_phase(linear,half=False) if DECIMATOR_PHASE=='minimum' else linear
    taps=np.asarray(taps)*up;taps.setflags(write=False)
    return up,down,taps

class StreamingResampler:
    """Causal rational polyphase resampling with packet-boundary invariance.

    History begins on a down-factor boundary so upfirdn's local output grid
    always matches the global grid. Only causally available frames are emitted;
    a packet never flushes the FIR tail or waits for a future packet.
    """
    def __init__(self,source_rate,target_rate):
        self.up,self.down,self.taps=rate_filter(int(source_rate),int(target_rate))
        self.input_frames=0;self.output_frames=0;self.origin=0
        self.history=np.empty((0,CHANNEL_COUNT))
        self.memory_frames=math.ceil((len(self.taps)-1)/self.up)
    def process(self,packet):
        packet=np.asarray(packet)
        if not len(packet):return np.empty((0,CHANNEL_COUNT))
        if self.up==self.down:return packet
        data=np.concatenate((self.history,packet),axis=0)
        total=self.input_frames+len(packet)
        count=(total*self.up+self.down-1)//self.down-self.output_frames
        begin=self.output_frames-self.origin*self.up//self.down
        result=upfirdn(self.taps,data,up=self.up,down=self.down,axis=0)[begin:begin+count]
        origin=max(0,(total-self.memory_frames)//self.down*self.down)
        self.history=data[origin-self.origin:].copy()
        self.origin=origin;self.input_frames=total;self.output_frames+=len(result)
        return result
