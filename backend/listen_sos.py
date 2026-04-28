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
CHUNK = 48000                   # 1-second window

API_URL = "http://localhost:8000/api/sync"

# Detection band — lowered for phone speaker compatibility
# Phone speakers can reliably output 500Hz-10kHz.
# In production, the Android FSK app uses AudioTrack at 18kHz (bypasses speaker).
# For demo testing with a phone tone generator website, 8-12kHz works.
FREQ_LOW  = 8000                # Hz
FREQ_HIGH = 12000               # Hz

# ── Calibration ─────────────────────────────────────────────────────
CALIBRATION_SECONDS = 5

# ── Spike detection ─────────────────────────────────────────────────
#  After calibration, we know the baseline magnitude for EVERY frequency bin.
#  A real signal causes a MASSIVE spike in specific bins.
#  current_peak / baseline_at_same_freq > SPIKE_MULTIPLIER → trigger
SPIKE_MULTIPLIER = 4.0

# ── Minimum magnitude gate ──────────────────────────────────────────
#  Bins with near-zero baselines (base=1) can spike to 3-4× from pure
#  random noise. Require the raw magnitude to also exceed this floor.
MIN_MAGNITUDE = 40

# ── Consecutive-frame confirmation ──────────────────────────────────
CONFIRM_FRAMES = 3

# ── Cooldown ────────────────────────────────────────────────────────
COOLDOWN_SECONDS = 5


# ═══════════════════════════════════════════════════════════════════════
#  DSP FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

def compute_fft(data: np.ndarray):
    """Apply Hann window + FFT, return (magnitudes, frequencies)."""
    window = np.hanning(len(data))
    fft_mag = np.abs(np.fft.rfft(data * window))
    freqs = np.fft.rfftfreq(len(data), 1.0 / RATE)
    fft_mag[0] = 0  # kill DC
    return fft_mag, freqs


def get_band_mask(freqs):
    """Return boolean mask for frequency bins in the detection band."""
    return (freqs >= FREQ_LOW) & (freqs <= FREQ_HIGH)


# ═══════════════════════════════════════════════════════════════════════
#  GEOLOCATION
# ═══════════════════════════════════════════════════════════════════════

def get_current_location():
    print("\n" + "=" * 65)
    print("  📍  LOCATION SETUP  (required for accurate dashboard mapping)")
    print("=" * 65)
    print("  How to get your exact coordinates:")
    print("    1. Open Google Maps → right-click your building")
    print("    2. Click the coordinates shown (copies to clipboard)")
    print("    3. Paste them below")
    print()

    while True:
        user_loc = input("  > Enter your coordinates (lat,lng): ").strip()
        user_loc = user_loc.replace(" ", "")

        if not user_loc or "," not in user_loc:
            print("  ⚠️  Invalid format. Please enter as: lat,lng  (e.g. 12.9716,77.5946)")
            continue

        parts = user_loc.split(",")
        if len(parts) != 2:
            print("  ⚠️  Expected exactly two numbers separated by a comma.")
            continue

        try:
            lat = float(parts[0])
            lng = float(parts[1])
        except ValueError:
            print("  ⚠️  Could not parse numbers. Example: 12.9716,77.5946")
            continue

        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            print("  ⚠️  Latitude must be -90..90 and longitude -180..180.")
            continue

        loc = f"{lat},{lng}"
        print(f"  ✅  Location locked: {loc}")
        return loc


CURRENT_LOC = get_current_location()


# ═══════════════════════════════════════════════════════════════════════
#  CALIBRATION PHASE — PER-BIN BASELINE
# ═══════════════════════════════════════════════════════════════════════

print()
print("=" * 65)
print("  🔬  CALIBRATION PHASE — Learning mic noise fingerprint")
print("=" * 65)
print(f"  Recording {CALIBRATION_SECONDS}s of ambient silence…")
print("  ⚠️  DO NOT play any signal during calibration!")
print()

# Accumulate FFT magnitudes for each bin, then take the MAX per bin
baseline_accumulator = None
sample_freqs = None

for i in range(CALIBRATION_SECONDS):
    recording = sd.rec(CHUNK, samplerate=RATE, channels=1, dtype='int16')
    sd.wait()
    data = recording[:, 0].astype(np.float64)
    fft_mag, freqs = compute_fft(data)

    if baseline_accumulator is None:
        baseline_accumulator = fft_mag.copy()
        sample_freqs = freqs
    else:
        # Take the MAX across all calibration frames (conservative baseline)
        baseline_accumulator = np.maximum(baseline_accumulator, fft_mag)

    band_mask = get_band_mask(freqs)
    band_peak = float(np.max(fft_mag[band_mask])) if np.any(band_mask) else 0
    print(f"    [{i+1}/{CALIBRATION_SECONDS}]  band peak mag = {band_peak:.0f}")

