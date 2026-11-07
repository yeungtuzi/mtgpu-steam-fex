#!/bin/bash
# M1000 game mode: switch KDE to the panel's native 1280x720 mode, open Steam
# Big Picture, and restore the previous mode/scale on exit.
set -u

CFG="$HOME/.config/kwinoutputconfig.json"
BAK="$HOME/.config/kwinoutputconfig.json.m1000bak"
STATE="$HOME/.config/m1000-gamemode.state"
LOG="$HOME/.config/m1000-gamemode.log"
KSD="/opt/kde6/bin/kscreen-doctor"
STEAM_BIN="/opt/steamos/steam/steamrtarm64/steam"
OUT="eDP-1"
WATCHDOG=20

log() { echo "$(date -Is) $*" >>"$LOG"; }

env_session() {
    export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/1000}"
    export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-1}"
    export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=/run/user/1000/bus}"
    export DISPLAY="${DISPLAY:-:0}"
    if [ -z "${XAUTHORITY:-}" ]; then
        XAUTHORITY=$(ls /run/user/1000/xauth_* 2>/dev/null | head -1)
        export XAUTHORITY
    fi
}

ks() { env_session; "$KSD" "$@" >/dev/null 2>&1; }

current_mode_index() {
    env_session
    "$KSD" -o 2>/dev/null | sed 's/\x1b\[[0-9;]*m//g' | tr ' ' '\n' | grep -oE '^[0-9]+:[^ ]*\*' | head -1 | cut -d: -f1
}

current_scale() {
    env_session
    "$KSD" -o 2>/dev/null | sed 's/\x1b\[[0-9;]*m//g' | grep -m1 'Scale:' | grep -oE '[0-9.]+' | head -1
}

start() {
    local confirm="${1:-}"
    if [ -f "$STATE" ]; then
        log "already in game mode"
        return 0
    fi
    [ -f "$CFG" ] && [ ! -f "$BAK" ] && cp -f "$CFG" "$BAK"

    local m s
    m=$(current_mode_index); s=$(current_scale)
    [ -n "$m" ] || { log "cannot detect current mode"; return 1; }
    printf 'MODE=%s\nSCALE=%s\n' "$m" "$s" >"$STATE"

    ks "output.$OUT.mode.13" "output.$OUT.scale.1.0"
    log "switched to 1280x720 (mode13) scale 1.0; previous mode=$m scale=$s"

    env_session
    if pgrep -x steam >/dev/null 2>&1; then
        "$STEAM_BIN" steam://open/bigpicture >/dev/null 2>&1 &
    else
        "$STEAM_BIN" -bigpicture >/dev/null 2>&1 &
    fi
    log "steam big picture requested"

    if [ "$confirm" = "--confirm" ]; then
        : >"$STATE.keep"
        log "watchdog disabled for this session"
    else
        rm -f "$STATE.keep"
        nohup setsid bash -c "sleep $WATCHDOG; [ -f '$STATE' ] && [ ! -f '$STATE.keep' ] && '$0' stop --auto" >/dev/null 2>&1 &
        log "watchdog armed: auto-restore in ${WATCHDOG}s unless confirmed"
    fi
}

stop() {
    local reason="${1:-manual}"
    if [ ! -f "$STATE" ]; then
        log "not in game mode"
        return 0
    fi
    # shellcheck disable=SC1090
    . "$STATE"
    ks "output.$OUT.mode.${MODE:-1}" "output.$OUT.scale.${SCALE:-2}"
    rm -f "$STATE" "$STATE.keep"
    log "restored mode=${MODE:-1} scale=${SCALE:-2} ($reason)"
}

status() {
    if [ -f "$STATE" ]; then
        echo "game-mode: active ($(tr '\n' ' ' <"$STATE"))"
    else
        echo "game-mode: inactive"
    fi
}

case "${1:-status}" in
    start) shift || true; start "${1:-}" ;;
    stop) shift || true; stop "${1:-manual}" ;;
    status) status ;;
    *) echo "usage: $0 {start [--confirm]|stop|status}"; exit 2 ;;
esac
