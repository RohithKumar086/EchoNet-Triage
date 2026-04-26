import time
import json
import random
import uuid
import requests
from datetime import datetime, timezone

# ═════════════════════════════════════════════════════════════════════
#  CONFIG
# ═════════════════════════════════════════════════════════════════════

API_URL = "http://localhost:8000/api/sync"
NUM_PACKETS = 25
DELAY_BETWEEN_REQUESTS = 0.5  # seconds (for the staggered "pop-pop" effect)

# Center point for the map cluster (Bengaluru, India)
CENTER_LAT = 12.9716
CENTER_LNG = 77.5946
RADIUS_OFFSET = 0.02  # Roughly 1-2 km scatter radius

MESSAGES = [
    "SOS!",
    "FIRE",
    "MEDIC",
    "TRAPPED",
    "WATER NEEDED",
    "ROAD BLOCKED",
    "SAFE HERE"
]

print("╔══════════════════════════════════════════════════════════╗")
print("║         ECHONET-TRIAGE · CHAOS LOAD TESTER             ║")
print("╚══════════════════════════════════════════════════════════╝")
print(f"📡 Target: {API_URL}")
print(f"📦 Generating {NUM_PACKETS} distress packets...")
print()

# ═════════════════════════════════════════════════════════════════════
#  GENERATION & INJECTION
# ═════════════════════════════════════════════════════════════════════

for i in range(NUM_PACKETS):
    # Generate random jitter around the center point
    lat = CENTER_LAT + random.uniform(-RADIUS_OFFSET, RADIUS_OFFSET)
    lng = CENTER_LNG + random.uniform(-RADIUS_OFFSET, RADIUS_OFFSET)
    
    # Construct the JSON packet matching the FSK/FastAPI schema
    packet = {
        "id": f"pkt-{str(uuid.uuid4())[:8]}",
        "timestamp": int(datetime.now(timezone.utc).timestamp()),
        "loc": f"{lat:.6f},{lng:.6f}",
        "msg": random.choice(MESSAGES),
        "ttl": random.randint(1, 5)
    }

    # The backend accepts a list of packets per POST request.
    # We send them one by one to simulate the staggered effect.
    payload = [packet]

    try:
        response = requests.post(API_URL, json=payload)
        
        if response.status_code == 200:
            print(f"[{i+1:02d}/{NUM_PACKETS}] 🟢 Injected: {packet['id']} | {packet['msg']} @ {packet['loc']}")
        else:
            print(f"[{i+1:02d}/{NUM_PACKETS}] 🔴 Failed: HTTP {response.status_code} - {response.text}")
            
    except requests.exceptions.ConnectionError:
        print(f"🔴 Connection Refused. Is the backend running on {API_URL}?")
        break

    # Staggered visual effect
    time.sleep(DELAY_BETWEEN_REQUESTS)

print("\n✅ Chaos load test complete.")
