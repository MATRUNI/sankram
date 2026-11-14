#!/usr/bin/env python3
"""
scripts/local_benchmark.py

High-performance zero-latency local benchmark suite.
Standard Library Only (Zero external pip packages).
Migrated from local_benchmark.js.
"""

import os
import sys
import time
import socket
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor

MOCK_PORT = 9099
PROXY_PORT = 17777
TOTAL_REQUESTS = 20000
CONCURRENCY = 50

class MockHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'{"status":"ok","speed":"c"}'
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, format, *args):
        pass

def run_worker(requests_to_run, keep_alive):
    success = 0
    failed = 0
    req_bytes = (
        f"GET /?url=http://127.0.0.1:{MOCK_PORT}/bench HTTP/1.1\r\n"
        f"Host: 127.0.0.1:{PROXY_PORT}\r\n"
        f"Connection: {'keep-alive' if keep_alive else 'close'}\r\n\r\n"
    ).encode("utf-8")

    sock = None
    for _ in range(requests_to_run):
        try:
            if sock is None or not keep_alive:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2.0)
                sock.connect(("127.0.0.1", PROXY_PORT))
            sock.sendall(req_bytes)
            resp = sock.recv(512)
            if b"200 OK" in resp or b"status" in resp:
                success += 1
            else:
                failed += 1
            if not keep_alive:
                sock.close()
                sock = None
        except Exception:
            failed += 1
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass
                sock = None

    if sock:
        try:
            sock.close()
        except Exception:
            pass

    return success, failed

def main():
    use_keepalive = "--no-keepalive" not in sys.argv
    total_reqs = TOTAL_REQUESTS
    concurrency = CONCURRENCY

    # 1. Start zero-latency mock upstream server
    mock_server = ThreadingHTTPServer(("127.0.0.1", MOCK_PORT), MockHandler)
    server_thread = threading.Thread(target=mock_server.serve_forever, daemon=True)
    server_thread.start()

    print("\n===============================================================")
    print("        LOCAL HIGH-THROUGHPUT PROXY BENCHMARK                  ")
    print("===============================================================")
    print(f"Target Proxy   : http://127.0.0.1:{PROXY_PORT}")
    print(f"Mock Upstream  : http://127.0.0.1:{MOCK_PORT}")
    print(f"Total Requests : {total_reqs}")
    print(f"Concurrency    : {concurrency} workers ({'Keep-Alive' if use_keepalive else 'Short-Lived'})")
    print(f"Harness        : Python 3 Standard Library\n")

    reqs_per_worker = total_reqs // concurrency
    start_time = time.perf_counter()

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(run_worker, reqs_per_worker, use_keepalive) for _ in range(concurrency)]
        results = [f.result() for f in futures]

    total_duration = time.perf_counter() - start_time
    total_success = sum(r[0] for r in results)
    total_failed = sum(r[1] for r in results)
    rps = (total_success + total_failed) / total_duration if total_duration > 0 else 0

    print("---------------- RESULTS ----------------")
    print(f"Successful Requests : {total_success} / {total_reqs} ({((total_success / total_reqs) * 100):.1f}%)")
    print(f"Failed Requests     : {total_failed}")
    print(f"Total Time          : {total_duration:.2f} seconds")
    print(f"🔥 THROUGHPUT       : {rps:.1f} req/sec")
    print("===============================================================\n")

    mock_server.shutdown()
    mock_server.server_close()
    sys.exit(0 if total_failed == 0 else 1)

if __name__ == "__main__":
    main()

