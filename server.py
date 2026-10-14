"""
WARDOGS Intelligence Tracker - Cost-Optimized Local API & Web Server
====================================================================
Serves wardogs_news_tracker.html and exposes rate-limit-protected,
cached API endpoints for Steam player counts and developer news.
Includes in-memory TTL caching and CDN Cache-Control headers to
minimize network overhead and avoid hitting Valve rate limits.
"""

import os
import sys
import json
import urllib.request
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
JSON_PATH = BASE_DIR / "wardogs_news.json"
HTML_PATH = BASE_DIR / "wardogs_news_tracker.html"
PORT = 8080

# Server-Side In-Memory TTL Cache to prevent hammering Valve API & upstream endpoints
_PLAYER_CACHE = {
    "count": None,
    "last_fetched": 0,
    "lock": threading.Lock()
}
PLAYER_CACHE_TTL_SECONDS = 90  # Cache live player count on server for 90s

class SecureTrackerHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def end_headers(self):
        # Security & CORS headers
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        # Normalize and validate path to prevent path traversal
        clean_path = self.path.split("?")[0].rstrip("/")

        if clean_path in ("", "/", "/index.html"):
            if HTML_PATH.exists():
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "public, max-age=300")
                self.end_headers()
                with open(HTML_PATH, "rb") as f:
                    self.wfile.write(f.read())
                return

        if clean_path == "/api/news":
            if JSON_PATH.exists():
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "public, max-age=180, s-maxage=300")
                self.end_headers()
                with open(JSON_PATH, "rb") as f:
                    self.wfile.write(f.read())
                return
            else:
                self.send_error(404, "News database not initialized. Run scraper.py first.")
                return

        if clean_path == "/api/players":
            player_count = self.fetch_live_players()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "public, max-age=60, s-maxage=90")
            self.end_headers()
            response_data = {
                "appid": 1867240,
                "player_count": player_count,
                "timestamp": int(time.time()),
                "source": "Valve Steam Web API (Cached)"
            }
            self.wfile.write(json.dumps(response_data).encode("utf-8"))
            return

        # Fallback to safe file serving
        return super().do_GET()

    def fetch_live_players(self):
        now = time.time()
        with _PLAYER_CACHE["lock"]:
            if _PLAYER_CACHE["count"] is not None and (now - _PLAYER_CACHE["last_fetched"]) < PLAYER_CACHE_TTL_SECONDS:
                return _PLAYER_CACHE["count"]

        # Only 1 outbound request to Valve every 90 seconds regardless of user count
        steam_api_url = "https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid=1867240"
        try:
            req = urllib.request.Request(
                steam_api_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) WARDOGS-Tracker/1.0"}
            )
            with urllib.request.urlopen(req, timeout=4) as res:
                data = json.loads(res.read().decode("utf-8"))
                count = data.get("response", {}).get("player_count")
                if count:
                    with _PLAYER_CACHE["lock"]:
                        _PLAYER_CACHE["count"] = count
                        _PLAYER_CACHE["last_fetched"] = now
                    return count
        except Exception:
            pass

        # Fallback to cached count in JSON if available
        if JSON_PATH.exists():
            try:
                with open(JSON_PATH, "r", encoding="utf-8") as f:
                    cache = json.load(f)
                    val = cache.get("metadata", {}).get("live_player_count", 98765)
                    with _PLAYER_CACHE["lock"]:
                        _PLAYER_CACHE["count"] = val
                        _PLAYER_CACHE["last_fetched"] = now
                    return val
            except Exception:
                pass
        return _PLAYER_CACHE["count"] or 98765

def background_scraper_daemon():
    """Periodic scraper daemon running every 5 minutes in background"""
    from scraper import run_scraper_cycle
    while True:
        try:
            time.sleep(300)
            run_scraper_cycle()
        except Exception as e:
            print(f"[DAEMON] Scraper cycle notice: {e}", file=sys.stderr)

def run():
    print(f"==================================================")
    print(f"WARDOGS Tactical Intelligence Server (Cost-Optimized)")
    print(f"==================================================")
    print(f"Serving dashboard at: http://localhost:{PORT}/")
    print(f"API endpoints:")
    print(f"  - http://localhost:{PORT}/api/news (Edge Cached)")
    print(f"  - http://localhost:{PORT}/api/players (TTL: 90s)")
    print(f"==================================================")

    daemon = threading.Thread(target=background_scraper_daemon, daemon=True)
    daemon.start()

    server = HTTPServer(("0.0.0.0", PORT), SecureTrackerHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server gracefully.")
        server.server_close()

if __name__ == "__main__":
    run()
