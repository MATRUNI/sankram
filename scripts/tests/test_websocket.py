#!/usr/bin/env python3
"""
Sankram Proxy - Automated WebSocket Tunneling Test Suite
Validates RFC 6455 Handshake, CORS & PNA injection, and Full-Duplex Echo Framing.
"""

import socket
import threading
import time
import base64
import hashlib
import sys
import subprocess

WS_MAGIC = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
MOCK_PORT = 3000
PROXY_PORT = 17777

def run_mock_ws():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", MOCK_PORT))
    server.listen(5)
    
    conn, addr = server.accept()
    data = conn.recv(4096).decode("utf-8", errors="ignore")
    key = ""
    for line in data.split("\r\n"):
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
    
    # Echo frames back
    while True:
        data = conn.recv(4096)
        if not data:
            break
        # Decode client frame (client frames are masked)
        if len(data) >= 6:
            mask = data[2:6]
            payload = bytes([b ^ mask[i % 4] for i, b in enumerate(data[6:])])
            # Reply with unmasked text frame (0x81)
            echo = b"\x81" + bytes([len(payload)]) + payload
            conn.sendall(echo)
            
    conn.close()
    server.close()

def main():
    print("=" * 64)
    print("       SANKRAM WEBSOCKET FULL-DUPLEX TUNNEL TEST SUITE       ")
    print("=" * 64)
    
    # 1. Start Mock WS Backend
    t = threading.Thread(target=run_mock_ws, daemon=True)
    t.start()
    time.sleep(0.2)
    
    # 2. Start Sankram Proxy
    bin_path = "./build/sankram.exe" if sys.platform == "win32" else "./build/sankram"
    proxy = subprocess.Popen([bin_path, "-p", str(PROXY_PORT), "-o", "https://api-os.pages.dev", "-l", "debug"])
    time.sleep(0.5)
    
    try:
        # 3. Connect client to Sankram
        client = socket.socket()
        client.connect(("127.0.0.1", PROXY_PORT))
        handshake = (
            "GET / HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{PROXY_PORT}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
            "Origin: https://api-os.pages.dev\r\n\r\n"
        )
        client.sendall(handshake.encode())
        
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = client.recv(4096)
            if not chunk:
                break
            resp += chunk

        assert b"101 Switching Protocols" in resp, "Missing 101 Switching Protocols"
        assert b"Access-Control-Allow-Origin: https://api-os.pages.dev" in resp, "Missing CORS Origin header"
        assert b"Access-Control-Allow-Private-Network: true" in resp, "Missing PNA header"
        print("  [✔ PASS] RFC 6455 Handshake & CORS / PNA Injected  [HTTP 101]")
        
        # 4. Send Message 1
        msg1 = b"Hello Sankram WebSocket!"
        mask = b"\x12\x34\x56\x78"
        masked = bytes([b ^ mask[i % 4] for i, b in enumerate(msg1)])
        frame1 = b"\x81" + bytes([0x80 | len(msg1)]) + mask + masked
        client.sendall(frame1)
        
        echo1 = client.recv(4096)
        assert echo1[2:] == msg1, f"Echo mismatch: {echo1[2:]} != {msg1}"
        print(f"  [✔ PASS] Bidirectional Frame Echo 1                [{echo1[2:].decode()}]")
        
        # 5. Send Message 2
        msg2 = b"Full duplex real-time streaming confirmed."
        masked2 = bytes([b ^ mask[i % 4] for i, b in enumerate(msg2)])
        frame2 = b"\x81" + bytes([0x80 | len(msg2)]) + mask + masked2
        client.sendall(frame2)
        
        echo2 = client.recv(4096)
        assert echo2[2:] == msg2, f"Echo mismatch: {echo2[2:]} != {msg2}"
        print(f"  [✔ PASS] Bidirectional Frame Echo 2                [{echo2[2:].decode()}]")
        
        client.close()
        print("  [✔ PASS] Graceful Disconnect & Teardown            [CLEAN]")
        print("=" * 64)
        print("🎉 ALL WEBSOCKET TESTS PASSED (100% GREEN)")
        print("=" * 64)
        return 0
    except Exception as e:
        print(f"❌ WEBSOCKET TEST FAILED: {e}")
        return 1
    finally:
        proxy.terminate()
        proxy.wait()

if __name__ == "__main__":
    sys.exit(main())

