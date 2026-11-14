#!/usr/bin/env python3
"""
Sankram Unified Master Test Suite Orchestrator
Standard Library Only (Zero external pip packages).
Executes:
  1. WebSocket Full-Duplex & RFC 6455 Handshake Test Suite
  2. HTTP Real-World Functional Matrix & Parallel Concurrency Burst
  3. Live Log Rotation & Commit-Before-Retire Test Suite
"""

import os
import sys
import time
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
C_BLUE = "\033[34m"

SUITES = [
    {
        "id": "websocket",
        "name": "WebSocket RFC 6455 & Full-Duplex Tunnel",
        "script": "scripts/tests/test_websocket.py",
    },
    {
        "id": "functional",
        "name": "HTTP Functional Matrix & 50-Req Parallel Burst",
        "script": "scripts/tests/test_functional.py",
    },
    {
        "id": "rotation",
        "name": "Log Carousel Rotation & Commit-Before-Retire",
        "script": "scripts/tests/test_rotation.py",
    },
    {
        "id": "fallback",
        "name": "Fallback & Overflow Circuit-Breaker Resilience",
        "script": "scripts/tests/test_fallback.py",
    },
]

def main():
    print(f"\n{C_BOLD}{C_CYAN}╔══════════════════════════════════════════════════════════════════╗{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}║              SANKRAM UNIFIED TEST SUITE RUNNER                   ║{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}║          Pure Python 3 Standard Library Test Harness             ║{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}╚══════════════════════════════════════════════════════════════════╝{C_RESET}\n")

    # Verify Sankram binary
    bin_path = "./build/sankram.exe" if sys.platform == "win32" else "./build/sankram"
    if not os.path.exists(bin_path):
        bin_path = "./build/api"
        if not os.path.exists(bin_path):
            print(f"{C_RED}❌ Error: Sankram binary not found in ./build/. Please run 'make' first.{C_RESET}\n")
            return 1

    overall_start = time.perf_counter()
    results = []

    for idx, s in enumerate(SUITES, 1):
        print(f"\n{C_BOLD}>>> [{idx}/{len(SUITES)}] Running {s['name']}...{C_RESET}")
        start_time = time.perf_counter()
        
        child_env = os.environ.copy()
        child_env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run([sys.executable, s["script"]], env=child_env)
        duration = time.perf_counter() - start_time
        passed = (proc.returncode == 0)
        
        results.append({
            "name": s["name"],
            "passed": passed,
            "duration": duration,
        })
        
        if not passed:
            print(f"\n{C_RED}✖ Test Suite '{s['name']}' FAILED with exit code {proc.returncode}{C_RESET}")

    total_time = time.perf_counter() - overall_start
    all_passed = all(r["passed"] for r in results)

    # Consolidated Scorecard
    print(f"\n{C_BOLD}=================================================================={C_RESET}")
    print(f"{C_BOLD}             SANKRAM UNIFIED TEST SUITE SCORECARD                 {C_RESET}")
    print(f"{C_BOLD}=================================================================={C_RESET}")
    for r in results:
        badge = f"{C_GREEN}✔ PASS{C_RESET}" if r["passed"] else f"{C_RED}✖ FAIL{C_RESET}"
        dur_str = f"{r['duration']:.2f}s".rjust(7)
        print(f"  [{badge}] {r['name']:<50} ({C_YELLOW}{dur_str}{C_RESET})")
    print(f"{C_BOLD}------------------------------------------------------------------{C_RESET}")
    print(f"  Total Duration: {C_BOLD}{total_time:.2f}s{C_RESET}")
    
    if all_passed:
        print(f"  Final Verdict : {C_BOLD}{C_GREEN}100% GREEN — ALL SUITES PASSED!{C_RESET}")
        print(f"{C_BOLD}=================================================================={C_RESET}\n")
        return 0
    else:
        print(f"  Final Verdict : {C_BOLD}{C_RED}ONE OR MORE TEST SUITES FAILED!{C_RESET}")
        print(f"{C_BOLD}=================================================================={C_RESET}\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())

