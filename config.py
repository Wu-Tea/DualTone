"""Named audio contracts and tuning choices. Units are part of each name.

These are implementation choices, not measured speaker calibration. See
hardware-and-research.md. User-editable parameters live in settings.json.
"""
APP_NAME='DualTone'
SETTINGS_VERSION=2
PROCESSING_RATE_HZ=48000
# Internal DSP clock, independent from both selected endpoint mix formats.
TARGET_RATE_HZ=PROCESSING_RATE_HZ
SUPPORTED_DEVICE_RATES_HZ=(44100,48000,88200,96000,176400,192000,352800,384000)
SUPPORTED_SOURCE_RATES_HZ=SUPPORTED_DEVICE_RATES_HZ
CHANNEL_COUNT=2
SAMPLE_BITS=32
EQ_FREQUENCIES_HZ=(32,64,125,250,500,1000,2000,4000,8000,16000)
EQ_Q=1.4  # Screenshot has no bandwidth; documented approximation.
EQ_HEADROOM_DB=1.0  # Above measured frequency-response peak, not a limiter.
EQ_MAX_DB=12.0
EQ_FIT_TOLERANCE_DB=.15
EQ_FIT_MAX_ITERATIONS=100
EQ_COEFFICIENT_BOUND_DB=30
EQ_SCAN_POINTS=12000
# Extra samples within each active passband resolve very narrow ranges when
# estimating the combined response peak; this is not an audio buffer size.
FILTER_BAND_SCAN_POINTS=65
BANDPASS_ORDER=3
MAX_FILTER_BANDS=8
FILTER_BAND_GAIN_DB=(-24.0,12.0)
NEW_FILTER_BAND_LOW_HZ=2000.0
NEW_FILTER_BAND_HIGH_HZ=5000.0
DECIMATOR_TAPS=63
DECIMATOR_CUTOFF_HZ=21000
DECIMATOR_PHASE='minimum'
RESAMPLER_TAPS_PER_PHASE=64
RESAMPLER_CUTOFF_NYQUIST_FRACTION=.875
# Reject device timestamps displaced from the host QPC epoch. This threshold
# is a validity bound, never an offset added to audio or a resync buffer.
AUDIO_TIMESTAMP_MAX_SKEW_SECONDS=1.0
AUDIO_SCHEDULER_TASK='Pro Audio'
PACKET_POLL_SECONDS=.0005
# Only the idle/stop check has a timeout. Audio-ready events wake immediately.
AUDIO_EVENT_IDLE_TIMEOUT_MS=100
STOP_TIMEOUT_SECONDS=2.0
PEAK_IDLE_SECONDS=.1
AUDIO_MUTEX_NAME='Local\\CodexDualAudioTrial'
SETTINGS_MAX_BYTES=128*1024
PRESET_MAX_COUNT=100
PRESET_NAME_MAX_CHARS=60
DEVICE_ID_MAX_CHARS=256
PARAMETER_LIMITS={'gain':(0,100),'low':(50,15000),'high':(100,16000),'spatial_strength':(0,100)}
# Mid attenuation leaves stereo difference unchanged; it never boosts peaks.
# Full strength retains some center instead of emitting only opposite-polarity sides.
SPATIAL_MODES=('space',)
SPATIAL_DEFAULT_STRENGTH_PERCENT=60.0
SPATIAL_MAX_MID_CUT_DB=12.0
# Coefficient interpolation prevents clicks; samples are never held in a delay line.
SPATIAL_TRANSITION_MS=10.0
IPC_PROTOCOL_VERSION=1
IPC_TIMEOUT_MS=5000
IPC_MAX_BYTES=128*1024

# A conservative listening starting point for Pebble Pro + G65B.
# 8% is software amplitude (-21.94 dB), NOT measured acoustic loudness.
SUPPLEMENT_GAIN_PERCENT=8.0
SUPPLEMENT_LOW_HZ=700.0
SUPPLEMENT_HIGH_HZ=3500.0
FOOTSTEP_TRIAL_LOW_HZ=300.0
FOOTSTEP_TRIAL_HIGH_HZ=3000.0

# Display-only analysis: bounded history, never waited on by audio forwarding.
SPECTRUM_FFT_FRAMES=4096
SPECTRUM_HISTORY_PACKETS=32
SPECTRUM_FLOOR_DB=-90.0
SPECTRUM_DISPLAY_POINTS=320
PLOT_MIN_FREQUENCY_HZ=20
PLOT_MAX_FREQUENCY_HZ=20000
UI_REFRESH_MS=100
UI_EDIT_DEBOUNCE_MS=100
UI_SAVE_DEBOUNCE_MS=500
