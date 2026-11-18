#!/usr/bin/env python3
"""
Sankram Proxy - Automated Static File Serving & SPA Fallback Test Suite
Validates:
  1. Static file delivery with accurate MIME types (HTML, CSS, JS, JSON, SVG).
  2. Index file resolution (GET / -> index.html).
  3. Query string stripping (GET /file.css?v=1.0 -> file.css).
  4. Path traversal prevention & security sandboxing (GET /../../etc/passwd -> 403 Forbidden).
  5. SPA (Single Page Application) routing fallback (GET /dashboard -> index.html).
  6. Non-SPA mode fallback to API upstream (GET /api/data -> Upstream).
Standard Library Only (Zero external pip packages).
"""

import os
import sys
import time
import socket
import tempfile
import threading
import subprocess

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_GREEN = "\033[32m"
C_RED = "\033[31m"
C_YELLOW = "\033[33m"
C_CYAN = "\033[36m"

TEST_PORT = 17780
MOCK_UPSTREAM_PORT = 3000

def raw_http_request(host, port, path, method="GET", extra_headers=None):
    """Sends a raw HTTP request and returns (status_code, headers_dict, body_bytes)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5.0)
    s.connect((host, port))
    
    req = f"{method} {path} HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n"
    if extra_headers:
        for k, v in extra_headers.items():
            req += f"{k}: {v}\r\n"
    req += "\r\n"
    s.sendall(req.encode("latin1"))
    
    response = b""
    while True:
        try:
            chunk = s.recv(4096)
            if not chunk:
                break
            response += chunk
        except socket.timeout:
            break
    s.close()
    
    if b"\r\n\r\n" not in response:
        return 0, {}, response
        
    header_part, body_part = response.split(b"\r\n\r\n", 1)
    lines = header_part.decode("latin1", errors="replace").split("\r\n")
    status_line = lines[0]
    parts = status_line.split(" ")
    status_code = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            hk, hv = line.split(":", 1)
            headers[hk.strip().lower()] = hv.strip()
            
    return status_code, headers, body_part

def run_mock_upstream(stop_event):
    """Lightweight mock upstream listening on port 3000."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind(("127.0.0.1", MOCK_UPSTREAM_PORT))
        server.listen(10)
        server.settimeout(0.5)
        while not stop_event.is_set():
            try:
                conn, _ = server.accept()
            except socket.timeout:
                continue
            try:
                data = conn.recv(2048).decode("latin1", errors="ignore")
                if "GET /api/status" in data:
                    body = b'{"status":"api_upstream_ok"}'
                    resp = (
                        b"HTTP/1.1 200 OK\r\n"
                        b"Content-Type: application/json\r\n"
                        b"Content-Length: " + str(len(body)).encode() + b"\r\n"
                        b"Connection: close\r\n\r\n" + body
                    )
                    conn.sendall(resp)
                else:
                    body = b"Not Found Upstream"
                    resp = (
                        b"HTTP/1.1 404 Not Found\r\n"
                        b"Content-Length: " + str(len(body)).encode() + b"\r\n"
                        b"Connection: close\r\n\r\n" + body
                    )
                    conn.sendall(resp)
                conn.close()
            except Exception:
                pass
    except Exception as e:
        print(f"Mock upstream bind warning: {e}")
    finally:
        server.close()

def wait_for_port(port, timeout=3.0):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return True
        except (socket.error, ConnectionRefusedError):
            time.sleep(0.05)
    return False

