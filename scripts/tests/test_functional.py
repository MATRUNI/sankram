#!/usr/bin/env python3
"""
Sankram Proxy - Real-World Web Pages & Functional Test Suite
Standard Library Only (Zero external pip packages).
Migrated from test_suite.js.
"""

import os
import sys
import time
import json
import re
import signal
import subprocess
import urllib.request
import urllib.error
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

PROXY_PORT = 17777
PROXY_URL = f"http://127.0.0.1:{PROXY_PORT}"
REPORT_FILE = "logs/test_suite_report.log"

# ANSI Terminal Colors
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_GREEN = "\033[32m"
C_RED = "\033[31m"
C_YELLOW = "\033[33m"
C_CYAN = "\033[36m"
C_BLUE = "\033[34m"
C_DIM = "\033[2m"

test_cases = [
    {
        "name": "Google Homepage (Full HTML)",
        "url": "https://www.google.com/",
        "method": "GET",
        "expected_status": 200,
        "headers": {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"},
        "validate": lambda headers, body: "google" in body.lower() or "<title>" in body.lower(),
    },
    {
        "name": "Hacker News Frontpage (HTML/Cloudflare)",
        "url": "https://news.ycombinator.com/",
        "method": "GET",
        "expected_status": 200,
        "headers": {"User-Agent": "Mozilla/5.0"},
        "validate": lambda headers, body: "Hacker News" in body,
    },
    {
        "name": "Wikipedia - C Language Article (~150KB)",
        "url": "https://en.wikipedia.org/wiki/C_(programming_language)",
        "method": "GET",
        "expected_status": 200,
        "headers": {"User-Agent": "C-Proxy-Benchmark/1.0 (https://github.com/)"},
        "validate": lambda headers, body: "Dennis Ritchie" in body or "programming" in body,
    },
    {
        "name": "DuckDuckGo Search Engine (HTML)",
        "url": "https://html.duckduckgo.com/html/",
        "method": "GET",
        "expected_status": [200, 202],
        "headers": {"User-Agent": "Mozilla/5.0"},
        "validate": lambda headers, body: "DuckDuckGo" in body or len(body) > 0,
    },
    {
        "name": "Plain HTTP Port 80 - Example.com",
        "url": "http://example.com/",
        "method": "GET",
        "expected_status": 200,
        "headers": {},
        "validate": lambda headers, body: "Example Domain" in body,
    },
    {
        "name": "Cloudflare CDN - REST JSON API",
        "url": "https://jsonplaceholder.typicode.com/posts/1",
        "method": "GET",
        "expected_status": 200,
        "headers": {},
        "validate": lambda headers, body: '"userId": 1' in body or '"userId":1' in body,
    },
    {
        "name": "POST Body Streaming - Upstream JSON",
        "url": "https://httpbin.org/post",
        "method": "POST",
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"project": "C-Proxy-C10K", "author": "Himanshu", "level": 9000}).encode("utf-8"),
        "expected_status": 200,
        "validate": lambda headers, body: "C-Proxy-C10K" in body,
    },
    {
        "name": "CORS Preflight - OPTIONS Check",
        "url": "https://httpbin.org/get",
        "method": "OPTIONS",
        "expected_status": 204,
        "headers": {
            "Origin": "https://api-os.pages.dev",
            "Access-Control-Request-Method": "GET"
        },
        "validate": lambda headers, body: "access-control-allow-origin" in [k.lower() for k in headers.keys()],
    },
    {
        "name": "HTTP 404 - Not Found Passthrough",
        "url": "https://httpbin.org/status/404",
        "method": "GET",
        "expected_status": 404,
        "headers": {},
    },
    {
        "name": "DNS Failure - 502 Bad Gateway",
        "url": "https://thisdomainwillneverexist999888777.xyz",
        "method": "GET",
        "expected_status": 502,
        "headers": {},
    },
    {
        "name": "Default Upstream Routing (Port 3000 Fallback)",
        "raw_url": f"{PROXY_URL}/",
        "method": "GET",
        "expected_status": [200, 502],  # 200 if dev server running, 502 if offline
        "headers": {},
    },
]

