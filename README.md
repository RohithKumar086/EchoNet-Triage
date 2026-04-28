<div align="center">
  <img src="https://raw.githubusercontent.com/RohithKumar086/EchoNet-Triage/main/assets/logo%20ECho%20net.png" width="150" height="150" alt="EchoNet Logo"/>
  
  <h1>EchoNet-Triage</h1>
  
  <p><b>When the grid goes dark, the mesh comes alive. An offline-first, near-ultrasonic network for zero-connectivity crisis triage.</b></p>

  <p>
    <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white" alt="Python"/>
    <img src="https://img.shields.io/badge/FastAPI-0.110-009688?logo=fastapi&logoColor=white" alt="FastAPI"/>
    <img src="https://img.shields.io/badge/React-18+-61DAFB?logo=react&logoColor=black" alt="React"/>
    <img src="https://img.shields.io/badge/Kotlin-Android-7F52FF?logo=kotlin&logoColor=white" alt="Kotlin"/>
  </p>
</div>

---

## 🏨 The Crisis: Silence is Deadly

Modern mega-resorts and hospitality complexes are sprawling, concrete-and-steel labyrinths. When a natural disaster (earthquake, hurricane, or wildfire) severs the power grid and knocks out cellular infrastructure, guest communication instantly flatlines. 

Staff are forced to sweep hundreds of rooms blindly. Guests with critical medical needs or those trapped under structural collapse have zero methods to signal for help. **In the golden hour of triage, traditional Wi-Fi and LTE are single points of failure.**

## 🔊 The Solution: EchoNet-Triage

EchoNet is a decentralized acoustic mesh network. We transform the existing smartphones of every guest and staff member into near-ultrasonic communication nodes. 

Using **Frequency-Shift Keying (FSK)** embedded in the inaudible 18kHz–22kHz spectrum, devices autonomously broadcast and relay encrypted, highly-compressed distress packets (SOS, Medical, Trapped) from phone to phone. When a single node in the mesh finally reaches a pocket of external connectivity, the entire aggregated payload is dumped to our crisis command center—instantly painting a live triage map for first responders.

No extra hardware. No cellular service required. Just the air itself.

## ⚙️ System Architecture

We didn't just wrap an API; we engineered an entirely custom audio-telemetry stack from first principles.

### 1. Acoustic DSP Engine (Android / Kotlin)
- **Zero-Dependency Audio Pipeline**: We bypass high-level media players, directly interfacing with Android's `AudioRecord` and `AudioTrack` APIs for raw 16-bit PCM capture and synthesis.
- **Goertzel Algorithm vs. FFT**: Because we only care about specific carrier frequencies (18kHz for binary `0`, 19kHz for binary `1`), computing a full Fast Fourier Transform is computationally wasteful. We implemented an $O(N)$ single-bin Goertzel filter in pure Kotlin, allowing constant, low-latency background listening with minimal battery drain.
- **Streaming State Machine**: Decodes incoming FSK bursts dynamically via a deterministic state machine (`SCANNING` → `EXTRACTING` → `COMPLETE`) using raised-cosine tapering to suppress spectral splatter.

### 2. The Command Bridge (Python / FastAPI)
- **High-Concurrency Intake**: Built on FastAPI to rapidly ingest and deduplicate high-velocity packet dumps when a mesh partition heals.
- **Event-Driven WebSockets**: Instantaneous, zero-polling bridging from the REST ingestion point to connected command dashboards.

### 3. Tactical UI (React / Vite / Tailwind)
- **Live Leaflet Mapping**: A React-Leaflet integration running over custom dark-mode Carto tiles, plotting GPS-encoded distress payloads as pulsing CSS markers.
- **The Live Feed**: Auto-updating, state-managed sidebar feed displaying packet TTLs, node origins, and payload classes in real-time.

### 4. Acoustic Listener (Python DSP — `listen_sos.py`)
- **Calibrated Detection**: On startup, records 5 seconds of ambient silence to build a per-frequency-bin noise fingerprint. This captures hardware artifacts (e.g., 18kHz self-noise from laptop motherboards) as the "normal" baseline.
- **Dual-Gate Trigger**: Detection requires BOTH a spike of 4× above the calibrated baseline AND raw magnitude ≥ 40, with 3 consecutive confirmations. This eliminates false positives from mic self-noise while reliably catching external signals.
- **GPS-Locked Mapping**: Prompts for exact Google Maps coordinates on startup, so the red distress dot appears precisely at the operator's building on the dashboard.

---

## 📂 Project Structure

