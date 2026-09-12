# -*- coding: utf-8 -*-
import os
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from checker import run_check
import config

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/check':
            # Manual trigger via HTTP
            threading.Thread(target=run_check).start()
            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write('Check triggered successfully.'.encode('utf-8'))
        else:
            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write('Delta LMS Bot is Running 24/7.'.encode('utf-8'))

def background_loop():
    print("🚀 Background checker loop started...")
    while True:
        try:
            print("[Daemon] Running scheduled check...")
            run_check()
        except Exception as e:
            print(f"[Daemon] Error during check: {e}")
        
        sleep_sec = config.CHECK_INTERVAL_MINUTES * 60
        print(f"[Daemon] Sleeping for {config.CHECK_INTERVAL_MINUTES} minutes...")
        time.sleep(sleep_sec)

def start_server():
    port = int(os.environ.get('PORT', 8080))
    # Start background loop in a separate daemon thread
    t = threading.Thread(target=background_loop, daemon=True)
    t.start()

    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    print(f"🌍 Web server listening on port {port}...")
    server.serve_forever()

if __name__ == '__main__':
    start_server()
