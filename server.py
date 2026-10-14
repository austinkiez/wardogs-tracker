"""
WARDOGS Local Server & Live Scraper Daemon
=========================================
Runs a lightweight HTTP server that serves the WARDOGS News Tracker dashboard,
exposes API endpoints for manual/automated rescrapes, and runs a background
polling loop to keep news synchronized.
"""

import http.server
import socketserver
import threading
import time
import json
from pathlib import Path
from scraper import run_scraper_cycle, OUTPUT_JSON_PATH

PORT = 8080
DIRECTORY = Path(__file__).parent

class WardogsHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIRECTORY), **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        if self.path == "/" or self.path == "":
            self.path = "/wardogs_news_tracker.html"
        elif self.path == "/api/news":
            if OUTPUT_JSON_PATH.exists():
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                with open(OUTPUT_JSON_PATH, "rb") as f:
                    self.wfile.write(f.read())
                return
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'{"error": "News data not initialized"}')
                return
        return super().do_GET()

    def do_POST(self):
        if self.path == "/api/scrape":
            print("[SERVER] Received manual resync request. Triggering scraper...")
            result = run_scraper_cycle()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "success",
                "message": "Scraper completed successfully",
                "total_posts": result["metadata"]["total_posts"],
                "last_updated": result["metadata"]["last_updated"]
            }).encode("utf-8"))
            return
        
        self.send_response(404)
        self.end_headers()

def background_scraper_daemon(interval_seconds=300):
    while True:
        try:
            time.sleep(interval_seconds)
            print(f"[DAEMON] Running scheduled scrape cycle ({interval_seconds}s interval)...")
            run_scraper_cycle()
        except Exception as e:
            print(f"[DAEMON] Background scrape encountered an error: {e}")

if __name__ == "__main__":
    run_scraper_cycle()
    t = threading.Thread(target=background_scraper_daemon, args=(300,), daemon=True)
    t.start()
    print(f"WARDOGS Tracker Server starting on port {PORT}...")
    with socketserver.TCPServer(("", PORT), WardogsHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down WARDOGS Tracker server.")
