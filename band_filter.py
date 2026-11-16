"""Causal parallel bandpasses. No look-ahead or extra packet buffering."""
import numpy as np
from scipy.signal import butter,sosfilt,sosfreqz
from config import BANDPASS_ORDER,TARGET_RATE_HZ,CHANNEL_COUNT

def compile_bands(settings):
    if not settings['band_enabled']:return None
    return tuple((butter(BANDPASS_ORDER,[row['low'],row['high']],btype='bandpass',fs=TARGET_RATE_HZ,output='sos'),10**(row['gain_db']/20))
                 for row in settings['bands'] if row['enabled'])

def band_signature(settings):
    if not settings['band_enabled']:return None
    return tuple((r['low'],r['high'],r['gain_db']) for r in settings['bands'] if r['enabled'])

def band_response(compiled,frequencies):
    if compiled is None:return np.ones(len(frequencies),complex)
    response=np.zeros(len(frequencies),complex)
    for sos,gain in compiled:response+=sosfreqz(sos,worN=frequencies,fs=TARGET_RATE_HZ)[1]*gain
    return response

class BandProcessor:
    def __init__(self,compiled):
        self.compiled=compiled
        self.states=[np.zeros((len(sos),2,CHANNEL_COUNT)) for sos,_ in (compiled or ())]
    def process(self,packet):
        if self.compiled is None:return packet
        result=np.zeros_like(packet,dtype=np.float64)
        for index,(sos,gain) in enumerate(self.compiled):
            filtered,self.states[index]=sosfilt(sos,packet,axis=0,zi=self.states[index])
            result+=filtered*gain
        return result