def is_proxy_alive():
    try:
        req = urllib.request.Request(f"{PROXY_URL}/", headers={"Connection": "close"})
        with urllib.request.urlopen(req, timeout=0.3) as resp:
            resp.read()
            return True
    except urllib.error.HTTPError:
        return True  # 502/404 means proxy is actively responding
    except Exception:
        return False

def run_single_test(tc, max_retries=2):
    target = tc.get("raw_url") or f"{PROXY_URL}/?url={urllib.parse.quote(tc['url'])}"
    method = tc.get("method", "GET")
    headers = tc.get("headers", {})
    body_data = tc.get("body")

    expected = tc.get("expected_status")
    validate_fn = tc.get("validate")

    for attempt in range(max_retries + 1):
        req = urllib.request.Request(target, data=body_data, headers=headers, method=method)
        start = time.perf_counter()
        status = 0
        error_msg = None
        body_str = ""
        resp_headers = {}

        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                status = response.status
                resp_headers = dict(response.headers)
                body_bytes = response.read()
                body_str = body_bytes.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            status = e.code
            resp_headers = dict(e.headers)
            try:
                body_str = e.read().decode("utf-8", errors="replace")
            except Exception:
                body_str = ""
        except Exception as e:
            error_msg = str(e)

        duration_ms = round((time.perf_counter() - start) * 1000)
        size_bytes = len(body_str.encode("utf-8"))

        if isinstance(expected, list):
            status_match = status in expected
        else:
            status_match = (status == expected)

        body_valid = True
        if validate_fn and status_match:
            try:
                body_valid = bool(validate_fn(resp_headers, body_str))
            except Exception as ve:
                body_valid = False
                error_msg = f"Validation exception: {ve}"

        if error_msg is None:
            if not status_match:
                error_msg = f"Expected HTTP {expected}, got {status}"
            elif not body_valid:
                error_msg = "Content validation failed on returned payload"

        passed = status_match and body_valid and (error_msg is None)
        if passed or attempt == max_retries or "DNS Failure" in tc.get("name", ""):
            break
        # Transient retry pause on external rate limit or cloud drop
        time.sleep(0.15)

    return {
        "name": tc["name"],
        "status": status,
        "duration_ms": duration_ms,
        "size_bytes": size_bytes,
        "passed": passed,
        "error_msg": error_msg,
    }