```
EchoNet-Triage/
├── android_node/          # Kotlin Android FSK client (AudioRecord/AudioTrack)
├── assets/                # Brand logo and media assets
├── backend/               # Python FastAPI backend
│   ├── main.py            # REST + WebSocket server (POST /api/sync, WS /ws/live)
│   ├── listen_sos.py      # Calibrated acoustic listener (v6.0)
│   ├── send_sos_tone.py   # Tone sender for laptop-to-laptop testing
│   ├── chaos_tester.py    # Stress test: simulates 25 offline packet dumps
│   ├── mic_diagnostic.py  # Debug tool: shows top 10 frequencies the mic hears
│   └── requirements.txt   # Python dependencies
├── dashboard/             # React + Vite tactical command center UI
│   └── src/App.jsx        # Dark-mode Leaflet map + real-time distress feed
└── dsp_sandbox/           # FSK codec prototyping (Python)
    ├── config.py          # Shared FSK parameters (18kHz/19kHz carriers)
    ├── fsk_encoder.py     # Text → FSK audio waveform → speaker
    ├── fsk_decoder.py     # Mic → Goertzel detection → decoded text
    └── loopback_test.py   # Encode + decode roundtrip validation
```

---

## 🚀 Running the Full Stack

### Prerequisites
- Python 3.10+ with pip
- Node.js 18+ with npm

### 1. Start the FastAPI Sync Backend
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload
```
Server starts at `http://localhost:8000`. Endpoints:
- `POST /api/sync` — Mobile node packet upload
- `GET  /api/packets` — Retrieve stored packets
- `WS   /ws/live` — Dashboard real-time feed

### 2. Launch the React Dashboard
```bash
cd dashboard
npm install
npm run dev
```
Navigate to `http://localhost:5173` to see the dark-mode Tactical Map.

### 3. Start the Acoustic Listener
```bash
cd backend
python listen_sos.py
```
The listener walks you through:
1. **Location Prompt** — Enter your exact GPS coordinates (right-click on Google Maps → copy coordinates).
2. **Calibration Phase** — Records 5 seconds of room silence. **Do not make any sound** during this phase.
3. **Detection Phase** — Monitors the 8–12 kHz band. When a sustained tone is detected (spike ≥ 4× baseline for 3 consecutive frames), it sends an SOS packet to the backend, which broadcasts it to the dashboard in real-time.

### 4. Generate the SOS Signal (from a second device)

**Option A — Phone (easiest for demos):**
1. Open [onlinetonegenerator.com](https://www.onlinetonegenerator.com/) on your phone
2. Set frequency to **10,000 Hz**, waveform to **Sine**
3. Phone volume → **MAX**
4. Press Play, hold phone near the listener laptop's microphone

**Option B — Another Laptop (strongest signal):**
```bash
cd backend
python send_sos_tone.py           # plays 15kHz for 10s
python send_sos_tone.py 10000     # plays 10kHz for 10s
python send_sos_tone.py 10000 20  # plays 10kHz for 20s
```

**Option C — FSK Encoder (full protocol):**
```bash
cd dsp_sandbox
python fsk_encoder.py "SOS!"     # transmits encoded FSK message
```

### 5. Stress Test (Simulated Batch Dump)
Simulate 25 aggregated offline distress packets being dumped at once:
```bash
cd backend
python chaos_tester.py
```
Watch the dashboard instantly populate with staggered, pulsing red triage markers.

---

## 🔧 Tuning the Listener

All detection parameters are at the top of `backend/listen_sos.py`:

| Parameter | Default | Description |
|---|---|---|
| `FREQ_LOW` / `FREQ_HIGH` | 8000 / 12000 Hz | Detection frequency band |
| `CALIBRATION_SECONDS` | 5 | Seconds of silence to learn baseline |
| `SPIKE_MULTIPLIER` | 4.0× | Signal must be this many times louder than baseline |
| `MIN_MAGNITUDE` | 40 | Raw FFT magnitude floor (blocks near-zero noise bins) |
| `CONFIRM_FRAMES` | 3 | Consecutive 1-second frames required before triggering |
| `COOLDOWN_SECONDS` | 5 | Pause after each confirmed detection |

> **Note on frequency bands:** The production Android app uses `AudioTrack` to generate 18kHz–19kHz FSK signals, bypassing speaker limitations. For live demos using phone speakers (which can't output ultrasonic frequencies), the listener defaults to 8–12 kHz. Adjust `FREQ_LOW` / `FREQ_HIGH` to match your transmitter.

---

## 🛠️ Debugging

**Mic not detecting anything?** Run the diagnostic:
```bash
cd backend
python mic_diagnostic.py
```
Play your tone while it runs — it shows the top 10 loudest frequencies your mic picks up, helping you determine what your speaker can actually produce.

**False positives?** Increase `SPIKE_MULTIPLIER` or `CONFIRM_FRAMES` in `listen_sos.py`.

**Signal too weak?** Decrease `MIN_MAGNITUDE` or move the sender device closer to the microphone.
