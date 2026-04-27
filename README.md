<div align="center">
  <img src="https://raw.githubusercontent.com/RohithKumar086/EchoNet-Triage/main/assets/logo%20ECho%20net.png" width="150" height="150" alt="EchoNet Logo"/>
  
  <h1>EchoNet-Triage</h1>
  
  <p><b>When the grid goes dark, the mesh comes alive. An offline-first, near-ultrasonic network for zero-connectivity crisis triage.</b></p>
</div>

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

---

## 🚀 Running the Local Demo

Want to see the Command Center light up? Here is how to run the full stack locally.

### 1. Start the FastAPI Sync Backend
You aren't currently inside your virtual environment (I don't see (venv) in your prompt). Activating it usually fixes the path issues because it points the terminal directly to your local Python installation.The Virtual Environment Fix (Most Important)
```bash
.\venv\Scripts\activate
```
If this works, you will see (venv) appear on the left. Then try running your command again:
```bash
python -m uvicorn main:app --reload
```
2. The py Launcher Fix
If you don't want to use the virtual environment right now, Windows comes with a "Python Launcher" called py. It is much better at finding Python than the standard python command. Try running this:
```bash
py -m uvicorn main:app --reload
```

### 2. Launch the React Dashboard
In a new terminal, spin up the Vite frontend:
```bash
cd dashboard
npm install
npm run dev
```
*Navigate to `http://localhost:5173` to see the dark-mode Tactical Map.*

### 3. Trigger the Chaos Load Test
Simulate the moment an Android node holding 25 aggregated offline distress packets finds internet and dumps them. In a third terminal:
```bash
cd EchoNet-Triage
cd backend
py chaos_tester.py
```
*Watch the frontend instantly populate with staggered, pulsing red triage markers.*
