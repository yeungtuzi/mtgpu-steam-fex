#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""One-shot Steam bootstrap (`steam -deckard -exitsteam`) for steam-fex-arm64.

Runs as the desktop user, in the user's graphical session.  Temporarily
disables any x86 binfmt handlers so Steam uses its own bundled FEX (same
approach as Armbian's installer).
"""

from __future__ import annotations

import argparse
import os
import pwd
import re
import subprocess
import sys
from pathlib import Path


def log(msg: str) -> None:
    print(f"[bootstrap] {msg}", flush=True)


def session_env(user: str) -> dict[str, str]:
    env: dict[str, str] = {}
    uid = pwd.getpwnam(user).pw_uid
    runtime = Path(f"/run/user/{uid}")
    if runtime.is_dir():
        env["XDG_RUNTIME_DIR"] = str(runtime)
        if (runtime / "bus").is_socket():
            env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={runtime}/bus"
    for line in subprocess.run(["loginctl", "list-sessions", "--no-legend"], capture_output=True, text=True).stdout.splitlines():
        sid = line.split()[0] if line.split() else ""
        if not sid:
            continue
        show = subprocess.run(
            ["loginctl", "show-session", sid, "-p", "Name", "-p", "Type", "-p", "State", "-p", "Display"],
            capture_output=True, text=True,
        ).stdout
        props = dict(re.findall(r"^(\w+)=(.*)$", show, re.M))
        if props.get("Name") != user or props.get("Type") not in ("wayland", "x11"):
            continue
        if props.get("State") not in ("active", "online"):
            continue
        if props.get("Display"):
            env["DISPLAY"] = props["Display"]
        wl = sorted(p.name for p in runtime.glob("wayland-*") if p.is_socket())
        if wl:
            env["WAYLAND_DISPLAY"] = wl[0]
        break
    if "DISPLAY" not in env and "WAYLAND_DISPLAY" not in env:
        env["DISPLAY"] = ":0"
    if "XDG_RUNTIME_DIR" not in env:
        env["XDG_RUNTIME_DIR"] = str(runtime)
    if "XAUTHORITY" not in env:
        for f in sorted(runtime.glob("xauth_*")):
            env["XAUTHORITY"] = str(f)
            break
    return env


def x86_binfmt_nodes() -> list[str]:
    nodes: list[str] = []
    base = Path("/proc/sys/fs/binfmt_misc")
    if not base.is_dir():
        return nodes
    for p in base.iterdir():
        if p.name in ("register", "status"):
            continue
        try:
            text = p.read_text()
        except OSError:
            continue
        if not text.startswith("enabled"):
            continue
        magic = ""
        for line in text.splitlines():
            if line.startswith("magic "):
                magic = line.split()[1]
        if magic.startswith("7f454c46") and (
            magic.endswith("02003e00") or magic.endswith("03003e00")
            or magic.endswith("02000300") or magic.endswith("03000300")
        ):
            nodes.append(p.name)
    return nodes


def set_binfmt(nodes: list[str], enabled: bool) -> None:
    for n in nodes:
        p = Path("/proc/sys/fs/binfmt_misc") / n
        try:
            p.write_text("1\n" if enabled else "0\n")
        except OSError as e:
            log(f"binfmt {n}: {e}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prefix", default="/opt/steamos")
    ap.add_argument("--user", default=os.environ.get("SUDO_USER") or "lf")
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()

    client = Path(args.prefix) / "steam" / "steamrtarm64" / "steam"
    if not client.is_file():
        print(f"[bootstrap] missing {client}", file=sys.stderr)
        return 1
    try:
        pwd.getpwnam(args.user)
    except KeyError:
        print(f"[bootstrap] no such user: {args.user}", file=sys.stderr)
        return 1

    env = session_env(args.user)
    env["STEAM_COMPAT_GRAPHICS_PROVIDER"] = str(Path(args.prefix) / "fex-emu" / "RootFS" / "ArchLinux" / "graphics_provider.json")
    log("session env: " + " ".join(f"{k}={v}" for k, v in sorted(env.items())))

    disabled = x86_binfmt_nodes()
    if disabled:
        log("temporarily disabling x86 binfmt: " + " ".join(disabled))
        set_binfmt(disabled, False)
    try:
        cmd = ["runuser", "-u", args.user, "--", "env"]
        cmd += [f"{k}={v}" for k, v in env.items()]
        cmd += [str(client), "-deckard", "-exitsteam"]
        log("running: " + " ".join(cmd))
        rc = subprocess.run(cmd, timeout=args.timeout).returncode
        log(f"steam exited with {rc} (non-zero is a warning)")
    except subprocess.TimeoutExpired:
        log(f"timeout after {args.timeout}s")
        rc = 124
    finally:
        if disabled:
            set_binfmt(disabled, True)
    return 0 if rc == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
