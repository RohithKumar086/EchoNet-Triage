"""
╔══════════════════════════════════════════════════════════════════╗
║              RESONANCE-PROTOCOL  ·  DSP CONFIG                  ║
║         Near-Ultrasonic FSK Codec — Shared Constants            ║
╚══════════════════════════════════════════════════════════════════╝

Frequency-Shift Keying (FSK) parameters for 18-19 kHz acoustic
data transmission.  All encoder/decoder modules import from here
so a single knob-turn propagates everywhere.
"""

# ── Audio Hardware ────────────────────────────────────────────────
SAMPLE_RATE   = 44_100          # Hz — standard rate; Nyquist @ 22.05 kHz
CHANNELS      = 1               # mono
DTYPE         = "float32"       # 32-bit float PCM

# ── FSK Carrier Frequencies ──────────────────────────────────────
FREQ_0        = 18_000          # Hz — represents binary 0
FREQ_1        = 19_000          # Hz — represents binary 1

# ── Timing ───────────────────────────────────────────────────────
BIT_DURATION  = 0.05            # seconds per bit (50 ms → 20 bps)
GUARD_SILENCE = 0.01            # seconds of silence between segments

# ── Amplitude ────────────────────────────────────────────────────
AMPLITUDE     = 0.85            # peak amplitude [0..1]  (leave headroom)
FADE_SAMPLES  = 32              # cosine-taper samples at segment edges

# ── Preamble / Sync ─────────────────────────────────────────────
#   Alternating 1-0 pattern that the decoder looks for before
#   extracting payload bits.  8-bit preamble = 400 ms total.
PREAMBLE_BITS = [1, 0, 1, 0, 1, 0, 1, 0]

# ── Goertzel Detection ───────────────────────────────────────────
#   Window size for the sliding Goertzel detector (in samples).
#   Should match BIT_DURATION exactly.
GOERTZEL_N    = int(SAMPLE_RATE * BIT_DURATION)   # 2205 samples @ 44.1 kHz

# ── Thresholds ───────────────────────────────────────────────────
ENERGY_THRESHOLD    = 0.005     # minimum Goertzel magnitude to count as "tone present"
PREAMBLE_TOLERANCE  = 1        # max bit errors allowed when matching preamble

# ── Derived ──────────────────────────────────────────────────────
SAMPLES_PER_BIT = int(SAMPLE_RATE * BIT_DURATION)
GUARD_SAMPLES   = int(SAMPLE_RATE * GUARD_SILENCE)
