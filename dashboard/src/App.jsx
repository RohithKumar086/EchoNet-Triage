import { useState, useEffect, useRef, useCallback } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import { AlertTriangle, Activity, Map as MapIcon, Wifi, WifiOff } from 'lucide-react';

// ── Fix Leaflet's broken default icon paths ─────────────────────────
// Leaflet ships icon images via CSS url() that Vite can't resolve.
// Since we use a custom divIcon, we just delete the defaults entirely
// to prevent 404 console errors for marker-icon.png / marker-shadow.png
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconUrl: '',
  iconRetinaUrl: '',
  shadowUrl: '',
});

// Custom pulsing marker icon
const pulsingIcon = L.divIcon({
  className: 'pulse-marker',
  iconSize: [24, 24],
  iconAnchor: [12, 12],
  popupAnchor: [0, -12],
});

// ── Component to dynamically fly to the latest packet ───────────────
function MapUpdater({ packets }) {
  const map = useMap();
  useEffect(() => {
    if (packets.length > 0) {
      const latest = packets[packets.length - 1];
      if (
        Array.isArray(latest.loc) &&
        latest.loc.length === 2 &&
        isFinite(latest.loc[0]) &&
        isFinite(latest.loc[1])
      ) {
        map.setView(latest.loc, map.getZoom(), { animate: true });
      }
    }
  }, [packets, map]);
  return null;
}

// ── Safe loc parser ─────────────────────────────────────────────────
function parseLoc(loc) {
  if (Array.isArray(loc)) return loc;
  if (typeof loc === 'string') {
    const parts = loc.split(',').map(Number);
    if (parts.length === 2 && parts.every(isFinite)) return parts;
  }
  return [0, 0]; // fallback
}

// ── Safe timestamp parser ───────────────────────────────────────────
function parseTimestamp(ts) {
  if (ts instanceof Date && !isNaN(ts)) return ts;
  if (typeof ts === 'number') {
    // If it looks like seconds (< year 2100 in seconds), convert to ms
    const date = new Date(ts < 1e12 ? ts * 1000 : ts);
    return isNaN(date) ? new Date() : date;
  }
  if (typeof ts === 'string') {
    const date = new Date(ts);
    return isNaN(date) ? new Date() : date;
  }
  return new Date();
}

// ── WebSocket config ────────────────────────────────────────────────
const WS_URL = 'ws://localhost:8000/ws/live';
const RECONNECT_DELAY_MS = 3000;

