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
    def do_GET(self):
        body = b'{"status":"ok","speed":"c"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_len) if content_len > 0 else b""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(post_data)))
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        self.wfile.write(post_data)

    def log_message(self, format, *args):
        pass

def main():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), MockHandler)
    print(f"Mock upstream server running on http://127.0.0.1:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping mock server...")
    finally:
        server.server_close()

if __name__ == "__main__":
    main()

