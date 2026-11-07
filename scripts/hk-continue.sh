#!/bin/bash
# Click through the main menu into the first save slot on the :3 session.
# Requires: the game is running on :3 and a WM (mutter) is up, plus a
# user1.dat save in the prefix (see docs/TESTING.md).
set -eu
disp="${DISPLAY_NUM:-:3}"
export DISPLAY="$disp" XAUTHORITY=
w=$(xdotool search --name "Hollow Knight" 2>/dev/null | tail -1)
[ -n "$w" ] || { echo "game window not found on $disp" >&2; exit 1; }

# START GAME (text row) then the KING'S PASS slot; xdotool clicks are
# unreliable while Unity is unfocused, so retry a couple of times.
for _ in 1 2 3; do
    xdotool mousemove 960 664; sleep 0.4; xdotool click 1; sleep 6
done
for _ in 1 2 3; do
    xdotool mousemove 800 330; sleep 0.4; xdotool click 1; sleep 20
done
echo "continued in save slot 1"
