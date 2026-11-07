#!/bin/bash
# Run Hollow Knight on the Moore Threads M1000 through native arm64 Wine.
#
# Why this exists
# ---------------
#  * FEX/Proton fills the "x86_64 Windows" part, but the FEX Vulkan thunk does
#    not expose VK_KHR_surface to Wine's guest loader, so DXVK falls back to
#    llvmpipe.  Proton 11 (ARM64) ships a native arm64 Wine instead: DXVK then
#    talks to the host Vulkan loader directly and sees the M1000.
#  * KWin/Wayland's rootless Xwayland does not map Wine toplevel windows on this
#    machine, and it cannot switch display modes.  A dedicated Xorg server on a
#    spare VT (modesetting on mt-igpu) provides both.
#  * Unity insists on exclusive fullscreen.  The bundled DXVK 2.3.1 build in
#    /opt/steamos/src/dxvk-2.3.1 is patched to keep the swapchain windowed.
#
# Everything user-visible lives under /opt/steamos.  The only system writes are
# the packages listed in INSTALL-MANIFEST.tsv.
#
# Usage:
#   scripts/run-hk-m1000.sh            # start Xorg :3 if needed, then the game
#   scripts/run-hk-m1000.sh --stop     # stop game + Xorg :3
#   scripts/run-hk-m1000.sh --shot FILE # screenshot the game display + exit

set -euo pipefail

PROTON="${PROTON:-/opt/steamos/steam/steamapps/common/Proton 11.0 (ARM64)}"
GAME="${GAME:-/opt/steamos/steam/steamapps/common/Hollow Knight}"
PREFIX="${PREFIX:-/opt/steamos/steam/steamapps/compatdata/367520/pfx-arm64}"
DISPLAY_NUM="${DISPLAY_NUM:-:3}"
VT="${VT:-8}"
XORG_CONF="${XORG_CONF:-/opt/steamos/xorg-m1000.conf}"

# Xorg- and Wine-side tuning
export DISPLAY="$DISPLAY_NUM"
export XAUTHORITY=
export XDG_RUNTIME_DIR=/run/user/1000
export WINEPREFIX="$PREFIX"
export WINESERVER="$PROTON/files/bin-arm64/wineserver"
export WINEDLLPATH="$PROTON/files/lib/wine"
export LD_LIBRARY_PATH="$PROTON/files/lib/aarch64-linux-gnu:$PROTON/files/lib:${LD_LIBRARY_PATH:-}"
export DXVK_HUD="${DXVK_HUD:-fps,devinfo}"
export SteamAppId="${SteamAppId:-367520}"
export SteamGameId="${SteamGameId:-367520}"

# Best-effort SteamAPI bridge: without it SteamAPI_Init() fails and the
# achievements UI throws, which confuses in-game navigation.
if [ -f /opt/steamos/steam/steamclient64.dll ]; then
    cp -n /opt/steamos/steam/steamclient64.dll \
        "$PREFIX/drive_c/windows/system32/steamclient64.dll" 2>/dev/null || true
fi

game_pids() {
    # deliberately not pkill -f: never match the caller's own command line
    pgrep -x hollow_knight.e 2>/dev/null || true
}

stop_all() {
    pids=$(game_pids)
    if [ -n "$pids" ]; then
        # shellcheck disable=SC2086
        kill $pids 2>/dev/null || true
        sleep 2
    fi
    keeper=$(pgrep -f "keep[-]focus.sh ${DISPLAY_NUM}" 2>/dev/null | head -1 || true)
    [ -n "$keeper" ] && kill "$keeper" 2>/dev/null || true
    pkill -x wineserver 2>/dev/null || true
    xorg_pid=$(pgrep -f "Xorg ${DISPLAY_NUM} " 2>/dev/null | head -1 || true)
    if [ -n "$xorg_pid" ]; then
        sudo kill "$xorg_pid" 2>/dev/null || true
    fi
}

if [ "${1:-}" = "--stop" ]; then
    stop_all
    echo "stopped"
    exit 0
fi

if [ "${1:-}" = "--shot" ]; then
    out="${2:?usage: $0 --shot FILE}"
    DISPLAY="$DISPLAY_NUM" import -window root "$out"
    echo "$out"
    exit 0
fi

# 1. Dedicated Xorg on the M1000 (modesetting/KMS) ---------------------------
if ! DISPLAY="$DISPLAY_NUM" xdpyinfo >/dev/null 2>&1; then
    echo "starting Xorg $DISPLAY_NUM on vt$VT"
    sudo setsid Xorg "$DISPLAY_NUM" "vt$VT" -config "$XORG_CONF" -noreset -nolisten tcp \
        -logfile "$WORK/xorg-m1000.log" >/dev/null 2>&1 &
    for _ in $(seq 1 30); do
        DISPLAY="$DISPLAY_NUM" xdpyinfo >/dev/null 2>&1 && break
        sleep 0.5
    done
fi
DISPLAY="$DISPLAY_NUM" xdpyinfo >/dev/null 2>&1 || {
    echo "Xorg $DISPLAY_NUM failed; see $WORK/xorg-m1000.log" >&2
    exit 1
}

# 2. Game --------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
cd "$GAME"
"$PROTON/files/bin-arm64/wine" hollow_knight.exe \
    -screen-fullscreen 0 -screen-width 1920 -screen-height 1080 &
wine_pid=$!

# Without a WM the window never gets focus and Unity throttles to ~1 FPS.
"$HERE/keep-focus.sh" "$DISPLAY_NUM" &
keeper_pid=$!
trap 'kill "$keeper_pid" 2>/dev/null || true' EXIT INT TERM
wait "$wine_pid"
kill "$keeper_pid" 2>/dev/null || true