export default function App() {
  const [packets, setPackets] = useState([]);
  const [wsStatus, setWsStatus] = useState('connecting');
  const wsRef = useRef(null);
  const reconnectTimerRef = useRef(null);

  // ── Normalize an incoming raw packet object ───────────────────────
  const normalizePacket = useCallback((pkt) => ({
    ...pkt,
    loc: parseLoc(pkt.loc),
    timestamp: parseTimestamp(pkt.timestamp),
  }), []);

  // ── WebSocket connection with auto-reconnect ──────────────────────
  useEffect(() => {
    let isMounted = true;

    function connect() {
      if (!isMounted) return;

      setWsStatus('connecting');
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!isMounted) return;
        console.log('✅ WebSocket connected');
        setWsStatus('connected');
      };

      ws.onmessage = (event) => {
        if (!isMounted) return;
        try {
          const data = JSON.parse(event.data);

          if (data.event === 'new_packet' && data.packet) {
            setPackets((prev) => [...prev, normalizePacket(data.packet)]);
          } else if (data.event === 'backfill' && Array.isArray(data.packets)) {
            setPackets(data.packets.map(normalizePacket));
          }
          // Silently ignore 'connected' welcome messages
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };

      ws.onerror = () => {
        if (!isMounted) return;
        console.error('❌ WebSocket error');
        setWsStatus('error');
      };

      ws.onclose = () => {
        if (!isMounted) return;
        console.log('🔌 WebSocket closed — will reconnect…');
        setWsStatus('error');
        wsRef.current = null;

        // Auto-reconnect after delay
        reconnectTimerRef.current = setTimeout(connect, RECONNECT_DELAY_MS);
      };
    }

    connect();

    return () => {
      isMounted = false;
      clearTimeout(reconnectTimerRef.current);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [normalizePacket]);

  // ── Inject a fake test packet (hackathon demo) ────────────────────
  const injectTestPacket = () => {
    const lat = 37.7749 + (Math.random() - 0.5) * 0.05;
    const lng = -122.4194 + (Math.random() - 0.5) * 0.05;
    setPackets((prev) => [
      ...prev,
      {
        id: `NODE_${Math.floor(Math.random() * 1000)}`,
        loc: [lat, lng],
        msg: ['SOS!', 'FIRE', 'MEDIC', 'TRAPPED'][Math.floor(Math.random() * 4)],
        timestamp: new Date(),
        ttl: 3,
      },
    ]);
  };

  return (
    <div className="flex h-screen bg-gray-900 overflow-hidden font-mono">
      {/* ── LEFT: MAP PANEL ─────────────────────────────────────── */}
      <div className="flex-1 relative border-r border-gray-700 shadow-2xl z-10">
        {/* Top HUD overlay */}
        <div className="absolute top-0 left-0 right-0 p-4 z-[1000] pointer-events-none flex justify-between items-start">
          <div className="bg-gray-800/90 backdrop-blur-sm border border-gray-700 p-3 rounded shadow-lg pointer-events-auto">
            <h1 className="text-xl font-bold flex items-center gap-2 text-white">
              <Activity className="text-red-500" />
              EchoNet Command
            </h1>
            <p className="text-xs text-gray-400 mt-1 uppercase tracking-wider">
              Tactical Triage Map
            </p>
          </div>

          <div className="bg-gray-800/90 backdrop-blur-sm border border-gray-700 p-2 rounded shadow-lg pointer-events-auto flex items-center gap-2">
            {wsStatus === 'connected' ? (
              <>
                <Wifi className="text-green-400 w-4 h-4" />
                <span className="text-xs text-green-400">UPLINK ACTIVE</span>
              </>
            ) : wsStatus === 'connecting' ? (
              <>
                <Activity className="text-yellow-400 w-4 h-4 animate-pulse" />
                <span className="text-xs text-yellow-400">CONNECTING…</span>
              </>
            ) : (
              <>
                <WifiOff className="text-red-500 w-4 h-4" />
                <span className="text-xs text-red-500">RECONNECTING…</span>
              </>
            )}
          </div>
        </div>

        {/* The Map */}
        <MapContainer
          center={[37.7749, -122.4194]}
          zoom={13}
          style={{ height: '100%', width: '100%', zIndex: 0 }}
          zoomControl={false}
        >
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; <a href="https://carto.com/">CARTO</a>'
          />
          <MapUpdater packets={packets} />

          {packets.map((pkt) => (
            <Marker key={pkt.id} position={pkt.loc} icon={pulsingIcon}>
              <Popup className="echonet-popup">
                <div className="text-gray-900 font-bold">{pkt.id}</div>
                <div className="text-red-600 text-lg">{pkt.msg}</div>
                <div className="text-xs text-gray-500">
                  {pkt.loc[0].toFixed(4)}, {pkt.loc[1].toFixed(4)}
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>

        {/* Bottom controls */}
        <div className="absolute bottom-6 left-6 z-[1000] flex gap-2">
          <button
            onClick={injectTestPacket}
            className="bg-gray-800 border border-gray-600 text-xs px-3 py-2 rounded shadow-lg hover:bg-gray-700 transition text-white"
          >
            + Inject Test Packet
          </button>
          <div className="bg-gray-800/80 border border-gray-700 text-xs px-3 py-2 rounded text-green-400">
            {packets.length} signals tracked
          </div>
        </div>
      </div>

      {/* ── RIGHT: LIVE FEED SIDEBAR ────────────────────────────── */}
      <div className="w-96 bg-gray-900 flex flex-col shadow-xl z-20">
        <div className="p-4 border-b border-gray-700 bg-gray-800/50">
          <h2 className="text-sm uppercase tracking-widest text-gray-400 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-yellow-500" />
            Live Distress Feed
          </h2>
          <p className="text-[10px] text-gray-600 mt-1">
            {packets.length} packet{packets.length !== 1 ? 's' : ''} received
          </p>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {packets.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-gray-600 space-y-3">
              <MapIcon className="w-12 h-12 opacity-20" />
              <p className="text-xs text-center">
                Monitoring near-ultrasonic
                <br />
                mesh frequencies…
              </p>
            </div>
          ) : (
            packets
              .slice()
              .reverse()
              .map((pkt) => (
                <div
                  key={pkt.id}
                  className="bg-gray-800 border-l-4 border-red-500 rounded p-3 shadow-md transition-all"
                >
                  <div className="flex justify-between items-start mb-1">
                    <span className="text-red-400 font-bold">{pkt.msg}</span>
                    <span className="text-xs text-gray-500">
                      {pkt.timestamp instanceof Date && !isNaN(pkt.timestamp)
                        ? pkt.timestamp.toLocaleTimeString()
                        : '—'}
                    </span>
                  </div>
                  <div className="text-xs text-green-400 mb-1">
                    Node: {pkt.id}
                  </div>
                  <div className="text-[10px] text-gray-500 flex justify-between">
                    <span>LAT: {pkt.loc[0].toFixed(5)}</span>
                    <span>LNG: {pkt.loc[1].toFixed(5)}</span>
                  </div>
                </div>
              ))
          )}
        </div>
      </div>
    </div>
  );
}
