"""
Quick diagnostic: shows the TOP 10 loudest frequencies your mic picks up.
Run this, then play your 18kHz tone from the phone — see if 18kHz even appears.
"""
import sounddevice as sd
import numpy as np

RATE = 48000
CHUNK = 48000  # 1-second window

print("=" * 65)
print("  🔬  MIC FREQUENCY DIAGNOSTIC")
print("=" * 65)
print("  Recording 10 one-second snapshots.")
print("  Play your tone from the phone NOW and hold it close to the mic.")
print("=" * 65)
print()

for i in range(10):
    recording = sd.rec(CHUNK, samplerate=RATE, channels=1, dtype='int16')
    sd.wait()
    data = recording[:, 0].astype(np.float64)

    window = np.hanning(len(data))
    fft_mag = np.abs(np.fft.rfft(data * window))
    freqs = np.fft.rfftfreq(len(data), 1.0 / RATE)
    fft_mag[0] = 0  # kill DC

    # Get top 10 frequencies by magnitude
    top_indices = np.argsort(fft_mag)[-10:][::-1]

    print(f"  ── Snapshot {i+1}/10 ──")
    for rank, idx in enumerate(top_indices, 1):
        freq = freqs[idx]
        mag = fft_mag[idx]
        marker = " ← IN BAND" if 17500 <= freq <= 19500 else ""
        print(f"    #{rank:2d}  {freq:8.0f} Hz   mag={mag:8.0f}{marker}")
    print()

print("=" * 65)
print("  If 18000 Hz does NOT appear in the top 10, your phone speaker")
print("  cannot produce that frequency loudly enough.")
print("  In that case, try 15000 Hz or use a laptop speaker instead.")
print("=" * 65)