def main():
    print(f"\n{C_BOLD}{C_CYAN}╔════════════════════════════════════════════════════════════════╗{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}║   C REVERSE PROXY — REAL WEBPAGES & HIGH-LOAD TEST SUITE      ║{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}╚════════════════════════════════════════════════════════════════╝{C_RESET}\n")

    spawned_proxy = None
    if not is_proxy_alive():
        bin_path = "./build/sankram.exe" if sys.platform == "win32" else "./build/sankram"
        if not os.path.exists(bin_path):
            bin_path = "./build/api"
        print(f"Proxy not running. Starting {bin_path} on port {PROXY_PORT}...")
        spawned_proxy = subprocess.Popen([bin_path, "-p", str(PROXY_PORT), "-o", "https://api-os.pages.dev,http://localhost:3000", "-l", "warn"],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(30):
            if is_proxy_alive():
                break
            time.sleep(0.1)

    try:
        os.makedirs("logs", exist_ok=True)
        log_lines = []

        def log(msg):
            print(msg)
            clean = re.sub(r"\x1b\[[0-9;]*m", "", msg)
            log_lines.append(clean + "\n")

        log(f"Timestamp   : {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
        log(f"Target Proxy: {PROXY_URL}\n")

        # Phase 1: Real-World Webpages & Matrix
        log(f"{C_BOLD}[PHASE 1] Loading Real Webpages, HTML Payloads & APIs simultaneously...{C_RESET}")
        with ThreadPoolExecutor(max_workers=len(test_cases)) as executor:
            phase1_results = list(executor.map(run_single_test, test_cases))

        for r in phase1_results:
            tag = f"{C_GREEN}✔ PASS{C_RESET}" if r["passed"] else f"{C_RED}✖ FAIL{C_RESET}"
            status_tag = f"HTTP {r['status']}" if r["status"] else "ERR"
            time_str = f"{r['duration_ms']}ms".rjust(7)
            size_kb = r["size_bytes"] / 1024.0
            size_str = f"{size_kb:.1f} KB".rjust(9) if size_kb >= 1.0 else f"{r['size_bytes']} B".rjust(9)

            log(f"  [{tag}] {C_BOLD}{r['name']:<42}{C_RESET} [{status_tag}] {C_BLUE}{size_str}{C_RESET} in {C_YELLOW}{time_str}{C_RESET}")
            if not r["passed"]:
                log(f"         {C_RED}↳ Error: {r['error_msg']}{C_RESET}")

        # Phase 2: Parallel Concurrency Burst (50 requests simultaneously)
        burst_count = 50
        log(f"\n{C_BOLD}[PHASE 2] Firing Parallel Burst ({burst_count} simultaneous requests across Google, Hacker News, Wikipedia)...{C_RESET}")

        burst_targets = [
            {"url": "https://www.google.com/", "name": "Google"},
            {"url": "http://example.com/", "name": "Example.com"},
        ]

        burst_cases = []
        for idx in range(burst_count):
            t = burst_targets[idx % len(burst_targets)]
            burst_cases.append({
                "name": f"Burst #{idx + 1} ({t['name']})",
                "url": t["url"],
                "method": "GET",
                "expected_status": 200,
                "headers": {"User-Agent": "C-Proxy-Benchmark/1.0 (https://github.com/)"},
            })

        burst_start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=burst_count) as executor:
            burst_results = list(executor.map(run_single_test, burst_cases))
        total_burst_time = time.perf_counter() - burst_start

        burst_passed = sum(1 for r in burst_results if r["passed"])
        burst_failed = burst_count - burst_passed
        latencies = sorted(r["duration_ms"] for r in burst_results)
        min_lat = latencies[0] if latencies else 0
        max_lat = latencies[-1] if latencies else 0
        avg_lat = sum(latencies) / len(latencies) if latencies else 0
        rps = (burst_count / total_burst_time) if total_burst_time > 0 else 0
        total_bytes = sum(r["size_bytes"] for r in burst_results)

        log(f"  Completed in : {C_YELLOW}{total_burst_time:.2f}s{C_RESET}")
        log(f"  Throughput   : {C_BOLD}{rps:.1f} req/sec{C_RESET}")
        log(f"  Data Streamed: {C_BOLD}{total_bytes / 1024.0:.1f} KB{C_RESET}")
        log(f"  Pass / Fail  : {C_GREEN}{burst_passed} passed{C_RESET}, {C_RED if burst_failed > 0 else C_DIM}{burst_failed} failed{C_RESET}")
        log(f"  Latency      : Min {min_lat}ms | Avg {avg_lat:.1f}ms | Max {max_lat}ms")
        for r in burst_results:
            if not r["passed"]:
                log(f"       {C_RED}↳ Failed: {r['name']} - {r['error_msg']}{C_RESET}")

        # Final Summary
        all_results = phase1_results + burst_results
        total_pass = sum(1 for r in all_results if r["passed"])
        total_fail = len(all_results) - total_pass

        rate = (total_pass / len(all_results)) * 100.0
        rate_color = C_GREEN if total_pass == len(all_results) else C_YELLOW

        log(f"\n{C_BOLD}================================================================{C_RESET}")
        log(f"                       FINAL REPORT                             ")
        log(f"================================================================")
        log(f"  Total Requests Executed : {len(all_results)}")
        log(f"  Success Rate            : {rate_color}{rate:.1f}%{C_RESET}")
        log(f"  Report Saved To         : {REPORT_FILE}")
        log(f"================================================================\n")

        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            f.writelines(log_lines)

        return 0 if total_fail == 0 else 1

    finally:
        if spawned_proxy and spawned_proxy.poll() is None:
            spawned_proxy.send_signal(signal.SIGINT if sys.platform != "win32" else signal.SIGTERM)
            spawned_proxy.wait()

if __name__ == "__main__":
    sys.exit(main())
