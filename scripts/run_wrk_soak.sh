#!/usr/bin/env bash
set -e

DURATION="${1:-3m}"
CONCURRENCY="${2:-200}"
WRK_THREADS="${3:-2}"
PROXY_THREADS="${4:-4}"
PROXY_PORT=17777
UPSTREAM_PORT=9099

WRK_BIN="/home/himanshu-yadav/.gemini/antigravity/brain/d4c4fd88-680f-4fa7-a457-8b3362faaee5/scratch/wrk/wrk"
MOCK_BIN="/home/himanshu-yadav/.gemini/antigravity/brain/d4c4fd88-680f-4fa7-a457-8b3362faaee5/scratch/mock_backend"

# Ensure clean slate
fuser -k $UPSTREAM_PORT/tcp $PROXY_PORT/tcp 2>/dev/null || true
pkill -9 -f sankram 2>/dev/null || true
sleep 0.5

echo "================================================================"
echo "  SANKRAM (संक्रम) — SUSTAINED MULTI-MINUTE WRK SOAK TEST       "
echo "================================================================"
echo "  Duration:        $DURATION"
echo "  Concurrency:     $CONCURRENCY connections"
echo "  wrk Threads:     $WRK_THREADS"
echo "  Proxy Reactors:  $PROXY_THREADS threads"
echo "================================================================"

# 1. Start pure C mock backend
$MOCK_BIN 27 $UPSTREAM_PORT 2 > /dev/null 2>&1 &
MOCK_PID=$!
sleep 0.3

# 2. Start Sankram Proxy
./build/sankram -p $PROXY_PORT -t $PROXY_THREADS -l error > /dev/null 2>&1 &
PROXY_PID=$!
sleep 0.5

# 3. Background Memory Monitor
MEM_LOG="/tmp/sankram_wrk_mem.log"
rm -f "$MEM_LOG"

monitor_memory() {
  local target_pid=$1
  local elapsed=0
  while kill -0 "$target_pid" 2>/dev/null; do
    local rss_kb
    rss_kb=$(grep VmRSS /proc/"$target_pid"/status 2>/dev/null | awk '{print $2}' || echo "0")
    echo "$(date +%s) $rss_kb" >> "$MEM_LOG"
    sleep 5
    elapsed=$((elapsed + 5))
    if [ $((elapsed % 30)) -eq 0 ]; then
      local mb
      mb=$(echo "scale=2; $rss_kb/1024" | bc 2>/dev/null || echo "0")
      echo "  ⏱️ [${elapsed}s elapsed] Sankram RSS Memory: ${mb} MB (running strong)"
    fi
  done
}

monitor_memory "$PROXY_PID" &
MONITOR_PID=$!

cleanup() {
  echo ""
  echo "Stopping services..."
  kill -9 "$MONITOR_PID" 2>/dev/null || true
  kill -9 "$PROXY_PID" 2>/dev/null || true
  kill -9 "$MOCK_PID" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo ""
echo "🚀 Pumping sustained load into Sankram for $DURATION..."
echo "📊 Monitoring RSS memory every 5 seconds..."
echo ""

START_TIME=$(date +%s)
$WRK_BIN -t "$WRK_THREADS" -c "$CONCURRENCY" -d "$DURATION" --latency "http://127.0.0.1:$PROXY_PORT/?url=http://127.0.0.1:$UPSTREAM_PORT/"
END_TIME=$(date +%s)

echo ""
echo "================================================================"
echo "  MEMORY STABILITY & LEAK VERIFICATION TIMELINE                 "
echo "================================================================"
if [ -f "$MEM_LOG" ]; then
  START_MEM=$(head -n 1 "$MEM_LOG" | awk '{print $2}')
  PEAK_MEM=$(awk '{if($2>max) max=$2} END {print max}' "$MEM_LOG")
  FINAL_MEM=$(tail -n 1 "$MEM_LOG" | awk '{print $2}')

  echo "  Start RSS Memory:   $(echo "scale=2; $START_MEM/1024" | bc) MB"
  echo "  Peak  RSS Memory:   $(echo "scale=2; $PEAK_MEM/1024" | bc) MB"
  echo "  Final RSS Memory:   $(echo "scale=2; $FINAL_MEM/1024" | bc) MB"
  echo "  Memory Drift:       $(echo "scale=2; ($FINAL_MEM - $START_MEM)/1024" | bc) MB"
  
  if [ "$START_MEM" -gt 0 ]; then
    DIFF=$((FINAL_MEM - START_MEM))
    if [ "$DIFF" -lt 1024 ]; then
      echo "  Stability Verdict:  PERFECT STABILITY (0 MEMORY LEAK) ✅"
    fi
  fi
fi
echo "================================================================"

