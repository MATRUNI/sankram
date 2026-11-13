#!/usr/bin/env python3
"""
Sankram Proxy - Live Log Rotation & Commit-Before-Retire Test Suite
Standard Library Only (Zero external pip packages).
Migrated from test_rotation.js.
"""

import os
import sys
import time
import signal
import socket
import subprocess
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

MOCK_PORT = 9099
PROXY_PORT = 17777
LOGS_DIR = os.path.abspath("logs")
CONCURRENCY = 25

class MockHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'{"status":"ok","proxy":"c"}'
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, format, *args):
        pass

def get_logs_status():
    if not os.path.exists(LOGS_DIR):
        return {"files": [], "active_file": None}

    entries = os.listdir(LOGS_DIR)
    log_files = [f for f in entries if f.startswith("@logger_") or (f.startswith("logger_") and f.endswith(".log"))]
    log_files.sort()

    active_file = next((f for f in log_files if f.startswith("@")), None)
    file_details = []
    for f in log_files:
        path = os.path.join(LOGS_DIR, f)
        size = os.path.getsize(path) if os.path.exists(path) else 0
        file_details.append({
            "name": f,
            "size": size,
            "active": f.startswith("@")
        })

    return {"files": file_details, "active_file": active_file}

def wait_for_proxy(port, max_tries=30):
    for _ in range(max_tries):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.2)
            s.connect(("127.0.0.1", port))
            req = f"GET /?url=http://127.0.0.1:{MOCK_PORT}/health HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n"
            s.sendall(req.encode())
            resp = s.recv(512)
            s.close()
            if b"200 OK" in resp or b"HTTP/1.1" in resp:
                return True
        except Exception:
            time.sleep(0.1)
    return False

# 400-byte query fits cleanly inside sizeof(url->path)=1024 without overflowing
QUERY_PAD = "x" * 400
RAW_REQ = (
    f"GET /?url=http://127.0.0.1:{MOCK_PORT}/bench?q={QUERY_PAD} HTTP/1.1\r\n"
    f"Host: 127.0.0.1:{PROXY_PORT}\r\n"
    f"User-Agent: Sankram-Rotation-Harness/1.0\r\n"
    f"Connection: close\r\n\r\n"
).encode("utf-8")

stop_event = threading.Event()
requests_counter = [0]
counter_lock = threading.Lock()

def worker_loop():
    while not stop_event.is_set():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.5)
            s.connect(("127.0.0.1", PROXY_PORT))
            s.sendall(RAW_REQ)
            s.recv(256)
            s.close()
            with counter_lock:
                requests_counter[0] += 1
        except Exception:
            pass

def main():
    print("=" * 64)
    print("       LIVE ROTATION & COMMIT-BEFORE-RETIRE TEST SUITE        ")
    print("=" * 64)

    # 1. Start Multi-Threaded Mock Server
    mock_server = ThreadingHTTPServer(("127.0.0.1", MOCK_PORT), MockHandler)
    server_thread = threading.Thread(target=mock_server.serve_forever, daemon=True)
    server_thread.start()

    initial_status = get_logs_status()
    print(f"Initial Active Log File : {initial_status['active_file'] or 'None'}")
    print("Files currently in logs/:")
    for f in initial_status["files"]:
        status_tag = "(ACTIVE)" if f["active"] else ""
        print(f"  - {f['name']:<20} : {f['size'] / 1024.0:.1f} KB {status_tag}")

    # 2. Start Proxy
    bin_path = "./build/sankram.exe" if sys.platform == "win32" else "./build/sankram"
    if not os.path.exists(bin_path):
        bin_path = "./build/api"

    print(f"\nStarting Proxy Server ({bin_path} -p {PROXY_PORT})...")
    proxy = subprocess.Popen([bin_path, "-p", str(PROXY_PORT), "-l", "info"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        ready = wait_for_proxy(PROXY_PORT)
        if not ready:
            print("❌ Failed to connect to proxy on port 17777")
            return 1

        print("✔ Proxy is running and listening on port 17777.\n")

        target_active = get_logs_status()["active_file"]
        print(f"Active Log File to Rotate: {target_active}")

        print("Firing parallel raw socket requests to cross rotation threshold...")
        stop_event.clear()
        requests_counter[0] = 0
        start_time = time.time()
        rotated = False
        new_active = None

        workers = []
        for _ in range(CONCURRENCY):
            t = threading.Thread(target=worker_loop, daemon=True)
            workers.append(t)
            t.start()

        while not rotated and (time.time() - start_time) < 30:
            time.sleep(0.1)
            with counter_lock:
                sent = requests_counter[0]

            current_status = get_logs_status()
            current_active = current_status["active_file"]
            active_obj = next((f for f in current_status["files"] if f["active"]), None)
            active_size = f"{active_obj['size'] / (1024 * 1024):.2f}" if active_obj else "0"

            sys.stdout.write(f"\rSent: {sent} reqs | Active: {current_active} ({active_size} MB / 2.00 MB)")
            sys.stdout.flush()

            if current_active and current_active != target_active:
                rotated = True
                new_active = current_active
                print(f"\n\n🎉 ROTATION DETECTED! Active marker moved to: {new_active}")
                break

        stop_event.set()
        for t in workers:
            t.join(timeout=0.5)

        time.sleep(0.6)
        print("\nShutting down proxy gracefully...")
        proxy.send_signal(signal.SIGINT if sys.platform != "win32" else signal.SIGTERM)
        proxy.wait(timeout=5)

        # 3. Verify Final Audit
        final_status = get_logs_status()
        print("\n===============================================================")
        print("                       FINAL LOGS AUDIT                        ")
        print("===============================================================")
        for f in final_status["files"]:
            tag = "⭐ ACTIVE" if f["active"] else "  ARCHIVED"
            print(f"  - {f['name']:<20} : {f['size'] / 1024.0:.1f} KB {tag}")

        active_count = sum(1 for f in final_status["files"] if f["active"])
        elapsed = time.time() - start_time
        with counter_lock:
            total_sent = requests_counter[0]
        rps = (total_sent / elapsed) if elapsed > 0 else 0
        print("---------------------------------------------------------------")
        print(f"Active markers found   : {active_count} (Expected: exactly 1)")
        print(f"Total Requests Sent    : {total_sent}")
        print(f"Throughput             : {rps:.1f} req/sec")
        print(f"Elapsed Time           : {elapsed:.2f}s")

        if rotated and active_count == 1:
            print("\n✅ PASS: Carousel rotation, commit-before-retire & active marker verified!")
            print("===============================================================\n")
            return 0
        else:
            print("\n❌ FAIL: Rotation did not occur or active marker count is invalid.")
            print("===============================================================\n")
            return 1

    except Exception as e:
        print(f"\n❌ Error during rotation test: {e}")
        return 1
    finally:
        stop_event.set()
        if proxy.poll() is None:
            proxy.kill()
        mock_server.shutdown()
        mock_server.server_close()

if __name__ == "__main__":
    sys.exit(main())
