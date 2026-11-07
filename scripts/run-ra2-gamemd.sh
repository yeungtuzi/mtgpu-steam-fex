#!/bin/bash
# Run RA2/Reunion gamemd (32-bit) through FEX + Proton Experimental x86_64 Wine.
# Defaults to a dedicated Xorg :3 because KWin rootless XWayland does not map
# Wine toplevel windows on this box (same reason as the Hollow Knight wrapper).
#
# Usage: run-ra2-gamemd.sh [gamemd-spawn.exe|gamemd.exe] [extra wine args]
# Env:   M1000_DISPLAY=:3  M1000_PREFIX=...  RA2_GAME_DIR=...
set -u
S=/opt/steamos/steam/steamapps/common
P="${M1000_PROTON:-$S/Proton - Experimental}"
GAME="${RA2_GAME_DIR:-/home/lf/文档/ra2reunion/Run}"
WORK="${M1000_WORK_DIR:-$HOME/.local/share/m1000/work}"
DISP="${M1000_DISPLAY:-:3}"
PREFIX="${M1000_PREFIX:-$WORK/ra2-proton/pfx2}"
LOG="$WORK/ra2-x3.log"
mkdir -p "$WORK"
exec >>"$LOG" 2>&1
echo "=== $(date -Is) display=$DISP exe=${1:-gamemd-spawn.exe} prefix=$PREFIX"

export DISPLAY="$DISP" XDG_RUNTIME_DIR=/run/user/1000
if [ "$DISP" = ":0" ]; then
    export XAUTHORITY="${XAUTHORITY:-$(ls /run/user/1000/xauth_* 2>/dev/null | head -1)}"
else
    export XAUTHORITY=
fi
export WINEPREFIX="$PREFIX"
export WINEDLLPATH="$P/files/lib/wine/x86_64-windows:$P/files/lib/wine/i386-windows"
export LD_LIBRARY_PATH="$P/files/lib/x86_64-linux-gnu:$P/files/lib/i386-linux-gnu:$P/files/lib:${LD_LIBRARY_PATH:-}"
export WINEDLLOVERRIDES="ddraw=n${WINEDLLOVERRIDES:+;$WINEDLLOVERRIDES}"
export FEX_TSOENABLED="${FEX_TSOENABLED:-0}"
export STEAM_COMPAT_CLIENT_INSTALL_PATH=/opt/steamos/steam

if [ "$DISP" != ":0" ] && [ "${M1000_NO_XORG:-0}" != "1" ]; then
    if ! xdpyinfo >/dev/null 2>&1; then
        sudo -n setsid Xorg "$DISP" vt8 -config /opt/steamos/xorg-m1000.conf \
            -noreset -nolisten tcp -logfile "$WORK/xorg-m1000.log" >/dev/null 2>&1 &
        for _ in $(seq 1 40); do xdpyinfo >/dev/null 2>&1 && break; sleep 0.5; done
        sudo -n chvt 8 2>/dev/null || true
    fi
    if ! pgrep -x mutter >/dev/null 2>&1; then
        setsid mutter --replace >/dev/null 2>&1 &
        sleep 2
    fi
fi

cd "$GAME" || exit 1
exe="${1:-gamemd-spawn.exe}"; shift || true
exec "$S/FEX-Emu/usr/bin/FEX" "$P/files/bin/wine" "$exe" "$@"
