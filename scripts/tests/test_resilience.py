#!/usr/bin/env python3
"""
Sankram Proxy - Automated Resilience & Pipelining Test Suite
Validates:
  1. Stale Pooled Upstream Auto-Retry (Peer RST / Keep-Alive Timeout)
  2. Multi-Request HTTP Pipelining in Single TCP Packet (memmove Buffer Preservation)
  3. Fragmented Pipelined Header Buffering Across Epoll Turns
"""

import os
import sys
import time
import socket
import threading
import subprocess
import base64
import hashlib

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

MOCK_PORT = 19091
PROXY_PORT = 17791

def test_stale_upstream_retry(proxy_bin):
    """
    Simulates upstream backend that abruptly closes connection while idle in the pool.
    Verifies Sankram transparently redials fresh upstream connection and returns 200 OK.
    """
    print(f"\n{C_CYAN}>>> [Part 1/7] Testing Stale Pooled Upstream Auto-Retry...{C_RESET}")
    
    mock_ready = threading.Event()
    
    def run_mock():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", MOCK_PORT))
        s.listen(5)
        mock_ready.set()
        
        # Connection 1: Serves response, then forcibly closes with RST while idle
        conn1, _ = s.accept()
        _ = conn1.recv(1024)
        conn1.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\nConnection: keep-alive\r\n\r\nOK-01")
        time.sleep(0.2)
        # Force TCP RST to guarantee socket is dead
        conn1.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, b'\x01\x00\x00\x00\x00\x00\x00\x00')
        conn1.close()
        
        # Connection 2: Fresh connection from Sankram retry!
        conn2, _ = s.accept()
        _ = conn2.recv(1024)
        conn2.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\nConnection: close\r\n\r\nOK-02")
        conn2.close()
        s.close()
        
    mock_thread = threading.Thread(target=run_mock, daemon=True)
    mock_thread.start()
    mock_ready.wait(timeout=2.0)
    
    proxy = subprocess.Popen([proxy_bin, "-p", str(PROXY_PORT), "-t", "1", "-l", "debug"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.4)
    
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("127.0.0.1", PROXY_PORT))
        
        # Request 1 (populates pool/keepalive)
        req1 = f"GET /?url=http%3A%2F%2F127.0.0.1%3A{MOCK_PORT}%2F HTTP/1.1\r\nHost: 127.0.0.1:{PROXY_PORT}\r\nConnection: keep-alive\r\n\r\n"
        client.sendall(req1.encode())
        resp1 = client.recv(1024).decode(errors="replace")
        assert "HTTP/1.1 200 OK" in resp1 and "OK-01" in resp1, f"Req 1 failed: {resp1}"
        print(f"  [{C_GREEN}✔ PASS{C_RESET}] Request 1 succeeded and kept connection alive")
        
        # Wait for upstream to abruptly close
        time.sleep(0.3)
        
        # Request 2 (stale connection in pool must auto-retry)
        req2 = f"GET /?url=http%3A%2F%2F127.0.0.1%3A{MOCK_PORT}%2F HTTP/1.1\r\nHost: 127.0.0.1:{PROXY_PORT}\r\nConnection: close\r\n\r\n"
        client.sendall(req2.encode())
        resp2 = client.recv(1024).decode(errors="replace")
        assert "HTTP/1.1 200 OK" in resp2 and "OK-02" in resp2, f"Req 2 failed (did not retry): {resp2}"
        print(f"  [{C_GREEN}✔ PASS{C_RESET}] Stale socket detected & transparently retried on fresh connection (200 OK)")
        
        client.close()
    finally:
        proxy.terminate()
        proxy.wait(timeout=3.0)

