#!/usr/bin/env python3
"""
scripts/mock_upstream.py
Zero-dependency mock upstream HTTP server using Python 3 standard library.
Listens on port 9099 (or MOCK_PORT env var).
"""

import os
import sys
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

PORT = int(os.environ.get("MOCK_PORT", 9099))

class MockHandler(BaseHTTPRequestHandler):
    def handle(self):
        try:
            super().handle()
        except Exception:
            pass

    def do_GET(self):
        body = b'{"status":"ok","speed":"c"}'
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            self.wfile.write(body)
        except Exception:
            pass

    def do_POST(self):
        try:
            content_len = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_len) if content_len > 0 else b""
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(post_data)))
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            self.wfile.write(post_data)
        except Exception:
            pass

    def log_message(self, format, *args):
        pass

class MockServer(ThreadingHTTPServer):
    request_queue_size = 512
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        pass

def main():
    server = MockServer(("127.0.0.1", PORT), MockHandler)
    print(f"Mock upstream server running on http://127.0.0.1:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping mock server...")
    finally:
        server.server_close()

if __name__ == "__main__":
    main()

