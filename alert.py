#!/usr/bin/env python3
"""
Facebook Marketplace alert bot (via ScrapeAtlas) -> Discord webhook.
Run:  python marketplace_alerts.py      (Python 3.8+, no extra packages)
"""

# ╔══════════════════════════════════════════════════════════════════════╗
# ║                     ✏️  EDIT THESE SETTINGS  ✏️                       ║
# ╚══════════════════════════════════════════════════════════════════════╝

ITEM       = ""      # what you want to find
MIN_PRICE  = None             # e.g. 5000   (None = no minimum)
MAX_PRICE  = 15000          # e.g. 15000  (None = no maximum)

# Any city/town/province names. Add or remove freely.
PLACES     = [""]
RADIUS_KM  = 20               # search radius around EACH place (max 500)

CHECK_EVERY_SECONDS = 300     # how often to check (each check = 1 credit per place)

WEBHOOK_URL = ""
API_KEY     = ""              # your ScrapeAtlas key (or set env var SCRAPEATLAS_API_KEY)

ALERT_ON_EXISTING = False     # True = also alert on listings already live at first run

# ──────────────────────────────────────────────────────────────────────
# Below this line you normally don't need to change anything.
# ──────────────────────────────────────────────────────────────────────
import json
import os
import sys
import time
import urllib.error
import urllib.request

MCP_URL     = os.environ.get("SCRAPEATLAS_MCP_URL", "https://api.scrapeatlas.com/mcp")
AUTH_HEADER = os.environ.get("SCRAPEATLAS_AUTH_HEADER", "Authorization")
AUTH_PREFIX = os.environ.get("SCRAPEATLAS_AUTH_PREFIX", "Bearer ")
STATE_FILE  = "marketplace_state.json"
PLACES_FILE = "places_cache.json"


class MCPClient:
    def __init__(self, url, api_key):
        self.url, self.api_key, self.session_id, self._id = url, api_key, None, 0

    def _post(self, payload, expect_response=True):
        headers = {"Content-Type": "application/json",
                   "Accept": "application/json, text/event-stream",
                   AUTH_HEADER: AUTH_PREFIX + self.api_key}
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        req = urllib.request.Request(self.url, data=json.dumps(payload).encode(),
                                     headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=120) as resp:
            self.session_id = resp.headers.get("Mcp-Session-Id") or self.session_id
            raw = resp.read().decode("utf-8", "replace")
            ctype = resp.headers.get("Content-Type", "")
        if not expect_response or not raw.strip():
            return None
        if "text/event-stream" in ctype:
            for line in raw.splitlines():
                if line.startswith("data:") and line[5:].strip():
                    msg = json.loads(line[5:].strip())
                    if "result" in msg or "error" in msg:
                        return msg
            return None
        return json.loads(raw)

    def _rpc(self, method, params=None):
        self._id += 1
        msg = {"jsonrpc": "2.0", "id": self._id, "method": method}
        if params is not None:
            msg["params"] = params
        out = self._post(msg)
        if out and "error" in out:
            raise RuntimeError(f"MCP error: {out['error']}")
        return (out or {}).get("result")

    def start(self):
        self._rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                 "clientInfo": {"name": "marketplace-alerts", "version": "2.0"}})
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"}, expect_response=False)

    def call_tool(self, name, arguments):
        result = self._rpc("tools/call", {"name": name, "arguments": arguments})
        for block in (result or {}).get("content", []):
            if block.get("type") == "text":
                try:
                    return json.loads(block["text"])
                except json.JSONDecodeError:
                    return {"raw": block["text"]}
        return {}


def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f)


def resolve_places(client):
    """Turn place names into coordinates (cached, so each name costs 1 credit once)."""
    cache = load_json(PLACES_FILE, {})
    resolved = {}
    for name in PLACES:
        key = name.strip().lower()
        if key not in cache:
            data = client.call_tool("facebookMarketplaceLocationSearch", {"query": name})
            body = data.get("body", data)
            locs = body.get("locations") or (body.get("data") or {}).get("items") or []
            if not locs:
                print(f"⚠️  Couldn't find a location for '{name}' — skipping.")
                continue
            top = locs[0]
            cache[key] = {"label": top["name"], "lat": top["latitude"], "lng": top["longitude"]}
            save_json(PLACES_FILE, cache)
        resolved[name] = cache[key]
        print(f"📍 {name} → {cache[key]['label']} ({cache[key]['lat']}, {cache[key]['lng']})")
    if not resolved:
        sys.exit("No valid places to search.")
    return resolved


