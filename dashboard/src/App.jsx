import { useState, useEffect, useRef, useCallback } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import {
  Activity,
  Radio,
  Wifi,
  WifiOff,
  Zap,
  MapPin,
  Clock,
  Signal,
  ShieldAlert,
  Waves,
} from 'lucide-react';

// ── Brand logo (Vite resolves this to a hashed URL) ─────────────────
import echonetLogo from '../../assets/logo ECho net.png';

// ── Fix Leaflet's broken default icon paths ─────────────────────────
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconUrl: '',
  iconRetinaUrl: '',
  shadowUrl: '',
});

// ── Custom marker icons ─────────────────────────────────────────────
const pulsingIcon = L.divIcon({
  className: 'pulse-marker',
  iconSize: [20, 20],
  iconAnchor: [10, 10],
  popupAnchor: [0, -14],
});

const criticalIcon = L.divIcon({
  className: 'pulse-marker-critical',
  iconSize: [22, 22],
  iconAnchor: [11, 11],
  popupAnchor: [0, -14],
});

// ── Default fallback coordinates (Bengaluru, India) ─────────────────
const DEFAULT_CENTER = [12.9716, 77.5946];

// ── Severity config ─────────────────────────────────────────────────
const SEVERITY_CONFIG = {
  'SOS!':    { color: 'text-red-400',    bg: 'bg-red-500/10',    border: 'border-red-500/40',  icon: criticalIcon, label: 'CRITICAL' },
  'FIRE':    { color: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/40', icon: criticalIcon, label: 'HIGH' },
  'MEDIC':   { color: 'text-amber-400',  bg: 'bg-amber-500/10',  border: 'border-amber-500/40',  icon: pulsingIcon,  label: 'MEDIUM' },
  'TRAPPED': { color: 'text-fuchsia-400', bg: 'bg-fuchsia-500/10', border: 'border-fuchsia-500/40', icon: pulsingIcon,  label: 'HIGH' },
};

const getConfig = (msg) => SEVERITY_CONFIG[msg] || { color: 'text-teal-400', bg: 'bg-teal-500/10', border: 'border-teal-500/40', icon: pulsingIcon, label: 'INFO' };

// ── Logo Image Component (uses actual brand logo via Vite import) ────
function EchoNetLogo({ size = 36 }) {
  return (
    <img
      src={echonetLogo}
      alt="EchoNet Triage"
      width={size}
      height={size}
      className="object-contain"
      style={{ borderRadius: size > 40 ? '12px' : '6px' }}
      draggable={false}
    />
  );
}

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

// ── Component to fly the map to user's geolocation ──────────────────
function GeoLocator({ onLocated }) {
  const map = useMap();
  useEffect(() => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const loc = [pos.coords.latitude, pos.coords.longitude];
        map.flyTo(loc, 14, { animate: true, duration: 1.5 });
        if (onLocated) onLocated(loc);
      },
      (err) => {
        console.warn('Geolocation unavailable, using default center:', err.message);
      },
      { enableHighAccuracy: true, timeout: 8000 }
    );
  }, [map, onLocated]);
  return null;
}

// ── Safe loc parser ─────────────────────────────────────────────────
function parseLoc(loc) {
  if (Array.isArray(loc)) return loc;
  if (typeof loc === 'string') {
    const parts = loc.split(',').map(Number);
    if (parts.length === 2 && parts.every(isFinite)) return parts;
  }
  return [0, 0];
}

// ── Safe timestamp parser ───────────────────────────────────────────
function parseTimestamp(ts) {
  if (ts instanceof Date && !isNaN(ts)) return ts;
  if (typeof ts === 'number') {
    const date = new Date(ts < 1e12 ? ts * 1000 : ts);
    return isNaN(date) ? new Date() : date;
  }
  if (typeof ts === 'string') {
    const date = new Date(ts);
    return isNaN(date) ? new Date() : date;
  }
  return new Date();
}

// ── Relative time helper ────────────────────────────────────────────
function timeAgo(date, now) {
  if (!(date instanceof Date) || isNaN(date)) return '—';
  const seconds = Math.floor((now - date) / 1000);
  if (seconds < 5)  return 'just now';
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  return `${Math.floor(seconds / 3600)}h ago`;
}

// ── WebSocket config ────────────────────────────────────────────────
const WS_URL = 'ws://localhost:8000/ws/live';
const RECONNECT_DELAY_MS = 3000;