# This is the per-bin baseline — includes ALL hardware artifacts
BASELINE = baseline_accumulator
# Ensure no zero bins (avoid division by zero)
BASELINE = np.maximum(BASELINE, 10.0)

band_mask = get_band_mask(sample_freqs)
baseline_band_max = float(np.max(BASELINE[band_mask]))

print()
print(f"  ✅  Calibration complete!")
print(f"      Band baseline max : {baseline_band_max:.0f}")
print(f"      Spike trigger     : {SPIKE_MULTIPLIER}× above per-bin baseline")
print(f"      → A real signal must push its bin {SPIKE_MULTIPLIER}× above its own baseline.")


# ═══════════════════════════════════════════════════════════════════════
#  MAIN LOOP
# ═══════════════════════════════════════════════════════════════════════

print()
print("=" * 65)
print("  🎤  ECHONET TRIAGE — ACOUSTIC LISTENER  v6.0  (per-bin calibrated)")
print(f"  📡  Detection band  : {FREQ_LOW}–{FREQ_HIGH} Hz")
print(f"  📊  Spike trigger   : {SPIKE_MULTIPLIER}× above per-bin baseline")
print(f"  🔁  Confirm frames  : {CONFIRM_FRAMES}")
print(f"  🎙️  Sample rate     : {RATE} Hz  |  Window: {CHUNK/RATE:.1f}s")
print(f"  📍  Location        : {CURRENT_LOC}")
print(f"  🌐  Backend         : {API_URL}")
print("=" * 65)
print()
print("  Legend:  SPIKE = max(current_bin / baseline_bin) across all band bins")
print("          🔴 = signal detected  |  ⚪ = idle")
print("=" * 65)

consecutive_hits = 0

try:
    while True:
        recording = sd.rec(CHUNK, samplerate=RATE, channels=1, dtype='int16')
        sd.wait()

        data = recording[:, 0].astype(np.float64)
        fft_mag, freqs = compute_fft(data)

        # ── Per-bin spike ratio in the detection band ────────────
        band_mask = get_band_mask(freqs)
        band_mags = fft_mag[band_mask]
        band_baseline = BASELINE[band_mask]
        band_freqs = freqs[band_mask]

        # Compute spike ratio for EACH bin: current / baseline
        spike_ratios = band_mags / band_baseline

        # The maximum spike ratio across all band bins
        max_spike_idx = np.argmax(spike_ratios)
        max_spike = float(spike_ratios[max_spike_idx])
        spike_freq = float(band_freqs[max_spike_idx])
        spike_mag = float(band_mags[max_spike_idx])
        spike_base = float(band_baseline[max_spike_idx])

        # Overall dominant frequency
        dominant_freq = float(freqs[np.argmax(fft_mag)])

        is_signal = (max_spike >= SPIKE_MULTIPLIER) and (spike_mag >= MIN_MAGNITUDE)

        # ── Live debug line ──────────────────────────────────────
        status = "🔴 SIGNAL" if is_signal else "⚪ idle  "
        bar_len = min(int(max_spike * 8), 40)
        print(
            f"[*] ambient={dominant_freq:6.0f} Hz  "
            f"spike_at={spike_freq:7.0f} Hz  "
            f"mag={spike_mag:7.0f}  "
            f"base={spike_base:5.0f}  "
            f"SPIKE={max_spike:5.1f}×  "
            f"{status}  "
            f"[{'█' * bar_len}{'░' * (40 - bar_len)}]",
            end="\r",
        )

        if is_signal:
            consecutive_hits += 1
        else:
            consecutive_hits = 0

        if consecutive_hits >= CONFIRM_FRAMES:
            consecutive_hits = 0

            print(f"\n\n{'=' * 65}")
            print(f"  🚨  SOS SIGNAL CONFIRMED!")
            print(f"  📻  Frequency : {spike_freq:.1f} Hz")
            print(f"  📊  Spike     : {max_spike:.1f}×  (threshold: {SPIKE_MULTIPLIER}×)")
            print(f"  📈  Magnitude : {spike_mag:.0f}  |  Baseline: {spike_base:.0f}")
            print(f"{'=' * 65}")

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