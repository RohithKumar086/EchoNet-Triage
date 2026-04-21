"""
╔══════════════════════════════════════════════════════════════════╗
║        RESONANCE-PROTOCOL  ·  LOOPBACK SELF-TEST                ║
║   Encode → (in-memory) → Decode  — no speakers / mic needed    ║
╚══════════════════════════════════════════════════════════════════╝

Usage:
    python loopback_test.py                # test with default "SOS!"
    python loopback_test.py "FIRE"         # test with custom text
    python loopback_test.py --all          # run full test suite

This is the first thing to run; it validates the entire DSP pipeline
in software before you touch any hardware.
"""

from __future__ import annotations

import sys
import time
import numpy as np

from config import SAMPLE_RATE, SAMPLES_PER_BIT
from fsk_encoder import encode_fsk, text_to_bits, save_wav
from fsk_decoder import decode_buffer


def loopback(text: str, add_noise: bool = False,
             snr_db: float = 20.0) -> tuple[str, bool]:
    """
    Encode *text* to FSK waveform, optionally add AWGN, then decode.
    Returns (decoded_text, success).
    """
    waveform = encode_fsk(text)

    if add_noise:
        # Additive White Gaussian Noise at specified SNR
        signal_power = np.mean(waveform ** 2)
        noise_power  = signal_power / (10 ** (snr_db / 10))
        noise        = np.random.normal(0, np.sqrt(noise_power),
                                        len(waveform)).astype(np.float32)
        waveform     = waveform + noise

    decoded = decode_buffer(waveform, expected_chars=len(text))
    success = decoded == text
    return decoded, success


def run_tests() -> None:
    """Run a suite of loopback tests with different payloads and noise levels."""
    test_cases = [
        # (label, text, noise, snr_db)
        ("Clean 4-char",      "SOS!",  False, 0),
        ("Clean 4-char alt",  "FIRE",  False, 0),
        ("Clean 4-char sym",  "H3LP",  False, 0),
        ("Clean 1-char",      "X",     False, 0),
        ("Clean 8-char",      "EVACUATE"[:8], False, 0),
        ("Noisy 30dB SNR",    "SOS!",  True,  30),
        ("Noisy 20dB SNR",    "SOS!",  True,  20),
        ("Noisy 15dB SNR",    "SOS!",  True,  15),
        ("Noisy 10dB SNR",    "SOS!",  True,  10),
    ]

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║       RESONANCE-PROTOCOL · LOOPBACK TEST SUITE         ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    passed = 0
    failed = 0

    for label, text, noise, snr in test_cases:
        snr_str = f" (SNR={snr}dB)" if noise else ""
        print(f"   ┌─ TEST: {label}{snr_str}  ─  \"{text}\"")

        t0 = time.perf_counter()
        decoded, success = loopback(text, add_noise=noise, snr_db=snr)
        dt = time.perf_counter() - t0

        status = "✅ PASS" if success else "❌ FAIL"
        decoded_display = decoded if decoded else "<empty>"
        print(f"   └─ {status}  →  \"{decoded_display}\"  ({dt*1000:.0f} ms)")
        print()

        if success:
            passed += 1
        else:
            failed += 1

    print("━" * 58)
    total = passed + failed
    print(f"   Results:  {passed}/{total} passed", end="")
    if failed:
        print(f"  ·  {failed} FAILED")
    else:
        print(f"  ·  ALL CLEAR 🎉")
    print()


def main() -> None:
    if "--all" in sys.argv:
        run_tests()
        return

    text = "SOS!"
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            text = arg

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║       RESONANCE-PROTOCOL · LOOPBACK TEST               ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()
    print(f"   📝  Input text : \"{text}\"")
    print(f"   🔢  Bit count  : {len(text) * 8}")
    print()

    t0 = time.perf_counter()
    decoded, success = loopback(text)
    dt = time.perf_counter() - t0

    print()
    if success:
        print(f"   ✅  LOOPBACK SUCCESS  —  \"{text}\"  →  \"{decoded}\"")
    else:
        print(f"   ❌  LOOPBACK FAILED")
        print(f"       Expected : \"{text}\"")
        print(f"       Got      : \"{decoded}\"")
    print(f"   ⏱   Round-trip : {dt*1000:.0f} ms")
    print()

    # Save the waveform for manual inspection
    waveform = encode_fsk(text)
    save_wav(waveform, "loopback_test.wav")


if __name__ == "__main__":
    main()
