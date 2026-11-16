"""Auxiliary-only stereo complement. No lookahead, delay line, or gain boost.

M=(L+R)/2, S=(L-R)/2; output=(k*M+S, k*M-S).
This reduces duplicated center content; it does not identify ambience, voices,
or original surround channels. k stays positive to retain mono compatibility.
"""
import numpy as np
from config import TARGET_RATE_HZ,SPATIAL_MAX_MID_CUT_DB,SPATIAL_TRANSITION_MS

def mid_gain(settings):
    if settings['spatial_mode']=='original':return 1.0
    return 10**(-SPATIAL_MAX_MID_CUT_DB*settings['spatial_strength']/100/20)

class SpatialProcessor:
    def __init__(self,settings):
        self.current=self.target=mid_gain(settings)
        self.remaining=0
        self.ramp_frames=max(1,round(TARGET_RATE_HZ*SPATIAL_TRANSITION_MS/1000))

    def update(self,settings):
        target=mid_gain(settings)
        if target!=self.target:
            self.target=target;self.remaining=self.ramp_frames

    def process(self,packet):
        if not len(packet):return packet
        if self.remaining:
            count=min(len(packet),self.remaining)
            step=(self.target-self.current)/self.remaining
            gains=np.full(len(packet),self.target)
            gains[:count]=self.current+step*np.arange(1,count+1)
            self.current=float(gains[count-1]);self.remaining-=count
            if not self.remaining:self.current=self.target
            cut=(1-gains)[:,None]
        else:
            if self.current==1:return packet
            cut=1-self.current
        return packet-packet.mean(axis=1,keepdims=True)*cut
