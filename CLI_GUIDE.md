# ⚡ Sankram (संक्रम) — Complete CLI Flags & Command Guide

A blunt, no-fluff guide to every single CLI flag in Sankram, what it does, why it exists, and copy-paste examples.

---

## 🚀 Quick Cheat Sheet

| Flag | Long Flag | Default | What it Does in Plain English |
|---|---|---|---|
| **`-b`** | `--bind <ip>` | `127.0.0.1` | **Where to listen.** Use `0.0.0.0` for Docker/network, `127.0.0.1` for local only. |
| **`-p`** | `--port <num>` | `17777` | **Port to listen on.** e.g., `-p 80` or `-p 8080`. |
| **`-s`** | `--static <dir>` | *(none)* | **Static frontend directory.** e.g., `-s ./dist` to serve React/Vue frontend files. |
| **`--spa`** | *(none)* | `false` | **SPA Route Fallback.** Makes `/dashboard` serve `index.html` instead of 404. |
| **`-o`** | `--origin <list>`| `*` | **CORS Allowed Origins.** Whitelist domains, e.g. `-o https://api-os.pages.dev`. |
| **`-t`** | `--threads <num>`| `Online Cores` | **Worker threads.** Number of symmetric epoll/kqueue event loops. |
| **`-l`** | `--log-level` | `info` | **Logging verbosity:** `debug`, `info`, `warn`, or `error`. |
| **`-m`** | `--mode <mode>` | `server` | **Program mode:** `server` (proxy), `stress` (benchmarking), or `logs`. |
| **`-v`** | `--verbose` | `false` | **Verbose mode:** Prints extra boot diagnostics. |
| **`--spawn-config`** | *(none)* | — | **Generate template:** Creates a default `proxy.conf` file on disk. |

---

## 🛠️ Server & Static File Mode (Detailed)

### 1. `-b`, `--bind <ip>`
* **What it does:** Tells the Linux kernel which network interface to attach to.
* **Why it matters:**
  * `127.0.0.1` (*default*): **Localhost only.** Safe for local development so nobody on your Wi-Fi can access it.
  * `0.0.0.0`: **All network interfaces.** **REQUIRED in Docker!** Inside a Docker container, if you don't bind to `0.0.0.0`, port forwarding (`-p 8080:80`) will fail with *Connection reset by peer*.
* **Example:**
  ```bash
  ./build/sankram -b 0.0.0.0 -p 80
  ```

---

### 2. `-p`, `--port <port>`
* **What it does:** The TCP port number where Sankram listens for incoming requests.
* **Example:**
  ```bash
  ./build/sankram -p 8080
  ```

---

### 3. `-s`, `--static <folder>`
* **What it does:** Turns Sankram into an ultra-fast static web server (like Nginx).
* **How it works:** Uses Linux kernel zero-copy `sendfile` to stream files directly from disk to client sockets without copying to user-space memory.
* **Example:**
  ```bash
  ./build/sankram -p 80 -s ./dist
  ```

---

### 4. `--spa`
* **What it does:** Single Page Application (SPA) routing fallback for React, Vue, Vite, Next export.
* **Why it matters:** In client-side routing (React Router), URLs like `/dashboard` or `/profile` don't exist as actual `.html` files on disk. Without `--spa`, refreshing the page gives 404. With `--spa`, Sankram returns `index.html` with HTTP 200 so React Router handles the route.
* **Example:**
  ```bash
  ./build/sankram -s ./dist --spa
  ```

---

### 5. `-o`, `--origin <origins>`
* **What it does:** Restricts Cross-Origin Resource Sharing (CORS) to specific domains.
* **Why it matters:** Injects `Access-Control-Allow-Origin` and handles browser `OPTIONS` preflight checks. You can pass multiple comma-separated domains.
* **Example:**
  ```bash
  ./build/sankram -o "https://api-os.pages.dev,https://myapp.com"
  ```

---

### 6. `-t`, `--threads <number>`
* **What it does:** Number of worker threads to spawn.
* **How it works:** Each thread runs its own private `epoll` (Linux) or `kqueue` (macOS) reactor sharing the listening socket via `SO_REUSEPORT` with lock-free connection dispatching. Defaults to your machine's CPU core count.
* **Example:**
  ```bash
  ./build/sankram -t 16
  ```

---

### 7. `-l`, `--log-level <debug|info|warn|error>`
* **What it does:** Controls how noisy the terminal output is.
  * `debug`: Prints every incoming connection, packet bytes, and DNS cache lookups.
  * `info`: Prints major server milestones and request counts.
  * `warn`: Stays quiet unless something abnormal happens (perfect for Docker production).
  * `error`: Only fatal errors and crashes.
* **Example:**
  ```bash
  ./build/sankram -l warn
  ```

---

## 🔥 Built-in Stress Testing Mode (`-m stress`)

Sankram has an ultra-high performance load generator built right inside the binary (like `wrk` or `autocannon`), so you don't need third-party tools to test your APIs.

| Flag | Description | Default | Example |
|---|---|---|---|
| **`-m stress`** | Activates stress benchmarking engine | — | `-m stress` |
| **`-u <url>`** | Target HTTP/HTTPS endpoint to hammer | *(required)* | `-u http://127.0.0.1:3000/api` |
| **`-n <num>`** | Total requests to complete | `1000` | `-n 50000` |
| **`-c <num>`** | Concurrent active connections | `10` | `-c 100` |
| **`-t <num>`** | Number of client benchmark threads | `4` | `-t 8` |
| **`-X <method>`**| HTTP method (`GET` or `POST`) | `GET` | `-X POST` |
| **`-d <data>`** | JSON/String body payload for POST | `""` | `-d '{"test":true}'` |

### **Stress Example:**
Fire 50,000 requests with 100 concurrent connections across 8 threads:
```bash
./build/sankram -m stress -u "http://127.0.0.1:8080/" -n 50000 -c 100 -t 8
```

---

## 📋 Top 3 Copy-Paste Recipes

### 1. Production Docker Frontend (Drop-in Nginx)
```bash
sankram -b 0.0.0.0 -p 80 -s ./dist --spa -l warn
```

### 2. Local Reverse Proxy to Node.js Backend (Port 3000) with CORS
```bash
./build/sankram -p 8080 -o "https://api-os.pages.dev" -l debug
```

### 3. Full-Stack Bundle (Serve Static Files + Fallback API to Port 3000)
```bash
./build/sankram -p 8080 -s ./dist -l info
```
*(If a file exists in `./dist`, Sankram serves it. If not, it automatically forwards to `127.0.0.1:3000`!)*