def main():
    print(f"\n{C_BOLD}{C_CYAN}╔══════════════════════════════════════════════════════════════════╗{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}║     SANKRAM STATIC FILE & SPA ENGINE AUTOMATED TEST SUITE        ║{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}║       Zero-Copy Sendfile, MIME Matrix & Traversal Security       ║{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}╚══════════════════════════════════════════════════════════════════╝{C_RESET}\n")

    bin_path = "./build/sankram.exe" if sys.platform == "win32" else "./build/sankram"
    if not os.path.exists(bin_path):
        print(f"{C_RED}❌ Error: Sankram binary not found at {bin_path}{C_RESET}")
        return 1

    with tempfile.TemporaryDirectory() as static_root:
        # Populate test static files
        html_content = b"<!DOCTYPE html><html><body><h1>Sankram SPA App</h1></body></html>"
        css_content = b"body { background: #0d1117; color: #58a6ff; }"
        js_content = b"console.log('Sankram static assets loaded successfully');"
        json_content = b'{"platform":"sankram","static":true}'
        svg_content = b'<svg xmlns="http://www.w3.org/2000/svg"><circle r="10"/></svg>'

        with open(os.path.join(static_root, "index.html"), "wb") as f:
            f.write(html_content)

        assets_dir = os.path.join(static_root, "assets")
        os.makedirs(assets_dir, exist_ok=True)

        with open(os.path.join(assets_dir, "style.css"), "wb") as f:
            f.write(css_content)

        with open(os.path.join(assets_dir, "app.js"), "wb") as f:
            f.write(js_content)

        with open(os.path.join(assets_dir, "data.json"), "wb") as f:
            f.write(json_content)

        with open(os.path.join(static_root, "logo.svg"), "wb") as f:
            f.write(svg_content)

        # -------------------------------------------------------------
        # PHASE 1: Static Files + SPA Fallback Mode (--spa)
        # -------------------------------------------------------------
        print(f"{C_BOLD}--- Phase 1: Static Delivery & SPA Mode Active (-s {static_root} --spa) ---{C_RESET}")
        cmd_spa = [bin_path, "-p", str(TEST_PORT), "-s", static_root, "--spa", "-l", "warn"]
        proc_spa = subprocess.Popen(cmd_spa)
        
        try:
            if not wait_for_port(TEST_PORT):
                raise RuntimeError("Sankram failed to bind test port in SPA mode.")

            # Test 1: GET / (Directory root -> index.html)
            code, hdrs, body = raw_http_request("127.0.0.1", TEST_PORT, "/")
            assert code == 200, f"Expected 200 for /, got {code}"
            assert "text/html" in hdrs.get("content-type", ""), f"Wrong Content-Type: {hdrs.get('content-type')}"
            assert body == html_content, "Body mismatch for /"
            print(f"  {C_GREEN}✔ [PASS]{C_RESET} Root URL Index Resolution (GET / -> index.html)  [HTTP 200]")

            # Test 2: GET /index.html
            code, hdrs, body = raw_http_request("127.0.0.1", TEST_PORT, "/index.html")
            assert code == 200, f"Expected 200, got {code}"
            assert "text/html" in hdrs.get("content-type", "")
            assert body == html_content
            print(f"  {C_GREEN}✔ [PASS]{C_RESET} Explicit Index Path (GET /index.html)             [HTTP 200]")

            # Test 3: GET /assets/style.css
            code, hdrs, body = raw_http_request("127.0.0.1", TEST_PORT, "/assets/style.css")
            assert code == 200, f"Expected 200, got {code}"
            assert "text/css" in hdrs.get("content-type", "")
            assert body == css_content
            print(f"  {C_GREEN}✔ [PASS]{C_RESET} Nested CSS Asset (GET /assets/style.css)          [HTTP 200]")

            # Test 4: GET /assets/app.js
            code, hdrs, body = raw_http_request("127.0.0.1", TEST_PORT, "/assets/app.js")
            assert code == 200, f"Expected 200, got {code}"
            assert "javascript" in hdrs.get("content-type", "")
            assert body == js_content
            print(f"  {C_GREEN}✔ [PASS]{C_RESET} Nested JS Asset (GET /assets/app.js)              [HTTP 200]")

            # Test 5: GET /assets/data.json
            code, hdrs, body = raw_http_request("127.0.0.1", TEST_PORT, "/assets/data.json")
            assert code == 200, f"Expected 200, got {code}"
            assert "application/json" in hdrs.get("content-type", "")
            assert body == json_content
            print(f"  {C_GREEN}✔ [PASS]{C_RESET} JSON Data Asset (GET /assets/data.json)           [HTTP 200]")

            # Test 6: GET /logo.svg
            code, hdrs, body = raw_http_request("127.0.0.1", TEST_PORT, "/logo.svg")
            assert code == 200, f"Expected 200, got {code}"
            assert "image/svg+xml" in hdrs.get("content-type", "")
            assert body == svg_content
            print(f"  {C_GREEN}✔ [PASS]{C_RESET} Vector SVG Asset (GET /logo.svg)                 [HTTP 200]")

            # Test 7: Query String Stripping (/assets/style.css?v=20261118&hash=abc)
            code, hdrs, body = raw_http_request("127.0.0.1", TEST_PORT, "/assets/style.css?v=20261118&hash=abc")
            assert code == 200, f"Expected 200, got {code}"
            assert "text/css" in hdrs.get("content-type", "")
            assert body == css_content
            print(f"  {C_GREEN}✔ [PASS]{C_RESET} Query Parameter Stripping (style.css?v=123)       [HTTP 200]")

            # Test 8: Security Sandboxing - Directory Traversal (/../../etc/passwd)
            code, _, _ = raw_http_request("127.0.0.1", TEST_PORT, "/../../etc/passwd")
            assert code == 403, f"Expected 403 Forbidden for traversal, got {code}"
            print(f"  {C_GREEN}✔ [PASS]{C_RESET} Path Traversal Defense (GET /../../etc/passwd)    [HTTP 403]")

            # Test 9: Security Sandboxing - Internal .. Traversal (/assets/../secret)
            code, _, _ = raw_http_request("127.0.0.1", TEST_PORT, "/assets/../secret")
            assert code == 403, f"Expected 403 Forbidden for traversal, got {code}"
            print(f"  {C_GREEN}✔ [PASS]{C_RESET} Subdir Traversal Defense (GET /assets/../secret)   [HTTP 403]")

            # Test 10: SPA Client Route Fallback (/dashboard)
            code, hdrs, body = raw_http_request("127.0.0.1", TEST_PORT, "/dashboard")
            assert code == 200, f"Expected 200 SPA fallback, got {code}"
            assert "text/html" in hdrs.get("content-type", "")
            assert body == html_content, "SPA fallback did not return index.html"
            print(f"  {C_GREEN}✔ [PASS]{C_RESET} SPA Route Fallback (GET /dashboard -> index.html) [HTTP 200]")

            # Test 11: Deep Nested SPA Route (/admin/settings/profile)
            code, hdrs, body = raw_http_request("127.0.0.1", TEST_PORT, "/admin/settings/profile")
            assert code == 200, f"Expected 200 SPA fallback, got {code}"
            assert "text/html" in hdrs.get("content-type", "")
            assert body == html_content
            print(f"  {C_GREEN}✔ [PASS]{C_RESET} Deep SPA Route Fallback (/admin/settings/profile)  [HTTP 200]")

        finally:
            proc_spa.terminate()
            proc_spa.wait()
            time.sleep(0.3)

        # -------------------------------------------------------------
        # PHASE 2: Non-SPA Mode & Seamless Upstream Fallback
        # -------------------------------------------------------------
        print(f"\n{C_BOLD}--- Phase 2: Static Delivery + Upstream Fallback (without --spa) ---{C_RESET}")
        stop_upstream = threading.Event()
        upstream_thread = threading.Thread(target=run_mock_upstream, args=(stop_upstream,), daemon=True)
        upstream_thread.start()
        time.sleep(0.2)

        cmd_non_spa = [bin_path, "-p", str(TEST_PORT), "-s", static_root, "-l", "warn"]
        proc_non_spa = subprocess.Popen(cmd_non_spa)

        try:
            if not wait_for_port(TEST_PORT):
                raise RuntimeError("Sankram failed to bind test port in Non-SPA mode.")

            # Test 12: Existing static file is still served directly by Sankram
            code, hdrs, body = raw_http_request("127.0.0.1", TEST_PORT, "/assets/style.css")
            assert code == 200
            assert body == css_content
            print(f"  {C_GREEN}✔ [PASS]{C_RESET} Direct Static File Service in Non-SPA Mode        [HTTP 200]")

            # Test 13: Non-existent file / API route falls through to upstream port 3000
            code, hdrs, body = raw_http_request("127.0.0.1", TEST_PORT, "/api/status")
            assert code == 200, f"Expected 200 from upstream API, got {code}"
            assert b"api_upstream_ok" in body, f"Upstream body mismatch: {body}"
            print(f"  {C_GREEN}✔ [PASS]{C_RESET} Non-Static Path Transparent Upstream Fallback     [HTTP 200 (Upstream)]")

            # Test 14: Non-existent route on upstream returns upstream 404
            code, _, _ = raw_http_request("127.0.0.1", TEST_PORT, "/unknown/resource")
            assert code == 404, f"Expected 404 from upstream, got {code}"
            print(f"  {C_GREEN}✔ [PASS]{C_RESET} Upstream 404 Preservation for Missing Paths       [HTTP 404 (Upstream)]")

        finally:
            proc_non_spa.terminate()
            proc_non_spa.wait()
            stop_upstream.set()
            time.sleep(0.2)

    print(f"\n{C_BOLD}{C_GREEN}=================================================================={C_RESET}")
    print(f"{C_BOLD}{C_GREEN}🎉 ALL STATIC FILE & SPA FALLBACK TESTS PASSED (100% GREEN)       {C_RESET}")
    print(f"{C_BOLD}{C_GREEN}=================================================================={C_RESET}\n")
    return 0

if __name__ == "__main__":
    sys.exit(main())

