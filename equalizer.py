"""Low-latency stereo EQ, RBJ peaking filters fitted to graphic-EQ anchors.

The screenshot supplies approximate gains but no bandwidth or filter design.
Use Q=1.4 and fit the combined response at its ten band centers.
Formula reference: https://www.w3.org/TR/audio-eq-cookbook/
"""
import numpy as np
from scipy.optimize import least_squares
from scipy.signal import sosfreqz
from config import (EQ_FREQUENCIES_HZ,EQ_Q,EQ_HEADROOM_DB,EQ_MAX_DB,TARGET_RATE_HZ,
                    EQ_FIT_TOLERANCE_DB,EQ_FIT_MAX_ITERATIONS,EQ_COEFFICIENT_BOUND_DB,EQ_SCAN_POINTS)

FREQUENCIES = EQ_FREQUENCIES_HZ
IMAGE_GAINS = (10.5, 8, 4, 0.5, 0.5, 3.5, 7, 10.5, 7.5, -8)

def peaking_sos(gains, rate):
    w = 2*np.pi*np.asarray(FREQUENCIES)/rate
    a = 10**(np.asarray(gains)/40)
    alpha = np.sin(w)/(2*EQ_Q)
    c = -2*np.cos(w)
    rows = np.column_stack((1+alpha*a, c, 1-alpha*a,
                            1+alpha/a, c, 1-alpha/a))
    return rows/rows[:, 3:4]

def design_eq(gains, rate=TARGET_RATE_HZ):
    gains = np.asarray(gains, dtype=float)
    if gains.shape != (len(FREQUENCIES),) or not np.all(np.isfinite(gains)) or np.any(abs(gains)>EQ_MAX_DB):
        raise ValueError('10 个频段必须为 -12 到 +12 dB 的有限数值')
    if rate != TARGET_RATE_HZ:
        raise ValueError('此 EQ 预设按显示器 48000 Hz 设计')
    def residual(values):
        _, h = sosfreqz(peaking_sos(values, rate), worN=FREQUENCIES, fs=rate)
        return 20*np.log10(abs(h))-gains
    fitted = least_squares(residual, gains, bounds=(-EQ_COEFFICIENT_BOUND_DB, EQ_COEFFICIENT_BOUND_DB), max_nfev=EQ_FIT_MAX_ITERATIONS)
    if not fitted.success or max(abs(residual(fitted.x))) > EQ_FIT_TOLERANCE_DB:
        raise ValueError('无法准确生成此 EQ 曲线')
    sos = peaking_sos(fitted.x, rate)
    _, h = sosfreqz(sos, worN=np.unique(np.r_[np.geomspace(FREQUENCIES[0]/8,rate/2-1,EQ_SCAN_POINTS),FREQUENCIES]), fs=rate)
    peak_db = max(0.0, float(max(20*np.log10(abs(h)))))
    preamp_db = -float(np.ceil(peak_db+EQ_HEADROOM_DB))
    return {'sos':sos, 'preamp_db':preamp_db, 'peak_db':peak_db,
            'gains':tuple(float(g) for g in gains)}
