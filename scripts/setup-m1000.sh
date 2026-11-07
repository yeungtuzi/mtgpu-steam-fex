#!/bin/bash
# Prepare the M1000 (Moore Threads) native-Vulkan path under /opt/steamos.
#
#   sudo scripts/setup-m1000.sh [--save FILE] [--patched-dxvk DIR]
#
# - installs config/xorg-m1000.conf as /opt/steamos/xorg-m1000.conf (and
#   records it in INSTALL-MANIFEST.tsv);
# - puts a DXVK 2.3.1 build into the Hollow Knight prefix (DXVK 2.7 reports
#   "No adapters found" on the M1000).  Stock 2.3.1 comes from Proton 8;
#   --patched-dxvk points at a self-built DXVK that keeps the swapchain windowed;
# - optionally installs a save file so the game can skip the crashing
#   Opening_Sequence.
set -euo pipefail

PREFIX="${PREFIX:-/opt/steamos/steam/steamapps/compatdata/367520/pfx-arm64}"
PROTON8="${PROTON8:-/opt/steamos/steam/steamapps/common/Proton 8.0}"
STEAM="${STEAM:-/opt/steamos/steam}"
HERE=$(cd "$(dirname "$0")" && pwd)
CONFIG_DIR="${CONFIG_DIR:-$HERE/../config}"
SAVE=""
PATCHED=""

while [ $# -gt 0 ]; do
    case "$1" in
        --save) SAVE="${2:?}"; shift 2 ;;
        --patched-dxvk) PATCHED="${2:?}"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

# 1. Xorg config + billing ---------------------------------------------------
install -m 0644 "$CONFIG_DIR/xorg-m1000.conf" /opt/steamos/xorg-m1000.conf
manifest=/opt/steamos/INSTALL-MANIFEST.tsv
if ! grep -qF "/opt/steamos/xorg-m1000.conf" "$manifest" 2>/dev/null; then
    printf 'file\t%s\t%s\n' /opt/steamos/xorg-m1000.conf \
        "$(sha256sum /opt/steamos/xorg-m1000.conf | cut -d' ' -f1)" >> "$manifest"
fi

# 2. DXVK 2.3.1 into the prefix ---------------------------------------------
system32="$PREFIX/drive_c/windows/system32"
[ -d "$system32" ] || { echo "prefix not found: $PREFIX" >&2; exit 1; }
if [ -n "$PATCHED" ]; then
    src="$PATCHED"
else
    src="$PROTON8/dist/lib64/wine/dxvk"
fi
for f in d3d11.dll dxgi.dll; do
    [ -f "$src/$f" ] || { echo "missing $src/$f" >&2; exit 1; }
    cp -n "$system32/$f" "$system32/$f.patched.bak" 2>/dev/null || true
    install -m 0644 "$src/$f" "$system32/$f"
    echo "installed $f from $src"
done

# 3. Optional save (skips the crashing intro) --------------------------------
if [ -n "$SAVE" ]; then
    dest="$PREFIX/drive_c/users/steamuser/AppData/LocalLow/Team Cherry/Hollow Knight"
    mkdir -p "$dest"
    install -m 0644 "$SAVE" "$dest/user1.dat"
    echo "installed save as $dest/user1.dat"
fi

echo
echo "next:"
echo "  scripts/run-hk-m1000.sh          # start Xorg :3 + game"
echo "  scripts/hk-continue.sh           # click START GAME -> save slot 1"
