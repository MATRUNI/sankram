#!/usr/bin/env python3
"""
Sankram Proxy - Fallback & Overflow Circuit-Breaker Test Suite
Standard Library Only (Zero external pip packages).
Migrated from test_fallback.js.
"""

import os
import sys
import time
import signal
import socket
import subprocess
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

MOCK_PORT = 9099
PROXY_PORT = 17777
LOGS_DIR = os.path.abspath("logs")
CONFIG_PATH = os.path.abspath("proxy.conf")
CONCURRENCY = 25

class MockHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'{"status":"ok","proxy":"c"}'
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

class MockServer(ThreadingHTTPServer):
    request_queue_size = 512
    daemon_threads = True
    allow_reuse_address = True

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

QUERY_PAD = "f" * 400
RAW_REQ = (
    f"GET /?url=http://127.0.0.1:{MOCK_PORT}/bench?q={QUERY_PAD} HTTP/1.1\r\n"
    f"Host: 127.0.0.1:{PROXY_PORT}\r\n"
    f"User-Agent: Sankram-Fallback-Harness/1.0\r\n"
    f"Connection: close\r\n\r\n"
).encode("utf-8")

stop_event = threading.Event()
requests_counter = [0]
success_counter = [0]
failed_counter = [0]
counter_lock = threading.Lock()
first_failures = []

def worker_loop():
    while not stop_event.is_set():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2.0)
            s.connect(("127.0.0.1", PROXY_PORT))
            s.sendall(RAW_REQ)
            resp = s.recv(512)
            s.close()
            ok = (b"200 OK" in resp or b"status" in resp)
            with counter_lock:
                requests_counter[0] += 1
                if ok:
                    success_counter[0] += 1
                else:
                    failed_counter[0] += 1
                    if len(first_failures) < 10:
                        first_failures.append(f"resp: {resp!r}")
        except Exception as e:
            with counter_lock:
                requests_counter[0] += 1
                failed_counter[0] += 1
                if len(first_failures) < 10:
                    first_failures.append(f"exception: {type(e).__name__} {e}")

