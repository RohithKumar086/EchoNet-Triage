import sounddevice as sd
import numpy as np
import requests
import time
import traceback
import uuid

# ═══════════════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════════════

RATE = 48000
CHUNK = 48000                   # 1-second window for better frequency resolution
API_URL = "http://localhost:8000/api/sync"

# Detection band — the frequency range your transmitter uses
FREQ_LOW  = 17500               # Hz
FREQ_HIGH = 19500               # Hz

# ── SNR-based detection ─────────────────────────────────────────────
#  Instead of a raw magnitude threshold, we compare the PEAK in the
#  detection band against the MEDIAN magnitude of the full spectrum.
#  If peak_in_band / median_of_spectrum > SNR_THRESHOLD, it's a real signal.
#  This adapts automatically to quiet or noisy rooms.
SNR_THRESHOLD = 15.0            # signal must be 15× louder than median noise

# ── Consecutive-frame confirmation ──────────────────────────────────
#  Require N consecutive detections before triggering, to avoid one-off glitches
CONFIRM_FRAMES = 2

# ── Cooldown ────────────────────────────────────────────────────────
COOLDOWN_SECONDS = 3

# ═══════════════════════════════════════════════════════════════════════
#  DSP FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

def analyze_audio(data: np.ndarray):
    """
    Run FFT and return a diagnostic dict:
      - band_peak_freq: loudest frequency in the detection band
      - band_peak_mag:  its magnitude
      - noise_median:   median magnitude across the whole spectrum (noise floor)
      - snr:            band_peak_mag / noise_median  (signal-to-noise ratio)
      - dominant_freq:  loudest frequency in the full spectrum (for display)
    """
    fft_mag = np.abs(np.fft.rfft(data))
    freqs = np.fft.rfftfreq(len(data), 1.0 / RATE)

    # ── Skip DC bin (index 0) ────────────────────────────────────
    fft_mag[0] = 0

    # ── Overall dominant frequency (for ambient display) ─────────
    dominant_freq = float(freqs[np.argmax(fft_mag)])

    # ── Noise floor: median of the ENTIRE spectrum ───────────────
    noise_median = float(np.median(fft_mag))
    # Avoid division by zero
    if noise_median < 1:
        noise_median = 1.0

    # ── Detection band ───────────────────────────────────────────
    band_mask = (freqs >= FREQ_LOW) & (freqs <= FREQ_HIGH)
    if not np.any(band_mask):
        return {
            "band_peak_freq": 0, "band_peak_mag": 0,
            "noise_median": noise_median, "snr": 0,
            "dominant_freq": dominant_freq,
        }

    band_mags = fft_mag[band_mask]
    band_freqs = freqs[band_mask]
    peak_idx = np.argmax(band_mags)

    band_peak_freq = float(band_freqs[peak_idx])
    band_peak_mag = float(band_mags[peak_idx])
    snr = band_peak_mag / noise_median

    return {
        "band_peak_freq": band_peak_freq,
        "band_peak_mag": band_peak_mag,
        "noise_median": noise_median,
        "snr": snr,
        "dominant_freq": dominant_freq,
    }


# ═══════════════════════════════════════════════════════════════════════
#  GEOLOCATION
# ═══════════════════════════════════════════════════════════════════════

def get_current_location():
    try:
        resp = requests.get("https://ipinfo.io/json", timeout=3)
        if resp.status_code == 200:
            return resp.json().get("loc", "12.9716,77.5946")
    except Exception:
        pass
    return "12.9716,77.5946" # Fallback to default if offline

CURRENT_LOC = get_current_location()

# ═══════════════════════════════════════════════════════════════════════
#  MAIN LOOP
# ═══════════════════════════════════════════════════════════════════════

print("=" * 65)
print("  🎤  ECHONET TRIAGE — ACOUSTIC LISTENER  v3.0  (SNR mode)")
print(f"  📡  Detection band  : {FREQ_LOW}–{FREQ_HIGH} Hz")
print(f"  📊  SNR threshold   : {SNR_THRESHOLD}×  (signal vs noise floor)")
print(f"  🔁  Confirm frames  : {CONFIRM_FRAMES}")
print(f"  🎙️  Sample rate     : {RATE} Hz  |  Window: {CHUNK/RATE:.1f}s")
print(f"  🌐  Backend         : {API_URL}")
print("=" * 65)
print()
print("  Legend:  SNR = band peak ÷ noise median")
print("          🔴 = signal detected  |  ⚪ = idle")
print("=" * 65)

consecutive_hits = 0

try:
    while True:
        # Record one chunk
        recording = sd.rec(CHUNK, samplerate=RATE, channels=1, dtype='int16')
        sd.wait()

        data = recording[:, 0].astype(np.float64)
        result = analyze_audio(data)

        snr = result["snr"]
        is_signal = snr >= SNR_THRESHOLD

        # ── Live debug line ──────────────────────────────────────
        status = "🔴 SIGNAL" if is_signal else "⚪ idle  "
        print(
            f"[*] ambient={result['dominant_freq']:6.0f} Hz  "
            f"band={result['band_peak_freq']:7.0f} Hz  "
            f"mag={result['band_peak_mag']:7.0f}  "
            f"noise={result['noise_median']:5.0f}  "
            f"SNR={snr:5.1f}×  "
            f"{status}  "
            f"[{'█' * min(int(snr), 40)}]",
            end="\r",
        )

        if is_signal:
            consecutive_hits += 1
        else:
            consecutive_hits = 0

        # ── Require N consecutive frames to confirm ──────────────
        if consecutive_hits >= CONFIRM_FRAMES:
            consecutive_hits = 0

            print(f"\n\n{'=' * 65}")
            print(f"  🚨  SOS SIGNAL CONFIRMED!")
            print(f"  📻  Frequency : {result['band_peak_freq']:.1f} Hz")
            print(f"  📊  SNR       : {snr:.1f}×  (threshold: {SNR_THRESHOLD}×)")
            print(f"  📈  Band mag  : {result['band_peak_mag']:.0f}  |  Noise floor: {result['noise_median']:.0f}")
            print(f"{'=' * 65}")

            # Build packet matching the DistressPacket schema
            sos_packet = {
                "id": f"SOS_{uuid.uuid4().hex[:8]}",
                "timestamp": int(time.time()),
                "msg": "SOS!",
                "loc": CURRENT_LOC,
                "ttl": 3,
            }

            try:
                response = requests.post(API_URL, json=[sos_packet], timeout=5)
                if response.status_code == 200:
                    resp_data = response.json()
                    print(f"  ✅  Routed to dashboard!  accepted={resp_data.get('accepted')}")
                elif response.status_code == 422:
                    print(f"  ⚠️  Schema mismatch (422): {response.text[:300]}")
                else:
                    print(f"  ⚠️  Backend responded {response.status_code}: {response.text[:200]}")
            except requests.ConnectionError:
                print("  ❌  Backend not reachable — is uvicorn running on port 8000?")
            except Exception as e:
                print(f"  ❌  Send failed: {e}")

            print(f"  💤  Cooling down {COOLDOWN_SECONDS}s…\n")
            time.sleep(COOLDOWN_SECONDS)

except KeyboardInterrupt:
    print("\n\n[!] Listener stopped by user.")
except Exception as e:
    print(f"\n[X] CRITICAL ERROR: {e}")
    traceback.print_exc()