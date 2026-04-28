"""
╔══════════════════════════════════════════════════════════════════╗
║            ECHONET TRIAGE — SOS TONE SENDER                     ║
║     Run this on Laptop B to trigger the listener on Laptop A    ║
╚══════════════════════════════════════════════════════════════════╝

Usage:
    python send_sos_tone.py              # plays 15kHz for 10 seconds
    python send_sos_tone.py 18000        # plays 18kHz for 10 seconds
    python send_sos_tone.py 15000 20     # plays 15kHz for 20 seconds
"""

import sys
import numpy as np
import sounddevice as sd
import time

# ── Parse CLI args ──────────────────────────────────────────────────
FREQ = 15000    # Hz — default (phone-safe, most speakers can do this)
DURATION = 10   # seconds

if len(sys.argv) > 1:
    try:
        FREQ = int(sys.argv[1])
    except ValueError:
        pass
if len(sys.argv) > 2:
    try:
        DURATION = int(sys.argv[2])
    except ValueError:
        pass

RATE = 48000
AMPLITUDE = 0.95  # near-max volume

print("=" * 55)
print("  📡  ECHONET TRIAGE — SOS TONE SENDER")
print("=" * 55)
print(f"  🔊  Frequency : {FREQ} Hz")
print(f"  ⏱   Duration  : {DURATION} seconds")
print(f"  🎙️  Rate      : {RATE} Hz")
print(f"  📈  Amplitude : {AMPLITUDE}")
print("=" * 55)
print()
print("  ⚠️  Set your laptop volume to MAX!")
print("  ⚠️  Place this laptop near the listener's microphone!")
print()

# Generate a continuous sine wave
t = np.arange(int(RATE * DURATION), dtype=np.float32) / RATE
tone = (AMPLITUDE * np.sin(2.0 * np.pi * FREQ * t)).astype(np.float32)

# Apply fade-in/out to avoid click artifacts
fade_len = min(1000, len(tone) // 2)
fade_in = 0.5 * (1 - np.cos(np.pi * np.arange(fade_len) / fade_len))
tone[:fade_len] *= fade_in.astype(np.float32)
tone[-fade_len:] *= fade_in[::-1].astype(np.float32)

print(f"  🔊  Transmitting {FREQ} Hz for {DURATION}s …")
print(f"  (You might hear a faint high-pitched tone)")
print()

sd.play(tone, samplerate=RATE, blocking=True)

print("  ✅  Transmission complete!")
print()
