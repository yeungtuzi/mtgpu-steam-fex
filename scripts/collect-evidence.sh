#!/bin/bash
# Collect a timestamped evidence bundle for the M1000 Hollow Knight run.
# Run on the target as the desktop user, with Xorg :3 already showing the game.
#
#   scripts/collect-evidence.sh [seconds] [outdir]
#
# Produces: screenshots every 10s, process stats, Vulkan device summary,
# and a summary.txt with the DXVK HUD region cropped out for quick reading.
set -u
secs="${1:-60}"
out="${2:-${M1000_WORK_DIR:-$HOME/.local/share/m1000/work}/evidence-$(date +%Y%m%d-%H%M%S)}"
disp="${DISPLAY_OVERRIDE:-:3}"
mkdir -p "$out" || exit 1

export DISPLAY="$disp"
export XAUTHORITY="${XAUTHORITY:-}"

{
  echo "date: $(date -Is)"
  echo "display: $disp"
  echo "kernel: $(uname -r)"
  echo "gpu: $(ls /sys/class/drm/*/device/vendor 2>/dev/null | head -3)"
  echo "--- vulkan ---"
  (command -v vulkaninfo >/dev/null && vulkaninfo --summary 2>/dev/null | grep -E "deviceName|driverName|apiVersion" | head -8) || true
  echo "--- game process ---"
  ps -eo pid,pcpu,pmem,etime,rss,comm | grep -i hollow | grep -v grep || echo "not running"
  echo "--- windows ---"
  xwininfo -root -tree 2>/dev/null | grep -i hollow | head -3
} > "$out/summary.txt" 2>&1

i=0
while [ "$i" -lt "$secs" ]; do
  # import can block forever if the X server is suspended (VT switched away)
  timeout 15 import -window root "$out/shot-$(printf %03d "$i").png" 2>/dev/null || true
  ps -eo pcpu,etime,rss,comm | grep -i hollow | grep -v grep >> "$out/ps.log" || true
  i=$((i + 10)); [ "$i" -lt "$secs" ] && sleep 10
done

echo "$out"