def main():
    print("=" * 64)
    print("         FALLBACK & OVERFLOW CIRCUIT-BREAKER TEST              ")
    print("=" * 64)

    # 1. Start Multi-Threaded Mock Server
    mock_server = MockServer(("127.0.0.1", MOCK_PORT), MockHandler)
    server_thread = threading.Thread(target=mock_server.serve_forever, daemon=True)
    server_thread.start()

    initial_status = get_logs_status()
    print(f"Current Active File : {initial_status['active_file']}")
    print("Files currently in logs/:")
    for f in initial_status["files"]:
        status_tag = "(ACTIVE)" if f["active"] else ""
        print(f"  - {f['name']:<20} : {f['size'] / 1024.0:.1f} KB {status_tag}")

    # 2. Configure 50KB rotation threshold and start Proxy
    with open(CONFIG_PATH, "w") as f:
        f.write("max_log_size = 50KB\n")

    bin_path = "./build/sankram.exe" if sys.platform == "win32" else "./build/sankram"
    if not os.path.exists(bin_path):
        bin_path = "./build/api"

    print(f"\nStarting Proxy Server ({bin_path} -p {PROXY_PORT})...")
    proxy = subprocess.Popen([bin_path, "-p", str(PROXY_PORT), "-l", "info"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)

    stderr_alert_detected = [False]
    def read_stderr():
        for line in proxy.stderr:
            if "Operating in overflow mode" in line or "Failed to rotate" in line:
                stderr_alert_detected[0] = True
                sys.stdout.write(f"\n[ALERT DETECTED ON STDERR] {line}")
                sys.stdout.flush()
    threading.Thread(target=read_stderr, daemon=True).start()

    try:
        ready = wait_for_proxy(PROXY_PORT)
        if not ready:
            print("❌ Failed to connect to proxy on port 17777")
            return 1

        post_start = get_logs_status()
        current_active = post_start["active_file"]
        print(f"Active Log File after startup: {current_active}\n")

        # 3. Sabotage rotation by setting chmod 555 on logs/ directory
        print("[SIMULATION] Setting chmod 555 on logs/ directory to simulate rotation failure...")
        os.chmod(LOGS_DIR, 0o555)

        print(f"Firing continuous parallel requests to push {current_active} past 50 KB limit into overflow mode...")
        stop_event.clear()
        requests_counter[0] = 0
        success_counter[0] = 0
        failed_counter[0] = 0
        crossed_threshold = False

        workers = [threading.Thread(target=worker_loop, daemon=True) for _ in range(CONCURRENCY)]
        for w in workers:
            w.start()

        while not stop_event.is_set():
            time.sleep(0.05)
            with counter_lock:
                reqs = requests_counter[0]
            try:
                active_path = os.path.join(LOGS_DIR, current_active)
                size = os.path.getsize(active_path)
                size_kb = size / 1024.0
                sys.stdout.write(f"\rSent: {reqs} reqs | Active File ({current_active}): {size_kb:.1f} KB / 50.0 KB")
                sys.stdout.flush()

                if size > 50 * 1024:
                    crossed_threshold = True
                    if stderr_alert_detected[0]:
                        print(f"\n\n✔ Verified: {current_active} crossed 50 KB, rotation failed safely, and proxy entered overflow mode!")
                        stop_event.set()
                        break
            except Exception:
                pass
            if reqs > 30000:
                stop_event.set()
                break

        stop_event.set()
        for w in workers:
            w.join(timeout=1.0)

        # Restore permissions immediately
        os.chmod(LOGS_DIR, 0o775)
        print("\nRestored chmod 775 on logs/ directory.")

        time.sleep(0.6)
        print("Shutting down proxy gracefully...")
        proxy.send_signal(signal.SIGINT if sys.platform != "win32" else signal.SIGTERM)
        proxy.wait(timeout=5)

        # 4. Final Audit
        with counter_lock:
            requests_completed = requests_counter[0]
            success_count = success_counter[0]
            fail_count = failed_counter[0]

        final_status = get_logs_status()
        print("\n===============================================================")
        print("                 FALLBACK AUDIT RESULTS                        ")
        print("===============================================================")
        for f in final_status["files"]:
            tag = "⭐ ACTIVE" if f["active"] else "  ARCHIVED"
            print(f"  - {f['name']:<20} : {f['size'] / 1024.0:.1f} KB {tag}")

        active_obj = next((f for f in final_status["files"] if f["name"] == current_active), None)
        final_size = active_obj["size"] if active_obj else 0

        print("---------------------------------------------------------------")
        print(f"Total Requests Sent    : {requests_completed}")
        print(f"Successful Requests    : {success_count}")
        print(f"Failed Requests        : {fail_count}")
        print(f"Active File Maintained : {current_active}")
        print(f"Final File Size        : {final_size / 1024.0:.1f} KB (> 50.0 KB)")
        print(f"Stderr Alert Triggered : {'YES' if stderr_alert_detected[0] else 'NO'}")
        if first_failures:
            print("First Failures Sample:")
            for f in first_failures:
                print(f"  - {f}")

        if crossed_threshold and stderr_alert_detected[0] and fail_count == 0 and final_status["active_file"] == current_active:
            print("\n✅ PASS: Fallback succeeded! The proxy refused to drop logs, alerted operator,")
            print("         and safely operated in overflow mode without crashing or losing requests!")
            print("===============================================================\n")
            return 0
        else:
            print("\n❌ Fallback test check failed.")
            print("===============================================================\n")
            return 1

    except Exception as e:
        print(f"\n❌ Error during fallback test: {e}")
        return 1
    finally:
        try:
            os.chmod(LOGS_DIR, 0o775)
        except Exception:
            pass
        if os.path.exists(CONFIG_PATH):
            try:
                os.remove(CONFIG_PATH)
            except Exception:
                pass
        if proxy.poll() is None:
            proxy.kill()
        try:
            mock_server.shutdown()
            mock_server.server_close()
        except Exception:
            pass

if __name__ == "__main__":
    sys.exit(main())