def search(client, place):
    args = {"query": ITEM, "lat": str(place["lat"]), "lng": str(place["lng"]),
            "radius_km": str(RADIUS_KM), "sort_by": "creation_time_descend",
            "availability": "available", "count": "24"}
    if MIN_PRICE is not None:
        args["min_price"] = str(MIN_PRICE)
    if MAX_PRICE is not None:
        args["max_price"] = str(MAX_PRICE)
    data = client.call_tool("facebookMarketplaceSearch", args)
    body = data.get("body", data)
    if body.get("status") not in (None, "success", "partial"):
        raise RuntimeError(f"Search failed: {body.get('failure') or body}")
    return body.get("listings") or (body.get("data") or {}).get("items") or []


def price_ok(listing):
    try:
        amount = float((listing.get("price") or {}).get("amount"))
    except (TypeError, ValueError):
        return True
    return not ((MIN_PRICE is not None and amount < MIN_PRICE) or
                (MAX_PRICE is not None and amount > MAX_PRICE))


def send_discord(listing, place_name):
    price = (listing.get("price") or {}).get("formatted_amount", "n/a")
    loc = (listing.get("location") or {}).get("display_name", "")
    title = listing.get("title", "(no title)").replace("\n", " ")[:200]
    embed = {"title": f"{title} — {price}", "url": listing.get("url"),
             "description": f"📍 {loc}\n🔎 Search: **{ITEM}** near **{place_name}**",
             "color": 0x1877F2}
    photo = (listing.get("primary_photo") or {}).get("url")
    if photo:
        embed["thumbnail"] = {"url": photo}
    payload = {"content": "🛒 **New Marketplace listing**", "embeds": [embed]}
    req = urllib.request.Request(WEBHOOK_URL, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "marketplace-alerts/2.0"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status


def poll(client, places, state):
    seen, baselined = set(state["seen"]), set(state["baselined"])
    alerted_this_poll = set()
    for name, place in places.items():
        key = f"{ITEM}|{name}|{MIN_PRICE}|{MAX_PRICE}|{RADIUS_KM}".lower()
        try:
            listings = search(client, place)
        except urllib.error.HTTPError as e:
            if e.code == 402:
                sys.exit("ScrapeAtlas: out of credits (HTTP 402).")
            print(f"[{name}] HTTP error {e.code}")
            continue
        except Exception as e:
            print(f"[{name}] error: {e}")
            continue

        first_time = key not in baselined
        baselined.add(key)
        fresh = [l for l in listings if l.get("id") and l["id"] not in seen
                 and l["id"] not in alerted_this_poll and price_ok(l)]
        if first_time and not ALERT_ON_EXISTING:
            print(f"[{name}] baseline saved ({len(listings)} current listings).")
            seen.update(l["id"] for l in listings if l.get("id"))
            continue

        failed = set()
        for l in reversed(fresh):  # oldest first
            try:
                send_discord(l, name)
                alerted_this_poll.add(l["id"])
                print(f"[{name}] alerted: {l.get('title')} — {(l.get('price') or {}).get('formatted_amount')}")
                time.sleep(1)  # be gentle with Discord rate limits
            except urllib.error.URLError as e:
                print(f"[{name}] webhook failed ({e}); will retry next poll.")
                failed.add(l["id"])
        seen.update(l["id"] for l in listings if l.get("id") and l["id"] not in failed)
        if not fresh:
            print(f"[{name}] nothing new.")

    state["seen"], state["baselined"] = sorted(seen)[-5000:], sorted(baselined)
    save_json(STATE_FILE, state)


def main():
    api_key = API_KEY or os.environ.get("SCRAPEATLAS_API_KEY")
    if not api_key:
        sys.exit("Put your ScrapeAtlas key in API_KEY at the top of the file.")
    client = MCPClient(MCP_URL, api_key)
    client.start()
    places = resolve_places(client)
    state = load_json(STATE_FILE, {"seen": [], "baselined": []})
    price_txt = f"{MIN_PRICE or 'any'} – {MAX_PRICE or 'any'}"
    print(f"\n👀 Watching '{ITEM}' | price {price_txt} | {', '.join(places)} | every {CHECK_EVERY_SECONDS}s\n")
    while True:
        poll(client, places, state)
        if "--once" in sys.argv:
            break
        time.sleep(CHECK_EVERY_SECONDS)


if __name__ == "__main__":
    main()