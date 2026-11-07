#!/bin/bash
# Keep the Hollow Knight window focused on the dedicated Xorg display.
#
# Without a window manager Unity treats the game as "in background" and
# throttles it to ~1 FPS, which also makes menu input appear to be ignored.
# Unity recreates its window on scene changes, so re-query the id every pass.
set -u
disp="${1:-:3}"
while :; do
    w=$(DISPLAY="$disp" xdotool search --name "Hollow Knight" 2>/dev/null | tail -1)
    if [ -n "$w" ]; then
        DISPLAY="$disp" xdotool windowfocus --sync "$w" 2>/dev/null || true
    fi
    sleep 5
done
