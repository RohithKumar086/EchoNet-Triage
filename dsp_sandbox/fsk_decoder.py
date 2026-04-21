"""
╔══════════════════════════════════════════════════════════════════╗
║           RESONANCE-PROTOCOL  ·  FSK DECODER                    ║
║    Phase 1 DSP Sandbox — Receive near-ultrasonic FSK → text     ║
╚══════════════════════════════════════════════════════════════════╝

Usage:
    python fsk_decoder.py                          # listen via mic (5 s)
    python fsk_decoder.py --duration 8             # listen for 8 seconds
    python fsk_decoder.py --file fsk_signal.wav    # decode from WAV file

Pipeline:
    microphone  →  PCM buffer  →  Goertzel filter  →  bit decisions  →  text

The decoder uses the **Goertzel algorithm** — a single-bin DFT that is
vastly more efficient than a full FFT when you only need the energy at
two known frequencies (18 kHz and 19 kHz).  It runs in O(N) per bin
with no complex-number overhead.
"""

from __future__ import annotations

import sys
import wave
import time
import argparse
import numpy as np
import sounddevice as sd

from config import (
    SAMPLE_RATE, CHANNELS, DTYPE,
    FREQ_0, FREQ_1,
    BIT_DURATION, AMPLITUDE, FADE_SAMPLES,
    PREAMBLE_BITS, SAMPLES_PER_BIT,
    GOERTZEL_N, ENERGY_THRESHOLD, PREAMBLE_TOLERANCE,
    GUARD_SAMPLES,
)


# ─────────────────────────────────────────────────────────────────
# 1.  GOERTZEL ALGORITHM
# ─────────────────────────────────────────────────────────────────

def goertzel_magnitude(samples: np.ndarray, target_freq: float,
                       sample_rate: int = SAMPLE_RATE) -> float:
    """
    Compute the magnitude of a single DFT bin at *target_freq* using
    the Goertzel recurrence.  This is O(N) with only real arithmetic.

    The Goertzel recurrence:
        coeff = 2 · cos(2π · k/N)
        s[n]  = x[n] + coeff · s[n−1] − s[n−2]

    After processing all N samples:
        power = s[N−1]² + s[N−2]² − coeff · s[N−1] · s[N−2]
        magnitude = √power

    Parameters
    ----------
    samples : 1-D float array of length N
    target_freq : the frequency bin to evaluate (Hz)
    sample_rate : samples per second

    Returns
    -------
    Magnitude (non-negative real number).
    """
    N = len(samples)
    # Normalised frequency index (need not be integer)
    k = target_freq * N / sample_rate
    omega = 2.0 * np.pi * k / N
    coeff = 2.0 * np.cos(omega)

    # Recurrence
    s_prev2 = 0.0       # s[n-2]
    s_prev1 = 0.0       # s[n-1]

    for x in samples:
        s = float(x) + coeff * s_prev1 - s_prev2
        s_prev2 = s_prev1
        s_prev1 = s

    # Final power calculation
    power = s_prev1**2 + s_prev2**2 - coeff * s_prev1 * s_prev2
    return np.sqrt(max(power, 0.0))


def goertzel_magnitude_vectorized(samples: np.ndarray, target_freq: float,
                                  sample_rate: int = SAMPLE_RATE) -> float:
    """
    Vectorized Goertzel — identical math but uses numpy for speed
    on large windows.  Falls back to the scalar version for small N.
    """
    N = len(samples)
    if N < 256:
        return goertzel_magnitude(samples, target_freq, sample_rate)

    k = target_freq * N / sample_rate
    omega = 2.0 * np.pi * k / N
    coeff = 2.0 * np.cos(omega)

    # Process in scalar (Goertzel is inherently sequential), but the
    # numpy casts avoid Python-level float boxing overhead.
    s1 = np.float64(0.0)
    s2 = np.float64(0.0)
    x_arr = samples.astype(np.float64)

    for i in range(N):
        s = x_arr[i] + coeff * s1 - s2
        s2 = s1
        s1 = s

    power = s1*s1 + s2*s2 - coeff * s1 * s2
    return float(np.sqrt(max(power, 0.0)))


