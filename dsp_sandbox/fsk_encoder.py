"""
╔══════════════════════════════════════════════════════════════════╗
║           RESONANCE-PROTOCOL  ·  FSK ENCODER                    ║
║    Phase 1 DSP Sandbox — Transmit text as near-ultrasonic FSK   ║
╚══════════════════════════════════════════════════════════════════╝

Usage:
    python fsk_encoder.py                  # defaults to "SOS!"
    python fsk_encoder.py "FIRE"           # encode custom 4-char string
    python fsk_encoder.py "HELP" --save    # also write to WAV file

Pipeline:
    string  →  ASCII bytes  →  bit array  →  FSK tones  →  speaker
"""

from __future__ import annotations

import sys
import time
import struct
import wave
import numpy as np
import sounddevice as sd

from config import (
    SAMPLE_RATE, CHANNELS, DTYPE,
    FREQ_0, FREQ_1,
    BIT_DURATION, AMPLITUDE, FADE_SAMPLES,
    PREAMBLE_BITS, SAMPLES_PER_BIT, GUARD_SAMPLES,
)

# ─────────────────────────────────────────────────────────────────
# 1.  TEXT  →  BIT ARRAY
# ─────────────────────────────────────────────────────────────────

def text_to_bits(text: str) -> list[int]:
    """
    Convert an ASCII string into a flat list of bits (MSB first).
    Each character becomes 8 bits.

    >>> text_to_bits("A")
    [0, 1, 0, 0, 0, 0, 0, 1]
    """
    bits: list[int] = []
    for ch in text:
        byte_val = ord(ch) & 0xFF          # clamp to 8-bit ASCII
        for shift in range(7, -1, -1):     # MSB → LSB
            bits.append((byte_val >> shift) & 1)
    return bits


# ─────────────────────────────────────────────────────────────────
# 2.  SINGLE-BIT TONE GENERATION
# ─────────────────────────────────────────────────────────────────

def generate_tone(freq: float, duration: float,
                  sample_rate: int = SAMPLE_RATE,
                  amplitude: float = AMPLITUDE) -> np.ndarray:
    """
    Generate a pure sine tone at *freq* Hz for *duration* seconds.
    Applies a raised-cosine (Tukey) taper at both edges to suppress
    spectral splatter from abrupt on/off transitions.
    """
    n_samples = int(sample_rate * duration)
    t = np.arange(n_samples, dtype=np.float32) / sample_rate

    # Pure sine carrier
    signal = amplitude * np.sin(2.0 * np.pi * freq * t, dtype=np.float32)

    # Raised-cosine fade-in / fade-out  (avoids broadband click artefacts)
    fade_len = min(FADE_SAMPLES, n_samples // 2)
    if fade_len > 0:
        taper = 0.5 * (1.0 - np.cos(np.pi * np.arange(fade_len) / fade_len))
        signal[:fade_len]  *= taper.astype(np.float32)
        signal[-fade_len:] *= taper[::-1].astype(np.float32)

    return signal


# ─────────────────────────────────────────────────────────────────
# 3.  FULL FSK WAVEFORM ASSEMBLY
# ─────────────────────────────────────────────────────────────────

def encode_fsk(text: str) -> np.ndarray:
    """
    Build the complete transmit waveform:

        [silence] [preamble tones] [data tones] [silence]

    Returns a 1-D float32 ndarray ready for playback.
    """
    payload_bits = text_to_bits(text)
    all_bits     = PREAMBLE_BITS + payload_bits

    # Pre-compute guard silence
    guard = np.zeros(GUARD_SAMPLES, dtype=np.float32)

    segments: list[np.ndarray] = []
    segments.append(np.zeros(SAMPLES_PER_BIT, dtype=np.float32))  # leading pad

    for bit in all_bits:
        freq = FREQ_1 if bit == 1 else FREQ_0
        tone = generate_tone(freq, BIT_DURATION)
        segments.append(tone)
        segments.append(guard)                       # inter-symbol silence

    segments.append(np.zeros(SAMPLES_PER_BIT, dtype=np.float32))  # trailing pad

    waveform = np.concatenate(segments)
    return waveform


# ─────────────────────────────────────────────────────────────────
# 4.  SAVE TO WAV  (optional, useful for loopback testing)
# ─────────────────────────────────────────────────────────────────

def save_wav(waveform: np.ndarray, filename: str = "fsk_signal.wav") -> None:
    """
    Write the waveform to a 16-bit PCM WAV file.
    """
    pcm16 = np.clip(waveform * 32767, -32768, 32767).astype(np.int16)
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)             # 16-bit
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm16.tobytes())
    print(f"   💾  Saved WAV → {filename}  ({len(pcm16)/SAMPLE_RATE:.2f}s)")


# ─────────────────────────────────────────────────────────────────
# 5.  PRETTY CONSOLE OUTPUT
# ─────────────────────────────────────────────────────────────────

def print_banner(text: str, bits: list[int], waveform: np.ndarray) -> None:
    duration = len(waveform) / SAMPLE_RATE
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║          RESONANCE-PROTOCOL · FSK ENCODER               ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()
    print(f"   📡  Payload text     :  \"{text}\"")
    print(f"   🔢  Payload bits     :  {len(bits)} bits")
    print(f"   🎵  FSK frequencies  :  {FREQ_0} Hz (0)  /  {FREQ_1} Hz (1)")
    print(f"   ⏱   Bit duration     :  {BIT_DURATION*1000:.0f} ms")
    print(f"   📊  Sample rate      :  {SAMPLE_RATE} Hz")
    print(f"   🔊  Waveform length  :  {len(waveform)} samples ({duration:.2f}s)")
    print()
    # Show the first 32 bits as a visual bar
    display_bits = (PREAMBLE_BITS + bits)[:48]
    bar = "".join("█" if b else "░" for b in display_bits)
    print(f"   Bitstream preview:  {bar}")
    print(f"                       {'P'*len(PREAMBLE_BITS)}{'D'*min(len(bits), 48-len(PREAMBLE_BITS))}")
    print(f"                       (P=preamble  D=data)")
    print()


# ─────────────────────────────────────────────────────────────────
# 6.  MAIN
# ─────────────────────────────────────────────────────────────────

def main() -> None:
    # Parse CLI args
    text = "SOS!"
    save_file = False
    for arg in sys.argv[1:]:
        if arg == "--save":
            save_file = True
        else:
            text = arg

    # Validate input
    if len(text) > 16:
        print("⚠  Warning: long payloads increase transmission time.")
    if not all(0 <= ord(c) < 128 for c in text):
        print("⚠  Warning: non-ASCII characters will be clamped to 7-bit.")

    # Encode
    payload_bits = text_to_bits(text)
    waveform     = encode_fsk(text)

    # Display info
    print_banner(text, payload_bits, waveform)

    # Optionally save WAV
    if save_file:
        save_wav(waveform)

    # Play through speakers
    print("   🔊  Transmitting via speaker …")
    print(f"   (Ensure volume is at MAX and decoder is listening)")
    print()
    sd.play(waveform, samplerate=SAMPLE_RATE, blocking=True)
    print("   ✅  Transmission complete.")
    print()


if __name__ == "__main__":
    main()
