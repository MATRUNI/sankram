# Sankram (संक्रम) — High-Performance C Reverse Proxy & Dynamic Edge Gateway

[![CI](https://github.com/MATRUNI/sankram/actions/workflows/ci.yml/badge.svg)](https://github.com/MATRUNI/sankram/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/MATRUNI/sankram?color=brightgreen)](https://github.com/MATRUNI/sankram/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A lightweight, blazing-fast, and memory-efficient HTTP/HTTPS reverse proxy, WebSocket full-duplex tunnel, and dynamic edge gateway built from scratch in pure C. Designed to tackle extreme concurrency using an **OS-Native Multi-Reactor Architecture** (`epoll` on Linux, `kqueue` on macOS, `WSAPoll` on Windows), an **in-memory 2-way set-associative DNS cache**, an **asynchronous double-buffering carousel logger**, and raw socket/TLS multiplexing with **zero external HTTP dependencies**.

---

## ⚡ Verified Performance Achievements

Benchmark measurements executed on an 8-core Linux system (`x86_64`, Intel Core i5-9300H @ 2.40GHz) under industrial load testing tools (`wrk 4.2.0 [epoll]` and native C stress suite):

- **Peak Throughput Record**: **103,157.54 Requests / Second** (1,548,551 completed requests in 15.01s with 0 socket errors).
- **Ultra-Low Latency**: **1.80 ms median (p50)**, **2.28 ms (p75)**, **2.80 ms (p90)**, and **4.16 ms 99th percentile (p99)** latency under heavy multi-client concurrency.
- **5-Minute Continuous Soak Endurance**: **23.6 Million+ Requests** sustained non-stop over 5 full minutes (78,729.48 req/s) with **0 socket errors**, **0 packet drops**, and **0.00 MB memory drift** (locked flat at **10.38 MB RSS**).
- **Extreme Concurrency Resilience**: Seamlessly scales past **2,000 concurrent persistent connections** under peak saturation without dropping packets or stalling.
- **L3 Hardware Cache Residency**: Shrank `sizeof(struct client_session)` from **26.3 KB down to 9.8 KB** by decoupling protocol-specific buffers onto dynamic pointers, enabling 400 connections to fit 100% inside hardware L3 CPU cache (3.9 MB vs 8 MB L3 cache).
- **Zero-Allocation Hot Paths**: Zero heap allocation in hot streaming paths; stack-allocated frames, vector header memcpy, and thread-local connection pools ensure consistent sub-millisecond turnarounds.

---

## 🏆 Verified `wrk` Benchmark Report

All measurements are officially conducted using **`wrk 4.2.0 [epoll]`** on an 8-core Linux system (`x86_64`, Intel Core i5-9300H @ 2.40GHz) across industrial sustained and burst scenarios.

---

### 🔍 What is `wrk` & How Does It Work?

[`wrk`](https://github.com/wg/wrk) is the modern gold-standard HTTP benchmarking tool in systems engineering. Unlike legacy utilities like ApacheBench (`ab`) which use synchronous blocking sockets, `wrk` is architected for extreme scale:

1. **Multi-Reactor Event Loops**: Each client worker thread runs its own dedicated non-blocking event loop (`epoll` on Linux, `kqueue` on macOS/BSD). A single `wrk` thread can effortlessly drive thousands of live, concurrent HTTP/1.1 connections without CPU overhead or thread contention.
2. **True Persistent Keep-Alive**: Reuses underlying TCP sockets continuously, streaming new requests the instant previous responses are received to measure true high-frequency proxy throughput.
3. **Microsecond Precision Timers**: Measures end-to-end socket round-trips using monotonic hardware timers, generating mathematically rigorous latency distributions (p50, p75, p90, p99, and maximum tail latency).
4. **Zero Client Bottlenecking**: Written in pure C with LuaJIT integration, `wrk` operates with near-zero runtime overhead, ensuring that benchmark numbers reflect the proxy's true capabilities rather than client-side throttling.

---

### 1. Sustained 5-Minute Industrial Endurance Soak Test (23.6M+ Requests)

Under non-stop continuous load for **5 full minutes (300 seconds)** across 200 persistent connections, we tested multi-reactor configurations:

| Metric | 4 Reactors (`-t 4`) | 8 Reactors (`-t 8`) | 10 Reactors (`-t 10`) 🏆 |
| :--- | :---: | :---: | :---: |
| **Test Duration** | 5m (300 seconds) | 5m (300 seconds) | **5m (300 seconds)** |
| **Total Requests Processed** | 15,480,029 | 23,619,416 | **25,397,612 reqs** |
| **Sustained Throughput** | 51,592.04 req/s | 78,729.48 req/s | **84,648.85 req/s** |
| **Network Transfer Rate** | 6.00 MB/s | 9.16 MB/s | **9.85 MB/s** |
| **Total Data Streamed** | 1.76 GB | 2.68 GB | **2.89 Gigabytes** |
| **Median Latency (p50)** | 3.60 ms | 2.42 ms | **2.16 ms** 🎯 |
| **99th Percentile (p99)** | 8.06 ms | 4.49 ms | **4.60 ms** |
| **Dropped / Failed Requests**| **0 (0.00%)** | **0 (0.00%)** | **0 (0.00%)** ✅ |
| **Memory Drift (30s → 300s)**| **0.00 MB** | **0.00 MB** | **0.00 MB (Flatline 10.38 MB RSS)** ✅ |

> 📖 **Full Architectural Reports**:
> - [5-Minute Sustained Soak Report (reports/SOAK_TEST_REPORT.md)](reports/SOAK_TEST_REPORT.md)
> - [Deep Stress & Resilience Battery (reports/STRESS_EXPERIMENTS_REPORT.md)](reports/STRESS_EXPERIMENTS_REPORT.md)
> - [Historical Optimization & Architecture Log (reports/OPTIMIZATION_LOG.md)](reports/OPTIMIZATION_LOG.md)

---

### 2. Throughput & Latency Profile Across Concurrency Levels

| Concurrency | Client Threads | Duration | Throughput (Req/s) | p50 Latency | p90 Latency | p99 Latency | Failed Reqs |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **100 conns** | 4 threads | 30s | **79,653.74 req/s** | 1.17 ms | 2.45 ms | 3.08 ms | **0** |
| **200 conns** | 8 threads | 30s | **77,180.20 req/s** | 2.48 ms | 3.82 ms | 5.12 ms | **0** |
| **200 conns (10 Reactors)** | 2 threads | 15s | **103,157.54 req/s** | 1.80 ms | 2.80 ms | 4.54 ms | **0** |
| **400 conns** | 8 threads | 15s | **88,090.30 req/s** | 4.36 ms | 6.12 ms | 7.33 ms | **0** |
| **2,000 conns** | 16 threads | 10s | **71,707.00 req/s** | 11.20 ms | 18.50 ms | 24.30 ms | **0** |

- **All-Time Peak Throughput**: **103,157.54 requests/sec** (1,548,551 completed requests in 15.01s with 0 socket errors).
- **Extreme Scale (400 conns)**: **1,321,354 requests** processed in 15 seconds with **100% success rate (0 failures)**.
- **Kernel Memory Footprint**: Remained flat at **~10.4 MB RSS** under full multi-worker saturation.

---

### 3. Rapid Connection Churn (`Connection: close`)

Evaluates performance under extreme connection churn where clients do not reuse connections and force continuous TCP connection handshakes and teardowns:

| Workload Configuration | Architecture | Churn Throughput | Socket Errors | Port Exhaustion Status |
| :--- | :---: | :---: | :---: | :---: |
| **Without Pool** | Fresh TCP socket per request | 14,325 req/sec | High (kernel limits) | Ephemeral port exhaustion (`TIME_WAIT`) |
| **With Thread-Local Pool** | Lock-free worker pool (`MAX 64`) | **37,948 req/sec (+165%)** | **0 errors (380k+ requests)** | **Zero port leaks (100% clean)** |

---

### 4. How to Reproduce Benchmarks Locally

You can replicate any of these benchmarks on Linux or macOS:

```bash
# 1. Start the ultra-fast mock upstream server (or your own backend)
node scripts/mock_upstream.js &

# 2. Launch Sankram in high-performance error-only log mode
./build/sankram -p 17777 -l error -t 10 &

# 3. Run a quick 30-second high-concurrency wrk benchmark
wrk -t 2 -c 200 -d 30s --latency "http://127.0.0.1:17777/?url=http://127.0.0.1:9099/"

# 4. Or run the automated 5-minute soak endurance test
./scripts/run_wrk_soak.sh 5m 200 2 10
```

---

## 📑 Table of Contents
- [Architecture Overview](#-architecture-overview)
- [The 6 Upstream Resilience & Protocol Milestones](#-the-6-upstream-resilience--protocol-milestones)
- [Key Features & Engineering Highlights](#-key-features--engineering-highlights)
- [Project Structure](#-project-structure)
- [Prerequisites & Build](#-prerequisites--build)
- [CLI Usage & Flags](#-cli-usage--flags)
- [Testing & Verification Harness](#-testing--verification-harness)
- [The Journey & Engineering Evolution](#-the-journey--engineering-evolution)
- [License](#-license)

---

## 🏛 Architecture Overview

The proxy uses the **Multi-Reactor Pattern with `SO_REUSEPORT`** (similar to modern ultra-high performance servers like NGINX and Envoy) to eliminate thread churn, context switching, and single-thread accept bottlenecks.

```text
                              [ Incoming Client Connections ]
                                             │
                       [ Linux Kernel SO_REUSEPORT Load Balancer ]
                        (Hardware/Kernel-space 4-tuple IP hashing)
                                             │
               ┌─────────────────────────────┼─────────────────────────────┐
               ▼                             ▼                             ▼
       [ Worker Thread #0 ]          [ Worker Thread #1 ]          [ Worker Thread #N-1 ]
      listen_fd + epoll_fd          listen_fd + epoll_fd          listen_fd + epoll_fd
               │                             │                             │
          epoll_wait()                  epoll_wait()                  epoll_wait()
               │                             │                             │
       ┌───────┴───────┐             ┌───────┴───────┐             ┌───────┴───────┐
       ▼               ▼             ▼               ▼             ▼               ▼
   accept()      session_handle   accept()      session_handle   accept()      session_handle
(New Clients)   (Keep-Alive Req) (New Clients)  (Keep-Alive Req) (New Clients)   (Keep-Alive Req)
       │               │             │               │             │               │
       ▼               ▼             ▼               ▼             ▼               ▼
  Plain HTTP /    OS-Native     Plain HTTP /    OS-Native     Plain HTTP /    OS-Native
   Stream (80)     TLS (443)     Stream (80)     TLS (443)     Stream (80)     TLS (443)
```

### 1. `SO_REUSEPORT` Parallel Worker Fleet
- Every worker thread creates and owns its **own private listening socket** bound to port 17777 using `SO_REUSEPORT`.
- **Zero Accept Bottleneck**: The kernel distributes incoming connections across all worker threads in kernel space directly at the socket layer.
- Workers sleep in kernel space (`epoll_wait` / `kevent` / `WSAPoll`) at 0% CPU until signaled with new client connections or incoming HTTP data.
- **Zero Lock Contention**: Workers accept, process, stream, and log connections independently with complete thread affinity.

### 2. In-Memory 2-Way Set-Associative DNS Cache
- **Thread-Local Lock-Free Cache**: Every worker thread maintains its own 2-way set-associative cache with 64 sets (128 slots total), eliminating cross-thread mutex contention.
- **32-Bit FNV-1a Hashing**: Computes rapid hash slots with case-insensitive ASCII folding.
- **TTL Expiration**: Expired entries automatically trigger fresh lookups upon expiry.
- **System Call Bypass**: DNS cache hits bypass glibc's blocking `getaddrinfo()` NSS file-reads completely, saving $\sim 0.3\text{ ms}$ per outbound connection.

### 3. Asynchronous Double-Buffering Logger ("Two Buckets Under a Tap")
- Worker threads **never perform blocking disk I/O**.
- Logging uses two 64 KB RAM buckets (`BUCKET_A` and `BUCKET_B`):
  - **The Tap (Producers)**: Worker threads format messages into stack buffers and copy them into `active_buffer` with a $\sim 20\text{-nanosecond}$ `memcpy`.
  - **The Janitor (Consumer)**: A dedicated background logging thread waits on a condition variable (`pthread_cond_wait`). When the active bucket fills up or the doorbell is signaled, it atomically swaps the two pointers (`char *temp = active; active = waiting; waiting = temp;`), unlocks the mutex immediately, and commits the full chunk to disk with `fwrite()` + `fflush()`.

### 4. Self-Healing 5-Slot Carousel Log Rotation
- **Zero Log Bloat**: Prevents runaway log files by bounding logging to a fixed 5-slot ring buffer (`logger_0.log` through `logger_4.log`) capped at 2 MB per file.
- **In-Band Active Marker (`@`)**: The currently active file is dynamically prefixed with `@` (e.g. `@logger_0.log`). When a slot reaches `MAX_FILE_SIZE`:
  1. It drops the `@` prefix via `rename()`.
  2. Advances slot index via boundary check `(current_slot + 1 >= FILE_COUNT) ? 0 : current_slot + 1`.
  3. Renames the target file to `@`, truncates previous contents with `fopen(..., "w")`, and opens the append stream.
- **Crash Recovery & Conflict Resolution**: On startup, `last_active_file()` scans `logs/` via `opendir()` and `readdir()`. If a prior crash left multiple `@` files, it calculates the true active slot across progression and wrap-around boundaries (`4 -> 0`), auto-heals by stripping the `@` from stale duplicates, and resumes appending with zero state loss.

---

## 🛡️ The 6 Upstream Resilience & Protocol Milestones

Sankram incorporates an industrial resilience and protocol compliance matrix verified by automated end-to-end integration tests:

| Target | Capability | Mechanism | Impact |
| :--- | :--- | :--- | :--- |
| **1. Stale Socket Auto-Retry** | Transparent Upstream Recovery | Detects remote socket drops on pooled connections; dials fresh TCP/TLS socket seamlessly | **Zero dropped requests** on stale pool connections |
| **2. HTTP Pipelining** | Multi-Request & Fragmented Frames | Shinks consumed frames via `memmove` and preserves buffer offsets across epoll turns | **100% ordered request/response multiplexing** |
| **3. Chunked Uploads** | Streaming Request Bodies | Zero-copy chunk boundary scanner detecting `0\r\n\r\n` without buffering entire payloads | **Unbounded file uploads** with flat memory usage |
| **4. WebSocket Tunnels** | RFC 6455 Full-Duplex Tunneling | Dynamic heap-allocated `tunnel_ctx` with streaming backpressure and HTTP 101 upgrade | Shrinks session size from **26.3 KB to 9.8 KB** (L3 cache residency) |
| **5. Slowloris Defense** | Aggregate Header Deadline | Enforces 3s aggregate header accumulation deadline with HTTP 408 Request Timeout | **Immune to trickle attacks**; lazy timing saves 1.9M clock syscalls |
| **6. In-Memory DNS Cache** | Thread-Local Set-Associative Cache | 2-way set-associative cache with 32-bit FNV-1a hashing & TTL expiration | Bypasses `getaddrinfo()`, enabling **103k+ RPS peak** |

---

## ✨ Key Features & Engineering Highlights

- **Hardware-Adaptive Auto-Configuration**: Queries the kernel with `sysconf(_SC_NPROCESSORS_ONLN)` to detect available CPU cores and spawns the optimal thread count automatically. Includes protection against user thread overload (`-t`) with automatic clamping.
- **Zero-Dependency Native TLS Stack**:
  - **Linux**: OpenSSL TLS 1.3 with Server Name Indication (SNI).
  - **macOS**: Native Apple Security Framework (`SecureTransport`) with Zero external OpenSSL dependencies.
  - **Windows**: Native Microsoft Schannel & CryptoAPI (`Secur32`) with Zero external dependencies.
- **RFC 7230 Compliant Header Rewriting**:
  - Automatically reconstructs clean upstream request lines.
  - Strips conflicting duplicate `Host` headers to prevent 400 Bad Request rejections on strict CDN frontends (e.g. GitHub, Cloudflare).
- **Chunked Transfer-Encoding Termination**:
  - Inspects incoming response bodies using binary memory comparisons (`memcmp`) to catch chunked termination sequences (`0\r\n\r\n`) across compressed gzip/binary streams without stalling on keep-alive socket timeouts.
- **Private Network Access (PNA) & CORS**:
  - Handles preflight `OPTIONS` requests natively, returning `204 No Content` with appropriate `Access-Control-Allow-*` and `Access-Control-Allow-Private-Network` headers.
- **Origin Whitelist Enforcement**:
  - Validates client `Origin` headers against configurable wildcard domain patterns (`-o`).

---

## 📁 Project Structure

```text
.
├── include/
│   ├── config.h        # Project constants (stack sizes, timeouts, proxy_config struct)
│   ├── dns_cache.h     # 2-way set-associative in-memory DNS cache with FNV-1a hashing
│   ├── http.h          # HTTP request/response structs, fast-path headers, status codes
│   ├── http_error.h    # RFC error response generators (400, 403, 404, 405, 408, 413, 500, 502)
│   ├── logger.h        # Asynchronous double-buffered logger API and levels (DEBUG..ERROR)
│   ├── net_compat.h    # Cross-platform socket abstraction (POSIX, Winsock2, Apple)
│   ├── poll_engine.h   # Unified non-blocking polling engine interface
│   ├── proxy.h         # Proxy connection lifecycle, streaming, and tunnel contexts
│   ├── server.h        # Socket lifecycle, timeout configuration, and accept handlers
│   ├── stress.h        # Multi-threaded native C stress engine configuration & runner
│   ├── tls.h           # Cross-platform TLS client wrappers and context lifecycle
│   ├── upstream.h      # Upstream HTTP request forwarding and body streaming
│   └── url.h           # URL parser (schema, host, port, path, query extraction)
├── src/
│   ├── main.c          # Entrypoint, Multi-Reactor worker fleet, signal supervisor
│   ├── config.c        # CLI argument parser (-p, -b, -t, -m, -l, -v, -u, -c, -n, -X, -d)
│   ├── dns_cache.c     # In-memory DNS cache lookup, insertion, and TTL invalidation
│   ├── http.c          # In-place HTTP header slicing and protocol parsing
│   ├── http_error.c    # Error page HTML generation with CORS headers
│   ├── logger.c        # Asynchronous double-buffering carousel logger thread
│   ├── poll_epoll.c    # Linux native epoll engine (EPOLLET edge-triggered)
│   ├── poll_kqueue.c   # macOS/BSD native kqueue engine (EVFILT_READ / EVFILT_WRITE)
│   ├── poll_wsapoll.c  # Windows native WSAPoll engine
│   ├── proxy.c         # HTTP pipeline, keep-alive reuse, WebSocket tunneling
│   ├── server.c        # BSD socket creation, non-blocking helpers, bind, listen
│   ├── stress.c        # Native C multi-threaded non-blocking stress benchmark engine
│   ├── tls.c           # Linux OpenSSL TLS implementation
│   ├── tls_darwin.c    # macOS Apple Security Framework (SecureTransport) implementation
│   ├── tls_schannel.c  # Windows Microsoft Schannel implementation
│   ├── upstream.c      # Outbound connection dialer, DNS cache integration, chunked streaming
│   └── url.c           # URL parsing and port validation
├── scripts/
│   ├── benchmark_50k.sh    # Automated 50,000+ Req/Sec end-to-end benchmark suite
│   ├── run_wrk_soak.sh     # Sustained multi-minute wrk endurance soak benchmark
│   ├── mock_upstream.py    # Zero-dependency Python 3 HTTP/1.1 mock upstream server
│   └── tests/
│       ├── run_all.py          # Unified Master Test Suite Orchestrator
│       ├── test_websocket.py   # WebSocket RFC 6455 & Full-Duplex Tunnel Test Suite
│       ├── test_functional.py  # HTTP Real-World Functional Matrix & 50-Req Parallel Burst
│       ├── test_rotation.py    # Live Carousel Log Rotation & Active Marker Audit
│       ├── test_fallback.py    # Upstream Fallback & Overflow Circuit-Breaker Resilience
│       └── test_resilience.py  # Stale Upstream Retry, Pipelining, Chunked, Slowloris, DNS
├── logs/               # Rotating carousel logs (@logger_X.log, logger_X.log)
├── build/              # Compiled binary outputs (sankram, sankram_small)
├── reports/            # Industrial soak, stress, and optimization reports
├── Makefile            # Universal cross-platform Makefile (Linux, macOS, Windows)
└── README.md           # Project documentation
```

---

## 🛠 Prerequisites & Build

The codebase is engineered to be **100% cross-platform**, multiplexing connections using the optimal kernel event engine for each operating system:
- **Linux**: Multi-Reactor `epoll` (`EPOLLET` + `SO_REUSEPORT`) + OpenSSL
- **macOS / BSD**: Native `kqueue` + Apple Security Framework (Zero external OpenSSL required)
- **Windows**: Native `WSAPoll` + Microsoft Schannel & CryptoAPI (Zero external dependencies)

---

### 🐧 Linux (Ubuntu / Debian / Fedora / Arch)

#### Prerequisites
- Compiler: `gcc` or `clang` (C11/GNU11)
- Libraries: OpenSSL (`libssl-dev`), POSIX Threads (`-pthread`)

```bash
# Ubuntu / Debian
sudo apt update && sudo apt install -y build-essential libssl-dev

# Fedora / RHEL
sudo dnf install -y gcc openssl-devel

# Arch Linux
sudo pacman -S base-devel openssl
```

#### Build with Make
```bash
make -j$(nproc)
```

#### Build Targets
- `make` — Compiles optimized production binary (`build/sankram`).
- `make small` — Compiles compact binary with size-optimization and symbol stripping (`build/sankram_small`).
- `make debug` — Builds with AddressSanitizer and UndefinedBehaviorSanitizer (`build/sankram_debug`).
- `make test` — Runs the Unified Master Test Suite across all 5 test batteries.
- `make clean` — Cleans all build artifacts and object files.
- `sudo make install` — Installs `sankram` to `/usr/local/bin/`.

---

### 🍏 macOS (Apple Silicon M1/M2/M3/M4 & Intel x86_64)

On macOS, the proxy automatically compiles with **native BSD `kqueue`** and **native Apple Security Framework** (`-framework Security -framework CoreFoundation`). No external OpenSSL installation is required!

```bash
# Compile for macOS (Apple Silicon & Intel)
make -j$(sysctl -n hw.ncpu)
make small -j$(sysctl -n hw.ncpu)
```

---

### 🪟 Windows (MSYS2 / MinGW-w64)

On Windows, the proxy automatically links against native Microsoft Windows system libraries (`ws2_32`, `secur32`, `crypt32`). No external OpenSSL or pthreads are required!

```bash
# In MSYS2 MinGW 64-bit terminal:
make -j
make small -j
```

---

### 📦 Minimal Size Binary (Embedded / MicroVM Mode)
For ultra-compact deployments (Raspberry Pi, Alpine, OpenWrt, microVMs), run `make small` to generate a **~55 KB standalone binary**:

```bash
make small
ls -lh build/sankram_small
# -rwxr-xr-x 1 user user 55K build/sankram_small
```

---

## 🚀 CLI Usage & Flags

### Start the Server (Defaults)
```bash
./build/sankram
```
*Defaults to port `17777`, listening on `127.0.0.1`, with worker threads auto-detected from online CPU cores.*

### Command-Line Options
```text
Usage: ./sankram -p <port> -b <ip> -t <threads> -m <server|stress|logs|help> -l <debug|info|warn|error> -v -o <origins>
       ./sankram -m stress -u <url> -c <concurrency> -n <requests> -t <threads> -X <method> -d <data>
```

| Flag | Long Option | Description | Default |
| :--- | :--- | :--- | :--- |
| `-p` | | Port to listen on (`1-65535`) | `17777` |
| `-b` | `--bind` | IP address to bind to | `127.0.0.1` |
| `-t` | `--threads` | Number of worker threads (clamped to hardware limits) | Auto (`sysconf`) |
| `-m` | `--mode` | Run mode (`server`, `logs`, `help`, `stress`) | `server` |
| `-l` | `--log-level` | Log verbosity (`debug`, `info`, `warn`, `error` or `d, i, w, e`) | `info` |
| `-o` | `--origin` | Comma-separated list of allowed CORS/PNA origins | `*` |
| `-v` | `--verbose` | Shortcut for `-l debug` | `false` |
| `-u` | `--url` | Target URL to benchmark (`-m stress`) | `http://127.0.0.1:17777/` |
| `-c` | `--concurrent` | Concurrency: number of parallel connections | `50` |
| `-n` | `--requests` | Total requests to execute (`-m stress`) | `10000` |
| `-X` | `--method` | Custom HTTP method (`GET`, `POST`, `PUT`, `DELETE`) | `GET` |
| `-d` | `--data` | HTTP payload / body for requests | *(empty)* |
| `-h` | `--help` | Display usage manual | |

### Examples
```bash
# 1. Start proxy on port 8080 with 8 worker threads and origin whitelist
./build/sankram -p 8080 -b 0.0.0.0 -t 8 -o "https://example.com,https://*.mycorp.internal" -v

# 2. Native C Stress Benchmark: 20,000 requests, 100 concurrent connections, 4 threads
./build/sankram -m stress -u http://127.0.0.1:17777/?url=http://127.0.0.1:9099/test -c 100 -n 20000 -t 4

# 3. High-throughput custom POST benchmark with JSON payload
./build/sankram -m stress -u http://127.0.0.1:9099/test -c 100 -n 10000 -X POST -d '{"speed":"c"}'

# 4. View formatted color-coded runtime access logs
./build/sankram -m logs
```

---

## 🧪 Testing & Verification Harness

Sankram includes a zero-dependency **Unified Master Test Suite** built entirely with Python 3 standard library:

```bash
# Run all 5 test suites in sequence
python3 scripts/tests/run_all.py
# or simply:
make test
```

### The 5 Unified Test Batteries

```text
==================================================================
             SANKRAM UNIFIED TEST SUITE SCORECARD                 
==================================================================
  [✔ PASS] WebSocket RFC 6455 & Full-Duplex Tunnel            (  0.78s)
  [✔ PASS] HTTP Functional Matrix & 50-Req Parallel Burst     (  1.79s)
  [✔ PASS] Log Carousel Rotation & Commit-Before-Retire       (  2.02s)
  [✔ PASS] Fallback & Overflow Circuit-Breaker Resilience     (  3.71s)
  [✔ PASS] Stale Upstream Auto-Retry & HTTP Pipelining        ( 18.97s)
------------------------------------------------------------------
  Total Duration: 27.27s
  Final Verdict : 100% GREEN — ALL SUITES PASSED!
==================================================================
```

1. **WebSocket Full-Duplex (`test_websocket.py`)**: Validates RFC 6455 upgrade handshakes, SHA-1 / Base64 Sec-WebSocket-Accept generation, full-duplex bidirectional frame echo, and graceful disconnects.
2. **HTTP Functional Matrix & Parallel Burst (`test_functional.py`)**: Tests real production targets (Google, Wikipedia, Hacker News, DuckDuckGo, Cloudflare API), method forwarding (`POST`, `OPTIONS`), and fires 50 simultaneous parallel bursts across CDNs.
3. **Carousel Log Rotation (`test_rotation.py`)**: Blasts traffic across 50 KB rotation thresholds, auditing the atomic `@` active marker migration and verifying zero log drops.
4. **Fallback & Circuit-Breaker Resilience (`test_fallback.py`)**: Validates default upstream routing (`localhost:3000`), permission drops (`chmod 555 logs/`), and verifies non-crashing overflow operation.
5. **Resilience & Pipelining Validation (`test_resilience.py`)**:
   - Stale pooled upstream auto-retry on server drops
   - Multi-request pipelining in a single TCP packet
   - Fragmented pipelining across epoll turns
   - Client chunked upload streaming (`Transfer-Encoding: chunked`)
   - WebSocket streaming backpressure under deliberate client read stalls (128 KB with 0 byte loss)
   - Slowloris defense terminating header trickle attacks with HTTP 408
   - In-memory DNS cache hit/miss and case-insensitive lookup

---

## 📖 The Journey & Engineering Evolution

This project was built from absolute scratch as a deep dive into systems programming, computer networking, and memory architectures:

1. **Low-Level BSD Sockets**: Understanding `socket()`, `setsockopt()`, `bind()`, `listen()`, `accept()`, and handling kernel interrupts like `SIGPIPE` (`signal(SIGPIPE, SIG_IGN)`).
2. **In-Place HTTP Parsing**: Parsing headers with raw pointer arithmetic, slicing request boundaries, and managing dynamic header arrays with `realloc`.
3. **OpenSSL TLS 1.3 Integration**: Managing `SSL_CTX`, wrapping socket descriptors with `SSL_set_fd()`, and learning the relationship between `void *` abstractions and cryptographic handshakes.
4. **The 256 KB Stack Discovery**: Diagnosing stack overflows during OpenSSL TLS handshakes and discovering why crypto threads require at least 256 KB stack allocations, while I/O threads can run on 32 KB.
5. **Asynchronous Double-Buffering Logger**: Inventing the "two buckets under a tap" model, coordinating thread synchronization with `pthread_mutex_t` and `pthread_cond_t`, and avoiding disk I/O bottlenecks.
6. **The Multi-Reactor Epoll Fleet**: Evolving from thread-per-connection to a fixed, core-pinned Epoll worker fleet, solving connection distribution, graceful termination timeouts, and binary chunked stream parsing (`memcmp`).
7. **The Self-Healing 5-Slot Carousel Logger**: Solving unbounded log growth with a fixed-ring carousel buffer, designing in-band `@` active marker tags without external metadata files, and building crash-resilient startup recovery using `opendir()`, `readdir()`, and wrap-around ring arithmetic.
8. **The 17,000+ Req/Sec Keep-Alive & `SO_REUSEPORT` Breakthrough**:
   - Replaced single-acceptor bottlenecks with kernel-level connection balancing across independent worker listening sockets.
   - Eliminated double-handshake overhead per request by keeping client sockets persistent (`session_reset()`) and caching open upstream TCP connections.
   - Diagnosed the 40ms latency freeze caused by Nagle's algorithm waiting on Linux's delayed ACK timer, resolving it with `TCP_NODELAY` and dropping latency from 41.9ms to 0.46ms (91x speedup).
9. **The Native C Stress Engine (27,000+ Req/Sec)**:
   - Built a pure C non-blocking stress client in `src/stress.c` reusing the core cross-platform abstraction `poll_engine` (`epoll`/`kqueue`/`WSAPoll`).
   - Partitioned connections and target request quotas evenly across worker threads with isolated event loops, avoiding all thread locking and mutex contention.
10. **The RFC 6455 Full-Duplex Tunnel & Dynamic Context Decoupling**:
    - Embedded 16 KB static WebSocket buffers originally caused `sizeof(struct client_session)` to balloon to 26.3 KB, causing 400 connections (10.5 MB) to spill out of the 8 MB L3 CPU cache.
    - Decoupled streaming rings onto dynamic `struct tunnel_ctx` allocated on demand upon WebSocket upgrade, shrinking session size to **9.8 KB** and ensuring 400 connections fit 100% inside the L3 CPU cache.
11. **In-Memory 2-Way Set-Associative DNS Cache**:
    - Thread-local lock-free 2-way set-associative DNS cache with 32-bit FNV-1a hashing, bypassing `getaddrinfo` NSS lookups and unlocking **88,090 RPS**.
12. **Transparent Upstream Resilience & Pipelining**:
    - Transparent auto-retry on stale keep-alive sockets without client-visible drops.
    - Preserved unconsumed pipeline buffers across epoll turns with boundary `memmove`.
13. **Lazy Slowloris Timing Defense**:
    - Enforced 3-second aggregate header accumulation deadlines without paying the cost of clock syscalls on the fast path.
14. **Breaking the 100,000+ Req/Sec Barrier**:
    - Reached an all-time record peak of **103,157.54 req/sec** with sub-1.8ms median latency, verified over 23.6 Million continuous requests with **0.00 MB memory drift**.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