# ─────────────────────────────────────────────────────────────────
# 2.  BIT DECISION  (one window → 0 or 1 or None)
# ─────────────────────────────────────────────────────────────────

def decide_bit(window: np.ndarray) -> int | None:
    """
    Given a window of SAMPLES_PER_BIT audio samples, compute the
    Goertzel magnitude at FREQ_0 and FREQ_1.

    Returns:
        1   if FREQ_1 dominates
        0   if FREQ_0 dominates
        None if neither exceeds the energy threshold (silence)
    """
    mag_0 = goertzel_magnitude_vectorized(window, FREQ_0)
    mag_1 = goertzel_magnitude_vectorized(window, FREQ_1)

    # Normalise to per-sample RMS-like quantity
    norm_0 = mag_0 / len(window)
    norm_1 = mag_1 / len(window)

    # Both below noise floor → silence / no tone
    if norm_0 < ENERGY_THRESHOLD and norm_1 < ENERGY_THRESHOLD:
        return None

    return 1 if mag_1 > mag_0 else 0


# ─────────────────────────────────────────────────────────────────
# 3.  PREAMBLE DETECTION
# ─────────────────────────────────────────────────────────────────

def match_preamble(bits: list[int | None]) -> bool:
    """
    Check whether the last len(PREAMBLE_BITS) decoded bits match the
    expected preamble within PREAMBLE_TOLERANCE bit errors.
    (Hamming-distance match.)
    """
    n = len(PREAMBLE_BITS)
    if len(bits) < n:
        return False

    window = bits[-n:]
    errors = sum(
        1 for a, b in zip(window, PREAMBLE_BITS)
        if a is None or a != b
    )
    return errors <= PREAMBLE_TOLERANCE


# ─────────────────────────────────────────────────────────────────
# 4.  BITS → TEXT
# ─────────────────────────────────────────────────────────────────

def bits_to_text(bits: list[int]) -> str:
    """
    Convert a flat list of bits (MSB first, 8 per char) back into
    an ASCII string.

    >>> bits_to_text([0,1,0,0,0,0,0,1])
    'A'
    """
    chars: list[str] = []
    for i in range(0, len(bits) - 7, 8):
        byte_val = 0
        for j in range(8):
            byte_val = (byte_val << 1) | bits[i + j]
        chars.append(chr(byte_val & 0x7F))
    return "".join(chars)


# ─────────────────────────────────────────────────────────────────
# 5.  FULL DECODE PIPELINE
# ─────────────────────────────────────────────────────────────────

def decode_buffer(audio: np.ndarray, expected_chars: int = 0) -> str:
    """
    Slide through an audio buffer one-bit-window at a time, detect
    the preamble, then extract the payload bits.

    Parameters
    ----------
    audio : 1-D float32 array (mono)
    expected_chars : If > 0, stop after extracting this many characters.
                     If 0, extract until energy drops (end-of-signal).

    Returns
    -------
    Decoded ASCII string.
    """
    step = SAMPLES_PER_BIT + GUARD_SAMPLES    # each symbol = tone + guard
    total_windows = (len(audio) - SAMPLES_PER_BIT) // step

    all_bits: list[int | None] = []
    preamble_found = False
    preamble_end_idx = -1
    payload_bits: list[int] = []
    silence_streak = 0

    print(f"   🔍  Scanning {total_windows} windows …")
    print()

    for w in range(total_windows):
        start = w * step
        end   = start + SAMPLES_PER_BIT
        if end > len(audio):
            break

        window = audio[start:end]
        bit = decide_bit(window)
        all_bits.append(bit)

        # ── State: looking for preamble ──────────────────────────
        if not preamble_found:
            if match_preamble(all_bits):
                preamble_found = True
                preamble_end_idx = w
                print(f"   ✅  Preamble locked at window {w}  "
                      f"(t = {start/SAMPLE_RATE:.3f}s)")
            continue

        # ── State: extracting payload ────────────────────────────
        if bit is None:
            silence_streak += 1
            # 3 consecutive silence windows → assume end of payload
            if silence_streak >= 3:
                break
            continue
        else:
            silence_streak = 0
            payload_bits.append(bit)

        # Stop if we have enough chars
        if expected_chars > 0 and len(payload_bits) >= expected_chars * 8:
            break

    # ── Report ───────────────────────────────────────────────────
    if not preamble_found:
        print("   ❌  Preamble NOT detected in audio buffer.")
        return ""

    decoded_text = bits_to_text(payload_bits)
    n_bits = len(payload_bits)
    print(f"   📦  Extracted {n_bits} payload bits  →  "
          f"{n_bits // 8} characters")
    bar = "".join("█" if b else "░" for b in payload_bits[:64])
    print(f"   Payload bits:  {bar}")
    print(f"   📝  Decoded text: \"{decoded_text}\"")
    return decoded_text


