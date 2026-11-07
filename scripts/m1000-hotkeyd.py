#!/usr/bin/env python3
"""Watch physical keyboards for Meta+Shift+G and leave M1000 game mode.

Runs as root (needs /dev/input/event*); the game-mode script itself is run as
the desktop user so it can reach the session D-Bus and KWin.
"""
import glob
import os
import select
import struct
import subprocess
import time

EV_KEY = 1
KEY_LEFTSHIFT = 42
KEY_RIGHTSHIFT = 54
KEY_LEFTMETA = 125
KEY_RIGHTMETA = 126
KEY_G = 34
USER = "lf"

devices = {}   # path -> fd
state = {}     # path -> set of pressed keys
last_fire = 0.0


def run_stop():
    global last_fire
    now = time.time()
    if now - last_fire < 2.0:
        return
    last_fire = now
    subprocess.run(
        ["setpriv", "--reuid=1000", "--regid=1000", "--init-groups",
         "env", "HOME=/home/lf", "USER=lf", "LOGNAME=lf",
         "XDG_RUNTIME_DIR=/run/user/1000",
         "WAYLAND_DISPLAY=wayland-1",
         "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus",
         "DISPLAY=:0",
         "/opt/steamos/bin/game-mode", "stop"],
        check=False,
    )


def rescan():
    for path in glob.glob("/dev/input/event*"):
        if path in devices:
            continue
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        except OSError:
            continue
        devices[path] = fd
        state[path] = set()


def main():
    while True:
        rescan()
        fds = list(devices.values())
        if not fds:
            time.sleep(2)
            continue
        try:
            ready, _, _ = select.select(fds, [], [], 2.0)
        except OSError:
            ready = []
        for path, fd in list(devices.items()):
            if fd not in ready:
                continue
            try:
                data = os.read(fd, 24 * 64)
            except OSError:
                os.close(fd)
                devices.pop(path, None)
                state.pop(path, None)
                continue
            for off in range(0, len(data) - 23, 24):
                _s, _us, etype, code, value = struct.unpack_from("llHHi", data, off)
                if etype != EV_KEY:
                    continue
                keys = state.setdefault(path, set())
                if value == 1:
                    keys.add(code)
                    mods = {KEY_LEFTMETA, KEY_RIGHTMETA} & keys
                    shift = {KEY_LEFTSHIFT, KEY_RIGHTSHIFT} & keys
                    if code == KEY_G and mods and shift:
                        run_stop()
                elif value == 0:
                    keys.discard(code)


if __name__ == "__main__":
    main()