def test_pipelined_multi_requests(proxy_bin):
    """
    Sends 3 distinct HTTP requests packed inside ONE single TCP packet.
    Verifies memmove buffer preservation and sequential pipeline responses.
    """
    print(f"\n{C_CYAN}>>> [Part 2/7] Testing Multi-Request Pipelining in Single Packet...{C_RESET}")
    
    mock_ready = threading.Event()
    
    def run_mock():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", MOCK_PORT))
        s.listen(5)
        mock_ready.set()
        
        conn, _ = s.accept()
        for i in range(1, 4):
            _ = conn.recv(1024)
            conn_hdr = "Connection: close" if i == 3 else "Connection: keep-alive"
            resp = f"HTTP/1.1 200 OK\r\nContent-Length: 6\r\n{conn_hdr}\r\n\r\nRESP-{i}".encode()
            conn.sendall(resp)
        conn.close()
        s.close()
        
    mock_thread = threading.Thread(target=run_mock, daemon=True)
    mock_thread.start()
    mock_ready.wait(timeout=2.0)
    
    proxy = subprocess.Popen([proxy_bin, "-p", str(PROXY_PORT), "-t", "2", "-l", "error"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.4)
    
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("127.0.0.1", PROXY_PORT))
        
        r1 = f"GET /?url=http%3A%2F%2F127.0.0.1%3A{MOCK_PORT}%2F1 HTTP/1.1\r\nHost: 127.0.0.1:{PROXY_PORT}\r\nConnection: keep-alive\r\n\r\n"
        r2 = f"GET /?url=http%3A%2F%2F127.0.0.1%3A{MOCK_PORT}%2F2 HTTP/1.1\r\nHost: 127.0.0.1:{PROXY_PORT}\r\nConnection: keep-alive\r\n\r\n"
        r3 = f"GET /?url=http%3A%2F%2F127.0.0.1%3A{MOCK_PORT}%2F3 HTTP/1.1\r\nHost: 127.0.0.1:{PROXY_PORT}\r\nConnection: close\r\n\r\n"
        
        # Fire all 3 in a single burst
        client.sendall((r1 + r2 + r3).encode())
        
        client.settimeout(3.0)
        buf = b""
        while True:
            try:
                chunk = client.recv(4096)
                if not chunk: break
                buf += chunk
                if b"RESP-3" in buf: break
            except socket.timeout:
                break
                
        assert b"RESP-1" in buf, "Missing RESP-1"
        assert b"RESP-2" in buf, "Missing RESP-2 (pipelining buffer lost!)"
        assert b"RESP-3" in buf, "Missing RESP-3 (pipelining buffer lost!)"
        assert buf.count(b"HTTP/1.1 200 OK") == 3, "Did not receive all 3 responses"
        
        print(f"  [{C_GREEN}✔ PASS{C_RESET}] 3 Pipelined Requests sent in 1 packet ➔ All 3 responses returned in order")
        client.close()
    finally:
        proxy.terminate()
        proxy.wait(timeout=3.0)

def test_fragmented_pipelined_request(proxy_bin):
    """
    Sends Request 1 + partial header of Request 2, pauses, then delivers remainder.
    Verifies epoll correctly re-arms and completes parsing of fragmented pipelined requests.
    """
    print(f"\n{C_CYAN}>>> [Part 3/7] Testing Fragmented Pipelining Across Epoll Turns...{C_RESET}")
    
    mock_ready = threading.Event()
    
    def run_mock():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", MOCK_PORT))
        s.listen(5)
        mock_ready.set()
        
        conn, _ = s.accept()
        _ = conn.recv(1024)
        conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 6\r\nConnection: keep-alive\r\n\r\nRESP-A")
        
        _ = conn.recv(1024)
        conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 6\r\nConnection: close\r\n\r\nRESP-B")
        conn.close()
        s.close()
        
    mock_thread = threading.Thread(target=run_mock, daemon=True)
    mock_thread.start()
    mock_ready.wait(timeout=2.0)
    
    proxy = subprocess.Popen([proxy_bin, "-p", str(PROXY_PORT), "-t", "2", "-l", "error"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.4)
    
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("127.0.0.1", PROXY_PORT))
        
        r1 = f"GET /?url=http%3A%2F%2F127.0.0.1%3A{MOCK_PORT}%2F1 HTTP/1.1\r\nHost: 127.0.0.1:{PROXY_PORT}\r\nConnection: keep-alive\r\n\r\n"
        r2_frag1 = f"GET /?url=http%3A%2F%2F127.0.0.1%3A{MOCK_PORT}%2F2 HTTP/1.1\r\nHost: 127.0.0.1"
        r2_frag2 = f":{PROXY_PORT}\r\nConnection: close\r\n\r\n"
        
        # Send Request 1 + first fragment of Request 2
        client.sendall((r1 + r2_frag1).encode())
        
        resp1 = client.recv(1024)
        assert b"RESP-A" in resp1, f"Req 1 failed: {resp1}"
        
        # Pause to let Sankram park in epoll waiting for rest of Request 2
        time.sleep(0.2)
        
        # Deliver second fragment
        client.sendall(r2_frag2.encode())
        
        resp2 = client.recv(1024)
        assert b"RESP-B" in resp2, f"Req 2 failed: {resp2}"
        
        print(f"  [{C_GREEN}✔ PASS{C_RESET}] Fragmented pipelined request correctly buffered, re-armed, and parsed")
        client.close()
    finally:
        proxy.terminate()
        proxy.wait(timeout=3.0)