// ── Stat Card Component ─────────────────────────────────────────────
function StatCard({ icon: Icon, label, value, accent = 'teal' }) {
  const accentColors = {
    teal:    'from-teal-500/20 to-transparent text-teal-400 border-teal-500/20',
    cyan:    'from-cyan-500/20 to-transparent text-cyan-400 border-cyan-500/20',
    violet:  'from-violet-500/20 to-transparent text-violet-400 border-violet-500/20',
    fuchsia: 'from-fuchsia-500/20 to-transparent text-fuchsia-400 border-fuchsia-500/20',
  };
  const c = accentColors[accent] || accentColors.teal;

  return (
    <div className={`glass-card rounded-xl p-3 bg-gradient-to-br ${c.split(' ')[0]} ${c.split(' ')[1]}`}>
      <div className="flex items-center gap-2 mb-1">
        <Icon className={`w-3.5 h-3.5 ${c.split(' ')[2]}`} />
        <span className="text-[10px] uppercase tracking-wider text-gray-500 font-medium">{label}</span>
      </div>
      <div className={`text-xl font-bold stat-value ${c.split(' ')[2]}`}>{value}</div>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════════════
//  MAIN APP
// ═════════════════════════════════════════════════════════════════════
export default function App() {
  const [packets, setPackets] = useState([]);
  const [wsStatus, setWsStatus] = useState('connecting');
  const [userLocation, setUserLocation] = useState(DEFAULT_CENTER);
  const [currentTime, setCurrentTime] = useState(new Date());
  const wsRef = useRef(null);
  const reconnectTimerRef = useRef(null);

  // ── Live clock ────────────────────────────────────────────────────
  useEffect(() => {
    const t = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  // ── Normalize packet ──────────────────────────────────────────────
  const normalizePacket = useCallback((pkt) => ({
    ...pkt,
    loc: parseLoc(pkt.loc),
    timestamp: parseTimestamp(pkt.timestamp),
  }), []);

  // ── WebSocket with auto-reconnect ─────────────────────────────────
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

  // ── Inject test packet ────────────────────────────────────────────
  const injectTestPacket = () => {
    const lat = userLocation[0] + (Math.random() - 0.5) * 0.05;
    const lng = userLocation[1] + (Math.random() - 0.5) * 0.05;
    setPackets((prev) => [
      ...prev,
      {
        id: `NODE_${Date.now()}_${Math.floor(Math.random() * 100)}`,
        loc: [lat, lng],
        msg: ['SOS!', 'FIRE', 'MEDIC', 'TRAPPED'][Math.floor(Math.random() * 4)],
        timestamp: new Date(),
        ttl: 3,
      },
    ]);
  };

  // ── Derived stats ─────────────────────────────────────────────────
  const criticalCount = packets.filter(p => p.msg === 'SOS!' || p.msg === 'FIRE').length;
  const uniqueNodes = new Set(packets.map(p => p.id)).size;

  return (
    <div className="flex h-screen overflow-hidden font-sans" style={{ background: '#060612' }}>

      {/* ── Ambient background orbs ─────────────────────────────────── */}
      <div className="ambient-orb" style={{ width: 400, height: 400, background: '#14b8a6', top: '-10%', left: '-5%' }} />
      <div className="ambient-orb" style={{ width: 350, height: 350, background: '#8b5cf6', bottom: '-8%', right: '20%', animationDelay: '3s' }} />
      <div className="ambient-orb" style={{ width: 300, height: 300, background: '#d946ef', top: '40%', right: '-5%', animationDelay: '5s' }} />

      {/* ═══ LEFT: MAP PANEL ═══════════════════════════════════════════ */}
      <div className="flex-1 relative z-10">

        {/* ── Top HUD overlay ──────────────────────────────────────── */}
        <div className="absolute top-0 left-0 right-0 p-5 z-[1000] pointer-events-none flex justify-between items-start">

          {/* Brand block */}
          <div className="glass-card rounded-2xl p-4 pointer-events-auto flex items-center gap-3.5 shadow-glow-teal">
            <div className="relative">
              <EchoNetLogo size={40} />
              <div className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-teal-400 border-2 border-echo-dark" 
                   style={{ boxShadow: '0 0 6px rgba(45, 212, 191, 0.8)' }} />
            </div>
            <div>
              <h1 className="text-lg font-bold gradient-text tracking-tight">
                EchoNet Triage
              </h1>
              <p className="text-[10px] text-gray-500 uppercase tracking-[0.2em] font-medium">
                Command Center
              </p>
            </div>
          </div>

          {/* Status + Clock block */}
          <div className="flex items-center gap-3 pointer-events-auto">
            {/* Live clock */}
            <div className="glass-card rounded-xl px-3 py-2 flex items-center gap-2">
              <Clock className="w-3.5 h-3.5 text-gray-500" />
              <span className="text-xs text-gray-400 font-mono stat-value">
                {currentTime.toLocaleTimeString('en-IN', { hour12: false })}
              </span>
            </div>

            {/* Connection status */}
            <div className="glass-card rounded-xl px-3 py-2 flex items-center gap-2.5">
              {wsStatus === 'connected' ? (
                <>
                  <div className="status-dot status-dot-active" />
                  <Wifi className="text-teal-400 w-4 h-4" />
                  <span className="text-xs text-teal-400 font-medium">UPLINK ACTIVE</span>
                </>
              ) : wsStatus === 'connecting' ? (
                <>
                  <div className="status-dot status-dot-warning" />
                  <Activity className="text-amber-400 w-4 h-4 animate-pulse" />
                  <span className="text-xs text-amber-400 font-medium">CONNECTING…</span>
                </>
              ) : (
                <>
                  <div className="status-dot status-dot-error" />
                  <WifiOff className="text-red-400 w-4 h-4" />
                  <span className="text-xs text-red-400 font-medium">RECONNECTING…</span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* ── The Map ──────────────────────────────────────────────── */}
        <MapContainer
          center={DEFAULT_CENTER}
          zoom={13}
          style={{ height: '100%', width: '100%', zIndex: 0 }}
          zoomControl={false}
        >
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; <a href="https://carto.com/">CARTO</a>'
          />
          <MapUpdater packets={packets} />
          <GeoLocator onLocated={setUserLocation} />

          {packets.map((pkt) => {
            const cfg = getConfig(pkt.msg);
            return (
              <Marker key={pkt.id} position={pkt.loc} icon={cfg.icon}>
                <Popup>
                  <div className="min-w-[180px]">
                    <div className="flex items-center gap-2 mb-2">
                      <ShieldAlert className="w-4 h-4" style={{ color: '#ef4444' }} />
                      <span className="font-bold text-sm" style={{ color: '#e2e8f0' }}>{pkt.msg}</span>
                      <span className="text-[9px] px-1.5 py-0.5 rounded-full font-semibold"
                            style={{ background: 'rgba(239,68,68,0.15)', color: '#fca5a5' }}>
                        {cfg.label}
                      </span>
                    </div>
                    <div className="space-y-1 text-xs" style={{ color: '#94a3b8' }}>
                      <div className="flex items-center gap-1.5">
                        <Radio className="w-3 h-3" style={{ color: '#2dd4bf' }} />
                        <span style={{ color: '#2dd4bf' }}>{pkt.id}</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <MapPin className="w-3 h-3" />
                        <span>{pkt.loc[0].toFixed(5)}, {pkt.loc[1].toFixed(5)}</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <Clock className="w-3 h-3" />
                        <span>{pkt.timestamp instanceof Date && !isNaN(pkt.timestamp) 
                          ? pkt.timestamp.toLocaleTimeString() : '—'}</span>
                      </div>
                    </div>
                  </div>
                </Popup>
              </Marker>
            );
          })}
        </MapContainer>

        {/* ── Bottom controls ──────────────────────────────────────── */}
        <div className="absolute bottom-6 left-6 z-[1000] flex items-center gap-3">
          <button
            onClick={injectTestPacket}
            className="glass-card btn-glow rounded-xl text-xs px-4 py-2.5 font-medium flex items-center gap-2 text-teal-300 hover:text-white cursor-pointer"
          >
            <Zap className="w-3.5 h-3.5" />
            Inject Test Signal
          </button>
          <div className="glass-card rounded-xl px-4 py-2.5 flex items-center gap-2">
            <Signal className="w-3.5 h-3.5 text-teal-400" />
            <span className="text-xs font-mono text-teal-300 stat-value">{packets.length}</span>
            <span className="text-xs text-gray-500">signals</span>
          </div>
        </div>

        {/* ── Gradient line at right edge ───────────────────────────── */}
        <div className="absolute top-0 right-0 bottom-0 w-px z-20"
             style={{ background: 'linear-gradient(180deg, transparent, #14b8a6, #8b5cf6, #d946ef, transparent)' }} />
      </div>

      {/* ═══ RIGHT: SIDEBAR ════════════════════════════════════════════ */}
      <div className="w-[400px] flex flex-col z-20 relative"
           style={{ background: 'linear-gradient(180deg, #0a0a1a, #060612)' }}>

        {/* ── Sidebar header ───────────────────────────────────────── */}
        <div className="p-5 pb-4" style={{ borderBottom: '1px solid rgba(30, 30, 63, 0.6)' }}>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2.5">
              <div className="relative">
                <Waves className="w-5 h-5 text-teal-400" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-gray-200 tracking-tight">
                  Live Distress Feed
                </h2>
                <p className="text-[10px] text-gray-600 mt-0.5">
                  Near-ultrasonic mesh monitoring
                </p>
              </div>
            </div>
            {packets.length > 0 && (
              <span className="text-[10px] px-2 py-1 rounded-full font-mono font-medium"
                    style={{ background: 'rgba(20,184,166,0.1)', color: '#2dd4bf', border: '1px solid rgba(20,184,166,0.2)' }}>
                {packets.length} PKT{packets.length !== 1 ? 'S' : ''}
              </span>
            )}
          </div>

          {/* ── Stats grid ─────────────────────────────────────────── */}
          <div className="grid grid-cols-3 gap-2">
            <StatCard icon={Signal}      label="Total"    value={packets.length} accent="teal" />
            <StatCard icon={ShieldAlert} label="Critical" value={criticalCount}  accent="fuchsia" />
            <StatCard icon={Radio}       label="Nodes"    value={uniqueNodes}    accent="violet" />
          </div>
        </div>

        {/* ── Shimmer divider ──────────────────────────────────────── */}
        <div className="shimmer-line h-px w-full" />

        {/* ── Packet feed ──────────────────────────────────────────── */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2.5">
          {packets.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center space-y-4 animate-fade-in">
              <div className="relative">
                <EchoNetLogo size={72} />
                <div className="absolute inset-0 animate-pulse-slow" style={{ background: 'radial-gradient(circle, rgba(20,184,166,0.1), transparent 70%)' }} />
              </div>
              <div className="text-center">
                <p className="text-sm text-gray-500 font-medium">Awaiting Signals</p>
                <p className="text-[10px] text-gray-700 mt-1">
                  Monitoring 18kHz–19kHz mesh band…
                </p>
              </div>
              <div className="flex items-center gap-2 mt-2">
                <div className="w-1.5 h-1.5 rounded-full bg-teal-500 animate-pulse" />
                <div className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse" style={{ animationDelay: '0.3s' }} />
                <div className="w-1.5 h-1.5 rounded-full bg-violet-500 animate-pulse" style={{ animationDelay: '0.6s' }} />
              </div>
            </div>
          ) : (
            packets
              .slice()
              .reverse()
              .map((pkt, i) => {
                const cfg = getConfig(pkt.msg);
                return (
                  <div
                    key={pkt.id}
                    className={`packet-card glass-card glass-card-hover rounded-xl p-3.5 border-l-[3px] ${cfg.border}`}
                    style={{ animationDelay: `${i * 0.05}s` }}
                  >
                    {/* Row 1: message + severity + time */}
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className={`text-sm font-bold ${cfg.color}`}>{pkt.msg}</span>
                        <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-semibold ${cfg.bg} ${cfg.color}`}>
                          {cfg.label}
                        </span>
                      </div>
                      <span className="text-[10px] text-gray-600 font-mono">
                        {timeAgo(pkt.timestamp, currentTime)}
                      </span>
                    </div>

                    {/* Row 2: node ID */}
                    <div className="flex items-center gap-1.5 mb-1.5">
                      <Radio className="w-3 h-3 text-teal-500" />
                      <span className="text-xs text-teal-400 font-mono font-medium">{pkt.id}</span>
                    </div>

                    {/* Row 3: coordinates + TTL */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3 text-[10px] text-gray-500 font-mono">
                        <span className="flex items-center gap-1">
                          <MapPin className="w-2.5 h-2.5" />
                          {pkt.loc[0].toFixed(4)}
                        </span>
                        <span>{pkt.loc[1].toFixed(4)}</span>
                      </div>
                      <span className="text-[9px] text-gray-600 font-mono">
                        TTL: {pkt.ttl}
                      </span>
                    </div>
                  </div>
                );
              })
          )}
        </div>

        {/* ── Sidebar footer ───────────────────────────────────────── */}
        <div className="p-4 flex items-center justify-between"
             style={{ borderTop: '1px solid rgba(30, 30, 63, 0.4)' }}>
          <div className="flex items-center gap-2">
            <EchoNetLogo size={18} />
            <span className="text-[10px] text-gray-600 font-medium">EchoNet Triage v0.4</span>
          </div>
          <span className="text-[9px] text-gray-700 font-mono">
            {currentTime.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}
          </span>
        </div>
      </div>
    </div>
  );
}
