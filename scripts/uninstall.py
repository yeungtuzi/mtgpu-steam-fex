#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Remove a steam-fex-arm64 install using INSTALL-MANIFEST.tsv.

Dry-run by default.  Only removes entries whose current state still matches
what install.py recorded; anything modified by hand is left alone with a
warning.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def log(msg: str) -> None:
    print(f"[uninstall] {msg}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prefix", default="/opt/steamos")
    ap.add_argument("--yes", action="store_true", help="actually remove (default: dry-run)")
    ap.add_argument(
        "--remove-apt",
        action="store_true",
        help="also apt-get remove packages recorded as 'apt' entries (opt-in)",
    )
    args = ap.parse_args()

    prefix = Path(args.prefix)
    manifest_path = prefix / "INSTALL-MANIFEST.tsv"
    if not manifest_path.is_file():
        print(f"[uninstall] no manifest at {manifest_path}", file=sys.stderr)
        return 1

    entries: list[tuple[str, str, str]] = []
    for line in manifest_path.read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        while len(parts) < 3:
            parts.append("")
        entries.append((parts[0], parts[1], parts[2]))

    removed_binfmt = False
    for kind, path_s, extra in reversed(entries):
        if kind == "dir" and path_s.startswith(str(prefix)):
            continue  # handled by the final rm -rf
        p = Path(path_s)
        if kind == "symlink":
            if p.is_symlink() and os.readlink(p) == extra:
                log(f"remove symlink {p}")
                if args.yes:
                    p.unlink()
            elif p.is_symlink():
                log(f"SKIP {p}: points to {os.readlink(p)}, expected {extra}")
            elif p.exists():
                log(f"SKIP {p}: no longer a symlink")
        elif kind == "file":
            if p.is_file():
                log(f"remove file {p}")
                if args.yes:
                    p.unlink()
                    if path_s.startswith("/etc/binfmt.d/"):
                        removed_binfmt = True
            elif p.exists():
                log(f"SKIP {p}: not a regular file")
        elif kind == "apt":
            installed = ""
            try:
                installed = subprocess.run(
                    ["dpkg-query", "-W", "-f=${Version}", path_s],
                    capture_output=True, text=True, check=False,
                ).stdout.strip()
            except FileNotFoundError:
                pass
            if not installed:
                log(f"apt {path_s}: not installed, nothing to do")
            elif installed != extra:
                log(f"SKIP apt {path_s}: installed {installed}, manifest says {extra}")
            elif args.remove_apt and args.yes:
                log(f"apt-get remove {path_s}")
                subprocess.run(["apt-get", "remove", "-y", path_s], check=False)
            else:
                log(f"apt {path_s} ({extra}): remove with: sudo apt-get remove {path_s}")
        elif kind == "dir":
            if p.is_dir():
                try:
                    if args.yes:
                        p.rmdir()
                    log(f"rmdir {p}")
                except OSError:
                    log(f"SKIP {p}: not empty")

    if removed_binfmt and args.yes:
        # Drop the in-kernel registration too; otherwise the rule stays active
        # until reboot even though the config file is gone.
        subprocess.run(["systemctl", "restart", "systemd-binfmt"], check=False)

    if prefix.exists():
        log(f"remove {prefix}")
        if args.yes:
            shutil.rmtree(prefix)

    if not args.yes:
        log("dry-run only; re-run with --yes to execute")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