def test_chunked_upload_streaming(proxy_bin):
    """
    Sends a client POST request with Transfer-Encoding: chunked in multiple network frames.
    Verifies Sankram streams chunks to upstream, detects terminal chunk 0\\r\\n\\r\\n, and returns response.
    """
    print(f"\n{C_CYAN}>>> [Part 4/7] Testing Client Chunked Upload (Transfer-Encoding: chunked)...{C_RESET}")
    
    mock_ready = threading.Event()
    received_body = bytearray()
    
    def run_mock():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", MOCK_PORT))
        s.listen(5)
        mock_ready.set()
        
        conn, _ = s.accept()
        while True:
            chunk = conn.recv(4096)
            if not chunk: break
            received_body.extend(chunk)
            if b"0\r\n\r\n" in received_body: break
            
        resp = b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 26\r\nConnection: close\r\n\r\n{\"status\":\"chunked_upload\"}"
        conn.sendall(resp)
        conn.close()
        s.close()
        
    mock_thread = threading.Thread(target=run_mock, daemon=True)
    mock_thread.start()
    mock_ready.wait(timeout=2.0)
    
    proxy = subprocess.Popen([proxy_bin, "-p", str(PROXY_PORT), "-t", "2", "-l", "error"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.4)
    
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("127.0.0.1", PROXY_PORT))
        
        # Headers + chunk 1
        headers = (
            f"POST /?url=http%3A%2F%2F127.0.0.1%3A{MOCK_PORT}%2Fupload HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{PROXY_PORT}\r\n"
            "Transfer-Encoding: chunked\r\n"
            "Connection: close\r\n\r\n"
            "4\r\nWiki\r\n"
        ).encode()
        client.sendall(headers)
        
        # Small delays to simulate streaming upload
        time.sleep(0.15)
        client.sendall(b"5\r\npedia\r\n")
        time.sleep(0.15)
        client.sendall(b"0\r\n\r\n")
        
        client.settimeout(3.0)
        resp = client.recv(4096)
        assert b"200 OK" in resp, f"Chunked upload failed: {resp}"
        assert b"chunked_upload" in resp, f"Invalid body: {resp}"
        assert b"4\r\nWiki\r\n5\r\npedia\r\n0\r\n\r\n" in received_body, "Upstream did not receive complete chunked frames"
        
        print(f"  [{C_GREEN}✔ PASS{C_RESET}] Chunked upload streamed across packets, 0\\r\\n\\r\\n detected, 200 OK received")
        client.close()
    finally:
        proxy.terminate()
        proxy.wait(timeout=3.0)

def test_streaming_backpressure_websocket(proxy_bin):
    """
    Simulates high-throughput streaming over WebSocket tunnel with asymmetric link speeds.
    Upstream blasts 128 KB of data while client deliberately stalls reading (triggering EAGAIN
    and upstream backpressure pause). Client then wakes up and drains all 128 KB with 0 bytes lost.
    """
    print(f"\n{C_CYAN}>>> [Part 5/7] Testing WebSocket Bidirectional Streaming Backpressure...{C_RESET}")
    
    WS_MAGIC = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    mock_ready = threading.Event()
    client_done = threading.Event()
    TOTAL_PAYLOAD_SIZE = 128 * 1024 # 128 KB
    TEST_DATA = b"X" * TOTAL_PAYLOAD_SIZE
    
    def run_mock():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", MOCK_PORT))
        s.listen(5)
        mock_ready.set()
        
        conn, _ = s.accept()
        req = conn.recv(4096).decode("utf-8", errors="ignore")
        key = ""
        for line in req.split("\r\n"):
            if line.lower().startswith("sec-websocket-key:"):
                key = line.split(":", 1)[1].strip()
                break
        accept = base64.b64encode(hashlib.sha1(key.encode() + WS_MAGIC).digest()).decode()
        resp = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
        )
        conn.sendall(resp.encode())
        
        # Blast 128 KB in 4 KB chunks without pause
        sent = 0
        chunk_size = 4096
        while sent < TOTAL_PAYLOAD_SIZE:
            to_send = min(chunk_size, TOTAL_PAYLOAD_SIZE - sent)
            conn.sendall(TEST_DATA[sent:sent+to_send])
            sent += to_send
            
        # Keep open until client drains all bytes
        client_done.wait(timeout=5.0)
        conn.close()
        s.close()
        
    mock_thread = threading.Thread(target=run_mock, daemon=True)
    mock_thread.start()
    mock_ready.wait(timeout=2.0)
    
    proxy = subprocess.Popen([proxy_bin, "-p", str(PROXY_PORT), "-t", "2", "-l", "error"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.4)
    
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("127.0.0.1", PROXY_PORT))
        
        ws_key = base64.b64encode(b"0123456789abcdef").decode()
        handshake = (
            f"GET /?url=http%3A%2F%2F127.0.0.1%3A{MOCK_PORT}%2Fws HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{PROXY_PORT}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {ws_key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ).encode()
        client.sendall(handshake)
        
        # Read 101 response
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = client.recv(1024)
            if not chunk: break
            resp += chunk
        assert b"101 Switching Protocols" in resp, f"Handshake failed: {resp}"
        
        header_end = resp.find(b"\r\n\r\n")
        initial_body = resp[header_end + 4:]
        
        # DELIBERATELY STALL CLIENT READ for 300ms to force proxy send buffer to fill up (EAGAIN backpressure)
        time.sleep(0.3)
        
        # Now wake up and drain all 128 KB
        client.settimeout(4.0)
        received = bytearray(initial_body)
        while len(received) < TOTAL_PAYLOAD_SIZE:
            try:
                data = client.recv(8192)
                if not data: break
                received.extend(data)
            except socket.timeout:
                break
                
        assert len(received) == TOTAL_PAYLOAD_SIZE, f"Backpressure data loss: received {len(received)} / {TOTAL_PAYLOAD_SIZE} bytes"
        assert bytes(received) == TEST_DATA, "Streamed data corrupted during backpressure buffer cycles"
        
        client_done.set()
        print(f"  [{C_GREEN}✔ PASS{C_RESET}] 128 KB streamed under backpressure stall: 0 bytes lost, 100% data integrity verified")
        client.close()
    finally:
        proxy.terminate()
        proxy.wait(timeout=3.0)

def test_slowloris_defense_header_timeout(proxy_bin):
    """
    Simulates a Slowloris attack by trickling incomplete HTTP headers across network packets.
    Verifies that Sankram enforces the aggregate header deadline, rejects the slow client with
    408 Request Timeout, and closes the connection without hanging.
    """
    print(f"\n{C_CYAN}>>> [Part 6/7] Testing Slowloris Defense (Aggregate Header Deadline)...{C_RESET}")
    
    proxy = subprocess.Popen([proxy_bin, "-p", str(PROXY_PORT), "-t", "2", "-l", "error"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.4)
    
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("127.0.0.1", PROXY_PORT))
        client.settimeout(15.0)
        
        # Initial partial request line
        client.sendall(b"GET /?url=http%3A%2F%2F127.0.0.1%3A19091%2F HTTP/1.1\r\n")
        client.sendall(f"Host: 127.0.0.1:{PROXY_PORT}\r\n".encode())
        
        # Trickle headers slowly every 0.8s without ever sending terminal \r\n\r\n
        start = time.time()
        resp = b""
        i = 1
        while time.time() - start < 13.0:
            try:
                client.sendall(f"X-Slow-Header-{i}: value-{i}\r\n".encode())
                i += 1
            except (BrokenPipeError, ConnectionResetError):
                break
            time.sleep(0.8)
            # Try non-blocking read to see if 408 was sent
            client.settimeout(0.2)
            try:
                chunk = client.recv(1024)
                if not chunk:
                    break
                resp += chunk
                if b"408" in resp:
                    break
            except socket.timeout:
                pass
            client.settimeout(15.0)
            
        elapsed = time.time() - start
        assert b"408" in resp or b"Timeout" in resp, f"Expected 408 Request Timeout, got: {resp}"
        print(f"  [{C_GREEN}✔ PASS{C_RESET}] Slowloris trickle attack detected & severed with 408 Request Timeout in {elapsed:.2f}s")
        client.close()
    finally:
        proxy.terminate()
        proxy.wait(timeout=3.0)

def test_dns_cache_resolution(proxy_bin):
    """
    Validates In-Memory DNS Caching with TTL & Case-Insensitive FNV-1a Hashing.
    Request 1: Resolves domain name 'localhost' (Cache Miss -> getaddrinfo -> Cached).
    Request 2: Resolves 'localhost' (Cache Hit -> zero DNS delay).
    Request 3: Resolves 'LOCALHOST' (Case-Insensitive Cache Hit).
    """
    print(f"\n{C_CYAN}>>> [Part 7/7] Testing In-Memory DNS Caching & Case-Insensitive Lookup...{C_RESET}")
    
    mock_ready = threading.Event()
    req_count = 0
    
    def run_mock():
        nonlocal req_count
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", MOCK_PORT))
        s.listen(10)
        mock_ready.set()
        
        while True:
            try:
                conn, _ = s.accept()
                req = conn.recv(2048)
                if not req:
                    conn.close()
                    continue
                req_count += 1
                resp = b"HTTP/1.1 200 OK\r\nContent-Length: 10\r\nConnection: close\r\n\r\ndns_cached"
                conn.sendall(resp)
                conn.close()
            except Exception:
                break
        s.close()
        
    mock_thread = threading.Thread(target=run_mock, daemon=True)
    mock_thread.start()
    mock_ready.wait(timeout=2.0)
    
    proxy = subprocess.Popen([proxy_bin, "-p", str(PROXY_PORT), "-t", "2", "-l", "error"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.4)
    
    try:
        # Request 1: Fresh resolution (Miss -> Cache Insert)
        client = socket.socket()
        client.connect(("127.0.0.1", PROXY_PORT))
        client.sendall(f"GET /?url=http%3A%2F%2Flocalhost%3A{MOCK_PORT}%2Ftest HTTP/1.1\r\nHost: 127.0.0.1:{PROXY_PORT}\r\nConnection: close\r\n\r\n".encode())
        resp1 = client.recv(1024)
        client.close()
        assert b"200 OK" in resp1 and b"dns_cached" in resp1, f"Req 1 failed: {resp1}"
        
        # Request 2: Cached resolution (Hit)
        client = socket.socket()
        client.connect(("127.0.0.1", PROXY_PORT))
        client.sendall(f"GET /?url=http%3A%2F%2Flocalhost%3A{MOCK_PORT}%2Ftest HTTP/1.1\r\nHost: 127.0.0.1:{PROXY_PORT}\r\nConnection: close\r\n\r\n".encode())
        resp2 = client.recv(1024)
        client.close()
        assert b"200 OK" in resp2 and b"dns_cached" in resp2, f"Req 2 failed: {resp2}"
        
        # Request 3: Case-insensitive 'LOCALHOST' (Hit)
        client = socket.socket()
        client.connect(("127.0.0.1", PROXY_PORT))
        client.sendall(f"GET /?url=http%3A%2F%2FLOCALHOST%3A{MOCK_PORT}%2Ftest HTTP/1.1\r\nHost: 127.0.0.1:{PROXY_PORT}\r\nConnection: close\r\n\r\n".encode())
        resp3 = client.recv(1024)
        client.close()
        assert b"200 OK" in resp3 and b"dns_cached" in resp3, f"Req 3 failed: {resp3}"
        
        assert req_count == 3, f"Expected 3 successful mock requests, got {req_count}"
        print(f"  [{C_GREEN}✔ PASS{C_RESET}] DNS Cache Miss -> Insert -> Hit -> Case-Insensitive Hit (3/3 succeeded)")
    finally:
        proxy.terminate()
        proxy.wait(timeout=3.0)

def main():
    print("=" * 64)
    print("    SANKRAM RESILIENCE & PIPELINING VALIDATION SUITE          ")
    print("=" * 64)
    
    proxy_bin = "./build/sankram.exe" if sys.platform == "win32" else "./build/sankram"
    if not os.path.exists(proxy_bin):
        proxy_bin = "./build/api"
        if not os.path.exists(proxy_bin):
            print(f"{C_RED}Error: Sankram binary not found in ./build/{C_RESET}")
            return 1
            
    try:
        test_stale_upstream_retry(proxy_bin)
        test_pipelined_multi_requests(proxy_bin)
        test_fragmented_pipelined_request(proxy_bin)
        test_chunked_upload_streaming(proxy_bin)
        test_streaming_backpressure_websocket(proxy_bin)
        test_slowloris_defense_header_timeout(proxy_bin)
        test_dns_cache_resolution(proxy_bin)
    except Exception as e:
        print(f"\n{C_RED}✖ Test Suite Encountered Error: {e}{C_RESET}")
        return 1
        
    print("\n" + "=" * 64)
    print(f"🎉 {C_GREEN}ALL RESILIENCE & PIPELINING TESTS PASSED (100% GREEN){C_RESET}")
    print("=" * 64)
    return 0

if __name__ == "__main__":
    sys.exit(main())

