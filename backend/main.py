"""
╔══════════════════════════════════════════════════════════════════╗
║         RESONANCE-PROTOCOL  ·  SYNC BACKEND                     ║
║   Phase 4 — FastAPI server: REST intake + WebSocket broadcast    ║
╚══════════════════════════════════════════════════════════════════╝

Run:
    python main.py                          # starts on 0.0.0.0:8000
    uvicorn main:app --reload --port 8000   # dev mode with hot-reload

Endpoints:
    POST   /api/sync      →  Accept batch of distress packets from Android nodes
    GET    /api/packets    →  Retrieve all received packets (debug/dashboard)
    WS     /ws/live        →  Real-time broadcast to connected UI dashboards

Test with curl:
    curl -X POST http://localhost:8000/api/sync \
      -H "Content-Type: application/json" \
      -d '[{"id":"pkt-001","timestamp":1713700000,"loc":"12.9716,77.5946","msg":"SOS!","ttl":3}]'
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ═════════════════════════════════════════════════════════════════════
#  LOGGING
# ═════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("echonet-backend")


# ═════════════════════════════════════════════════════════════════════
#  PYDANTIC MODELS
# ═════════════════════════════════════════════════════════════════════

class DistressPacket(BaseModel):
    """
    Schema for a single distress packet synced from an Android node.
    Matches the FSK-decoded JSON payload structure.
    """
    id: str = Field(..., description="Unique packet ID (UUID or short hash)")
    timestamp: int = Field(..., description="Unix epoch seconds when the SOS was created")
    loc: str = Field(..., description="GPS coordinates as 'lat,lng' string")
    msg: str = Field(..., description="Decoded distress message (e.g. 'SOS!', 'FIRE')")
    ttl: int = Field(..., description="Time-to-live hop counter for mesh relay")


class SyncResponse(BaseModel):
    """Response returned after a successful batch sync."""
    accepted: int = Field(..., description="Number of new packets accepted")
    duplicates: int = Field(..., description="Number of duplicate packets skipped")
    total_stored: int = Field(..., description="Total packets in server memory")


# ═════════════════════════════════════════════════════════════════════
#  IN-MEMORY STORES  (hackathon speed — no DB required)
# ═════════════════════════════════════════════════════════════════════

# Deduplication: set of packet IDs we've already seen
seen_packet_ids: set[str] = set()

# Full packet store (ordered by arrival time)
packet_store: list[dict[str, Any]] = []


# ═════════════════════════════════════════════════════════════════════
#  WEBSOCKET CONNECTION MANAGER
# ═════════════════════════════════════════════════════════════════════

class ConnectionManager:
    """
    Manages all active WebSocket connections from dashboard UI clients.
    Thread-safe via asyncio (single event loop).
    """

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)
        log.info(f"🔗 Dashboard connected  ({len(self._connections)} total)")

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.remove(ws)
        log.info(f"🔌 Dashboard disconnected  ({len(self._connections)} total)")

    @property
    def count(self) -> int:
        return len(self._connections)

    async def broadcast(self, data: dict[str, Any]) -> None:
        """
        Push a JSON payload to ALL connected WebSocket clients.
        Silently drops connections that have gone stale.
        """
        if not self._connections:
            return

        payload = json.dumps(data)
        stale: list[WebSocket] = []

        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                stale.append(ws)

        # Clean up dead connections
        for ws in stale:
            self._connections.remove(ws)
            log.warning(f"🗑️  Removed stale connection ({len(self._connections)} remaining)")

    async def broadcast_batch(self, packets: list[dict[str, Any]]) -> None:
        """
        Broadcast multiple packets individually to all clients.
        Each packet is sent as a separate WebSocket message so the
        dashboard can animate them arriving one-by-one.
        """
        for pkt in packets:
            await self.broadcast({
                "event": "new_packet",
                "packet": pkt,
            })


manager = ConnectionManager()


# ═════════════════════════════════════════════════════════════════════
#  FASTAPI APP
# ═════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="EchoNet-Triage Sync Backend",
    description="Phase 4 — REST intake + WebSocket broadcast for crisis mesh network",
    version="0.4.0",
)

# ── CORS: allow everything for rapid hackathon testing ───────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═════════════════════════════════════════════════════════════════════
#  STARTUP / SHUTDOWN EVENTS
# ═════════════════════════════════════════════════════════════════════

@app.on_event("startup")
async def on_startup() -> None:
    log.info("╔══════════════════════════════════════════════════════════╗")
    log.info("║       ECHONET-TRIAGE · SYNC BACKEND · v0.4.0           ║")
    log.info("║       REST intake  →  WebSocket broadcast              ║")
    log.info("╚══════════════════════════════════════════════════════════╝")
    log.info("📡 POST /api/sync      — Mobile node packet upload")
    log.info("📋 GET  /api/packets   — Retrieve all stored packets")
    log.info("🔴 WS   /ws/live       — Dashboard real-time feed")


# ═════════════════════════════════════════════════════════════════════
#  REST ENDPOINTS
# ═════════════════════════════════════════════════════════════════════

@app.post("/api/sync", response_model=SyncResponse)
async def sync_packets(packets: list[DistressPacket]) -> SyncResponse:
    """
    Accept a batch of distress packets from an Android node.

    Deduplicates by packet ID, stores new packets in memory,
    and immediately broadcasts each new packet to all connected
    WebSocket dashboard clients.

    This is the core bridge: REST in → WebSocket out.
    """
    new_packets: list[dict[str, Any]] = []
    duplicates = 0

    for pkt in packets:
        if pkt.id in seen_packet_ids:
            duplicates += 1
            log.debug(f"   ⏭️  Duplicate skipped: {pkt.id}")
            continue

        # Mark as seen
        seen_packet_ids.add(pkt.id)

        # Enrich with server-side metadata
        pkt_dict = pkt.model_dump()
        pkt_dict["received_at"] = datetime.now(timezone.utc).isoformat()

        # Store
        packet_store.append(pkt_dict)
        new_packets.append(pkt_dict)

        log.info(f"   📦 Accepted: {pkt.id}  msg=\"{pkt.msg}\"  loc={pkt.loc}")

    # ── Bridge: push new packets out to all dashboards ───────────
    if new_packets:
        await manager.broadcast_batch(new_packets)
        log.info(
            f"   📡 Broadcast {len(new_packets)} packet(s) "
            f"→ {manager.count} dashboard(s)"
        )

    return SyncResponse(
        accepted=len(new_packets),
        duplicates=duplicates,
        total_stored=len(packet_store),
    )


@app.get("/api/packets")
async def get_packets() -> dict[str, Any]:
    """
    Return all stored packets (for dashboard initial load or debug).
    """
    return {
        "count": len(packet_store),
        "packets": packet_store,
    }


@app.get("/api/status")
async def get_status() -> dict[str, Any]:
    """
    Health check + stats endpoint.
    """
    return {
        "status": "online",
        "version": "0.4.0",
        "packets_stored": len(packet_store),
        "unique_ids": len(seen_packet_ids),
        "dashboards_connected": manager.count,
    }


# ═════════════════════════════════════════════════════════════════════
#  WEBSOCKET ENDPOINT
# ═════════════════════════════════════════════════════════════════════

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    """
    Real-time feed for dashboard UI clients.

    On connect:
        1. Accepts the WebSocket connection
        2. Sends a welcome message with current stats
        3. Sends all existing packets as a backfill

    While connected:
        - Receives new_packet events whenever POST /api/sync delivers data
        - Keeps alive via ping/pong (handled by the ASGI server)

    The client can also send messages (e.g., acknowledgements),
    which we log but don't currently act on.
    """
    await manager.connect(websocket)

    try:
        # ── Send welcome + backfill ──────────────────────────────
        await websocket.send_text(json.dumps({
            "event": "connected",
            "message": "EchoNet-Triage live feed active",
            "packets_stored": len(packet_store),
            "dashboards_connected": manager.count,
        }))

        # Backfill: send all existing packets so the dashboard
        # can render the current state immediately
        if packet_store:
            await websocket.send_text(json.dumps({
                "event": "backfill",
                "packets": packet_store,
            }))
            log.info(f"   📋 Sent {len(packet_store)} backfill packets to new dashboard")

        # ── Keep connection alive — listen for client messages ───
        while True:
            data = await websocket.receive_text()
            log.debug(f"   💬 Dashboard says: {data}")

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        log.error(f"   ❌ WebSocket error: {e}")
        manager.disconnect(websocket)


# ═════════════════════════════════════════════════════════════════════
#  ENTRYPOINT
# ═════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