# ─────────────────────────────────────────────────────────────────
# 6.  AUDIO CAPTURE / WAV LOADING
# ─────────────────────────────────────────────────────────────────

def record_audio(duration: float = 5.0) -> np.ndarray:
    """
    Record *duration* seconds of mono audio from the default
    microphone and return a 1-D float32 array.
    """
    n_samples = int(SAMPLE_RATE * duration)
    print(f"   🎙️   Recording {duration:.1f}s of audio …")
    print(f"   (Transmit the FSK signal now!)")
    print()

    audio = sd.rec(n_samples, samplerate=SAMPLE_RATE,
                   channels=CHANNELS, dtype=DTYPE)
    sd.wait()    # block until recording finishes

    return audio.flatten()


def load_wav(filename: str) -> np.ndarray:
    """
    Load a WAV file and return a 1-D float32 array normalised to [-1, 1].
    """
    with wave.open(filename, "rb") as wf:
        n_channels = wf.getnchannels()
        samp_width = wf.getsampwidth()
        n_frames   = wf.getnframes()
        raw_bytes  = wf.readframes(n_frames)

    if samp_width == 2:
        data = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32)
        data /= 32768.0
    elif samp_width == 4:
        data = np.frombuffer(raw_bytes, dtype=np.int32).astype(np.float32)
        data /= 2147483648.0
    else:
        raise ValueError(f"Unsupported sample width: {samp_width}")

    # Mix to mono if stereo
    if n_channels == 2:
        data = (data[0::2] + data[1::2]) / 2.0

    return data


# ─────────────────────────────────────────────────────────────────
# 7.  MAIN
# ─────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resonance-Protocol FSK Decoder")
    parser.add_argument("--file", type=str, default=None,
                        help="Path to WAV file (skip mic recording)")
    parser.add_argument("--duration", type=float, default=5.0,
                        help="Mic recording duration in seconds")
    parser.add_argument("--chars", type=int, default=0,
                        help="Expected number of characters (0 = auto)")
    args = parser.parse_args()

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║          RESONANCE-PROTOCOL · FSK DECODER               ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()
    print(f"   🎵  Listening for:  {FREQ_0} Hz (0)  /  {FREQ_1} Hz (1)")
    print(f"   ⏱   Bit window  :  {BIT_DURATION*1000:.0f} ms "
          f"({SAMPLES_PER_BIT} samples)")
    print()

    # ── Load audio ───────────────────────────────────────────────
    if args.file:
        print(f"   📂  Loading WAV: {args.file}")
        audio = load_wav(args.file)
    else:
        audio = record_audio(args.duration)

    print(f"   📊  Buffer: {len(audio)} samples "
          f"({len(audio)/SAMPLE_RATE:.2f}s)")
    print()

    # ── Decode ───────────────────────────────────────────────────
    result = decode_buffer(audio, expected_chars=args.chars)

    print()
    if result:
        print(f"   ╔═══════════════════════════════════════╗")
        print(f"   ║  DECODED:  \"{result}\"")
        print(f"   ╚═══════════════════════════════════════╝")
    else:
        print("   ⚠  No valid signal detected.  Tips:")
        print("      • Increase speaker volume to max")
        print("      • Move devices closer (< 2m for Phase 1)")
        print("      • Re-run encoder with --save and test with --file")
    print()


if __name__ == "__main__":
    main()
