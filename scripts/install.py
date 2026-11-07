#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Install Steam (linuxarm64 public beta) + FEX + Proton on ARM64 Linux.

Everything lives under --prefix (default /opt/steamos).  Writes outside the
prefix (symlinks, desktop entry, env file) are recorded in
<PREFIX>/INSTALL-MANIFEST.tsv so scripts/uninstall.py can remove them again.

Tested target: Ubuntu 24.04 arm64, glibc 2.39, 4K pages, 48-bit VA.

Usage:
    sudo ./scripts/install.py                 # full install
    sudo ./scripts/install.py --skip-rootfs   # client + proton only
    ./scripts/install.py --dry-run            # print actions, change nothing
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import pwd
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

MANIFEST_URL = "https://client-update.fastly.steamstatic.com/steam_client_publicbeta_linuxarm64"
CLIENT_CDN = "https://client-update.steamstatic.com"
CLIENT_ENTRY = "bins_linuxarm64_linuxarm64"
ROOTFS_LINKS = "https://rootfs.fex-emu.gg/RootFS_links.json"
ROOTFS_NAME = "ArchLinux (SquashFS)"
PROTON_RELEASE_API = "https://api.github.com/repos/CachyOS/proton-cachyos/releases/latest"
GUEST_LINK = "/usr/share/guestos/fex-mesa"

USER_AGENT = "steam-fex-arm64/0.1 (+https://github.com/)"


def log(msg: str) -> None:
    print(f"[install] {msg}", flush=True)


def warn(msg: str) -> None:
    print(f"[install] WARNING: {msg}", file=sys.stderr, flush=True)


def fail(msg: str) -> "NoReturn":  # type: ignore[name-defined]
    print(f"[install] ERROR: {msg}", file=sys.stderr, flush=True)
    raise SystemExit(1)


def run(cmd: list[str], dry: bool = False, **kw) -> subprocess.CompletedProcess:
    log("run: " + " ".join(cmd))
    if dry:
        return subprocess.CompletedProcess(cmd, 0)
    return subprocess.run(cmd, check=True, **kw)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha512_file(path: Path) -> str:
    h = hashlib.sha512()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()



def remote_size(url: str) -> int | None:
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as r:
            n = r.headers.get("Content-Length")
            return int(n) if n else None
    except (urllib.error.URLError, ValueError):
        return None


def download(url: str, dest: Path, expected: str | None = None, algo: str = "sha256", dry: bool = False) -> Path:
    if dest.exists() and dest.stat().st_size > 0:
        if expected:
            have = sha256_file(dest) if algo == "sha256" else sha512_file(dest)
            if have == expected:
                log(f"cached {dest.name} ({have[:16]}…)")
                return dest
        elif remote_size(url) in (None, dest.stat().st_size):
            log(f"cached {dest.name} ({dest.stat().st_size >> 20} MiB)")
            return dest
    if dry:
        log(f"would download {url} -> {dest}")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    log(f"downloading {url}")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        resp = urllib.request.urlopen(req, timeout=120)
    except urllib.error.HTTPError as e:
        fail(f"download {url} failed: HTTP {e.code}")
    except urllib.error.URLError as e:
        fail(f"download {url} failed: {e.reason}")
    with resp as r, part.open("wb") as out:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            if total and done % (64 << 20) < (1 << 20):
                log(f"  {done * 100 // total}% ({done >> 20}/{total >> 20} MiB)")
    if expected:
        have = sha256_file(part) if algo == "sha256" else sha512_file(part)
        if have != expected:
            part.unlink(missing_ok=True)
            fail(f"checksum mismatch for {dest.name}: {have} != {expected}")
    part.replace(dest)
    return dest


def steam_manifest_entry(text: str, key: str) -> tuple[str, str]:
    m = re.search(r'"' + re.escape(key) + r'"\s*\{(.*?)\}', text, re.S)
    if not m:
        fail(f"manifest has no entry {key}")
    body = m.group(1)
    f = re.search(r'"file"\s+"([^"]+)"', body)
    s = re.search(r'"sha2"\s+"([^"]+)"', body)
    if not f or not s:
        fail(f"manifest entry {key} lacks file/sha2")
    return f.group(1), s.group(1)


def extract_zip(zpath: Path, dest: Path, dry: bool = False) -> None:
    log(f"extracting {zpath.name} -> {dest}")
    if dry:
        return
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zpath) as z:
        for info in z.infolist():
            name = info.filename.replace("\\", "/")
            parts = [p for p in name.split("/") if p not in ("", ".")]
            if not parts or any(p == ".." for p in parts):
                continue
            target = dest.joinpath(*parts)
            if info.is_dir() or name.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, target.open("wb") as out:
                shutil.copyfileobj(src, out)
            mode = (info.external_attr >> 16) & 0o777
            target.chmod(0o755 if mode & 0o111 else 0o644)


class Manifest:
    """Records every write outside the install prefix."""

    def __init__(self, path: Path):
        self.path = path
        self.lines: list[str] = []

    def add(self, kind: str, path: str, extra: str = "") -> None:
        line = f"{kind}\t{path}\t{extra}"
        if line not in self.lines:
            self.lines.append(line)

    def save(self, dry: bool = False) -> None:
        if dry:
            log("manifest (dry-run):\n  " + "\n  ".join(self.lines))
            return
        existing = self.path.read_text().splitlines() if self.path.exists() else []
        merged = existing + [l for l in self.lines if l not in existing]
        self.path.write_text("\n".join(merged) + "\n")


def _mkdir_tracked(path: Path, manifest: Manifest, dry: bool) -> None:
    """Create path (and missing parents), recording every directory we create."""
    missing: list[Path] = []
    p = path
    while not p.exists():
        missing.append(p)
        p = p.parent
    for d in reversed(missing):
        log(f"mkdir {d}")
        if not dry:
            d.mkdir()
        manifest.add("dir", str(d))


def ensure_dir(path: Path, manifest: Manifest, dry: bool) -> None:
    if path.is_dir():
        return
    if path.exists():
        fail(f"{path} exists but is not a directory")
    _mkdir_tracked(path, manifest, dry)


def ensure_symlink(path: Path, target: str, manifest: Manifest, dry: bool) -> None:
    if path.is_symlink():
        if os.readlink(path) == target:
            manifest.add("symlink", str(path), target)
            return
        fail(f"{path} is a symlink to {os.readlink(path)}, refusing to replace")
    if path.exists():
        fail(f"{path} already exists and is not a symlink, refusing to replace")
    log(f"symlink {path} -> {target}")
    _mkdir_tracked(path.parent, manifest, dry)
    if not dry:
        os.symlink(target, path)
    manifest.add("symlink", str(path), target)


def ensure_file(path: Path, content: str, manifest: Manifest, dry: bool, mode: int = 0o644) -> None:
    text = content
    already_ours = f"file\t{path}\t" in "\n".join(manifest.lines)
    if path.exists():
        try:
            if path.read_text() == text:
                manifest.add("file", str(path), hashlib.sha256(text.encode()).hexdigest())
                return
        except (OSError, UnicodeDecodeError):
            pass
        if not already_ours:
            fail(f"{path} exists with different content, refusing to replace")
    log(f"write {path}")
    _mkdir_tracked(path.parent, manifest, dry)
    if not dry:
        path.write_text(text)
        path.chmod(mode)
    manifest.add("file", str(path), hashlib.sha256(text.encode()).hexdigest())


def extract_rootfs(sqsh: Path, dest: Path, user: pwd.struct_passwd, dry: bool) -> None:
    if (dest / "graphics_provider.json").is_file():
        log(f"rootfs already extracted at {dest}")
        return
    staging = dest.parent / (dest.name + ".extracting")
    if staging.exists():
        shutil.rmtree(staging)
    log(f"unsquashfs {sqsh} -> {staging} (as {user.pw_name})")
    if dry:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    os.chown(dest.parent, user.pw_uid, user.pw_gid)
    cmd = ["runuser", "-u", user.pw_name, "--", "unsquashfs", "-no-xattrs", "-no-progress", "-d", str(staging), str(sqsh)]
    rc = subprocess.run(cmd).returncode
    # 2 == non-fatal errors (device nodes / permissions when not root)
    if rc not in (0, 2) or not (staging / "graphics_provider.json").is_file():
        fail(f"rootfs extraction failed (rc={rc}) or graphics_provider.json missing")
    if dest.exists():
        shutil.rmtree(dest)
    staging.rename(dest)


def install_client(prefix: Path, user: pwd.struct_passwd, args: argparse.Namespace, manifest: Manifest) -> Path:
    steam_root = prefix / "steam"
    steam_root.mkdir(parents=True, exist_ok=True)
    text = urllib.request.urlopen(
        urllib.request.Request(MANIFEST_URL, headers={"User-Agent": USER_AGENT}), timeout=60
    ).read().decode()
    target_file, target_sha = steam_manifest_entry(text, CLIENT_ENTRY)
    version = re.search(r'"version"\s+"([^"]+)"', text)
    log(f"Steam manifest version: {version.group(1) if version else 'unknown'}")
    zpath = download(f"{CLIENT_CDN}/{target_file}", prefix / "downloads" / target_file, target_sha, dry=args.dry_run)
    if not (steam_root / "steamrtarm64" / "steam").exists():
        extract_zip(zpath, steam_root, dry=args.dry_run)
    if not args.dry_run:
        client = steam_root / "steamrtarm64" / "steam"
        if not client.is_file():
            fail("steamrtarm64/steam missing after extraction")
        client.chmod(0o755)
        (steam_root / "package").mkdir(exist_ok=True)
        (steam_root / "package" / "beta").write_text("publicbeta\n")
    return steam_root


def install_rootfs(prefix: Path, user: pwd.struct_passwd, args: argparse.Namespace) -> Path:
    dest = prefix / "fex-emu" / "RootFS" / "ArchLinux"
    if (dest / "graphics_provider.json").is_file():
        log(f"rootfs already present at {dest}")
        return dest
    text = urllib.request.urlopen(
        urllib.request.Request(ROOTFS_LINKS, headers={"User-Agent": USER_AGENT}), timeout=60
    ).read().decode()
    entry = json.loads(text)["v1"][ROOTFS_NAME]
    url = entry["URL"]
    sqsh = download(url, prefix / "downloads" / Path(url).name, dry=args.dry_run)
    if not args.dry_run:
        check_rootfs(sqsh, entry.get("Hash", ""))
    extract_rootfs(sqsh, dest, user, args.dry_run)
    return dest


def check_rootfs(sqsh: Path, expected: str) -> None:
    """Verify the XXH3-64 hash FEX publishes when xxhsum is available."""
    if not expected:
        return
    if not shutil.which("xxhsum"):
        warn("xxhsum not installed, skipping rootfs hash check")
        return
    out = subprocess.run(["xxhsum", "-H3", str(sqsh)], capture_output=True, text=True).stdout
    have = (out.split() or [""])[0].replace("XXH3_", "").lower().zfill(16)
    if have != expected.lower().zfill(16):
        fail(f"rootfs hash mismatch: {have} != {expected}")
    log(f"rootfs hash ok ({have})")


def install_proton(prefix: Path, args: argparse.Namespace) -> None:
    compat = prefix / "steam" / "compatibilitytools.d"
    compat.mkdir(parents=True, exist_ok=True)
    if any(compat.glob("proton-cachyos-*-arm64")):
        log("Proton-CachyOS arm64 already installed")
        return
    data = json.loads(
        urllib.request.urlopen(
            urllib.request.Request(PROTON_RELEASE_API, headers={"User-Agent": USER_AGENT}), timeout=60
        ).read()
    )
    assets = {a["name"]: a["browser_download_url"] for a in data.get("assets", [])}
    tars = [n for n in assets if n.endswith("-arm64.tar.xz")]
    if not tars:
        fail("no Proton-CachyOS arm64 asset in latest release")
    name = sorted(tars)[-1]
    sums = name.replace(".tar.xz", ".sha512sum")
    tar_path = download(assets[name], prefix / "downloads" / name, dry=args.dry_run)
    if sums in assets:
        sums_path = download(assets[sums], prefix / "downloads" / sums, dry=args.dry_run)
        if not args.dry_run:
            expected = sums_path.read_text().split()[0]
            have = sha512_file(tar_path)
            if have != expected:
                fail(f"proton sha512 mismatch: {have} != {expected}")
    if args.dry_run:
        return
    staging = prefix / "downloads" / name.removesuffix(".tar.xz")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()
    log(f"extracting {name}")
    with tarfile.open(tar_path) as t:
        t.extractall(staging, filter="data")
    subdirs = [p for p in staging.iterdir() if p.is_dir()]
    src = subdirs[0] if len(subdirs) == 1 else staging
    dst = compat / name.removesuffix(".tar.xz")
    if dst.exists():
        shutil.rmtree(dst)
    src.rename(dst)
    shutil.rmtree(staging, ignore_errors=True)


def write_launcher(prefix: Path, manifest: Manifest, args: argparse.Namespace) -> None:
    launcher = prefix / "bin" / "steam"
    content = f"""#!/bin/bash
# Generated by steam-fex-arm64 install.py
set -e
PREFIX="{prefix}"
uid=$(id -u)
if [ -z "${{XDG_RUNTIME_DIR:-}}" ]; then export XDG_RUNTIME_DIR="/run/user/$uid"; fi
if [ -z "${{DISPLAY:-}}" ] && [ -z "${{WAYLAND_DISPLAY:-}}" ]; then export DISPLAY=:0; fi
if [ -z "${{XAUTHORITY:-}}" ]; then
  for f in /run/user/"$uid"/xauth_*; do [ -e "$f" ] && export XAUTHORITY="$f" && break; done
fi
export LD_LIBRARY_PATH="$PREFIX/lib${{LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}}"
export STEAM_COMPAT_GRAPHICS_PROVIDER="$PREFIX/fex-emu/RootFS/ArchLinux/graphics_provider.json"
if [ -S "/run/user/$uid/bus" ] && [ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ]; then
  export DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus"
fi
# Steam's game launch service lives in the Steam Linux Runtime; it is looked
# up by name, so it must be on PATH (otherwise every launch fails with
# "steam-runtime-launcher-service: not found").
for d in "$PREFIX/steam/steamapps/common"/SteamLinuxRuntime_*/pressure-vessel/bin; do
  [ -d "$d" ] && export PATH="$d:$PATH"
done
# Steam's X11 UI does not honour the compositor's HiDPI scale.  Raising Xft.dpi
# makes the CEF desktop UI scale correctly (verified at 2880x1800 / 200%).
export STEAM_UI_SCALE="${{STEAM_UI_SCALE:-2}}"
if [ "$STEAM_UI_SCALE" != "1" ] && command -v xrdb >/dev/null 2>&1; then
  printf 'Xft.dpi: %d\n' "$((96 * STEAM_UI_SCALE))" | xrdb -merge 2>/dev/null || true
fi
exec "$PREFIX/steam/steamrtarm64/steam" "$@"
"""
    ensure_file(launcher, content, manifest, args.dry_run, mode=0o755)


def adopt_runtime_dir(path: Path, dest: Path, dry: bool) -> None:
    """Move a FEX-created runtime dir (Server/Telemetry only) into the prefix."""
    allowed = {"Server", "Telemetry"}
    children = {p.name for p in path.iterdir()}
    if not children <= allowed:
        fail(f"{path} exists with unexpected content {sorted(children)}; move it away first")
    log(f"adopt {path} -> {dest}")
    if dry:
        return
    dest.mkdir(parents=True, exist_ok=True)
    for p in path.iterdir():
        target = dest / p.name
        if target.exists():
            continue
        p.rename(target)
    path.rmdir()


def write_user_files(prefix: Path, home: Path, manifest: Manifest, args: argparse.Namespace) -> None:
    local = home / ".local" / "share"
    dot_steam = home / ".steam"
    ensure_symlink(local / "Steam", str(prefix / "steam"), manifest, args.dry_run)
    fex_link = local / "fex-emu"
    if fex_link.is_dir() and not fex_link.is_symlink():
        adopt_runtime_dir(fex_link, prefix / "fex-emu", args.dry_run)
        if args.dry_run:
            log(f"symlink {fex_link} -> {prefix / 'fex-emu'} (after adopt)")
            manifest.add("symlink", str(fex_link), str(prefix / "fex-emu"))
        else:
            ensure_symlink(fex_link, str(prefix / "fex-emu"), manifest, args.dry_run)
    else:
        ensure_symlink(fex_link, str(prefix / "fex-emu"), manifest, args.dry_run)
    ensure_symlink(dot_steam / "steam", str(prefix / "steam"), manifest, args.dry_run)
    ensure_symlink(dot_steam / "root", str(prefix / "steam"), manifest, args.dry_run)
    ensure_symlink(dot_steam / "sdkarm64", str(prefix / "steam" / "linuxarm64"), manifest, args.dry_run)

    desktop = home / ".local" / "share" / "applications" / "steam.desktop"
    ensure_file(
        desktop,
        f"""[Desktop Entry]
Version=1.0
Type=Application
Name=Steam (ARM64 + FEX)
Comment=Steam linuxarm64 client with FEX and Proton
Exec={prefix}/bin/steam %U
Icon=steam
Terminal=false
Categories=Game;
MimeType=x-scheme-handler/steam;x-scheme-handler/steamlink;
""",
        manifest,
        args.dry_run,
    )
    env_file = home / ".config" / "environment.d" / "steam-fex.conf"
    ensure_file(
        env_file,
        f"STEAM_COMPAT_GRAPHICS_PROVIDER={prefix}/fex-emu/RootFS/ArchLinux/graphics_provider.json\n",
        manifest,
        args.dry_run,
    )


def install_fex(prefix: Path, home: Path, manifest: Manifest, args: argparse.Namespace) -> None:
    """Install the standalone FEX build from the Ubuntu PPA (extracted, not apt)."""
    fex_dir = prefix / "fex"
    if (fex_dir / "usr" / "bin" / "FEX").is_file():
        log("standalone FEX already installed")
    else:
        pkg = fex_package_name()
        index_url = "https://ppa.launchpadcontent.net/fex-emu/fex/ubuntu/dists/noble/main/binary-arm64/Packages.gz"
        raw = gzip.decompress(urllib.request.urlopen(
            urllib.request.Request(index_url, headers={"User-Agent": USER_AGENT}), timeout=60).read()).decode()
        filename = None
        for stanza in raw.split("\n\n"):
            if f"Package: {pkg}\n" in stanza and "Filename: " in stanza:
                filename = [l.split(": ", 1)[1] for l in stanza.splitlines() if l.startswith("Filename: ")][0]
                break
        if not filename:
            fail(f"{pkg} not found in PPA index")
        deb = download(f"https://ppa.launchpadcontent.net/fex-emu/fex/ubuntu/{filename}",
                       prefix / "downloads" / Path(filename).name, dry=args.dry_run)
        if not args.dry_run:
            if fex_dir.exists():
                shutil.rmtree(fex_dir)
            fex_dir.mkdir(parents=True)
            subprocess.run(["dpkg-deb", "-x", str(deb), str(fex_dir)], check=True)

    config = {
        "Config": {
            "RootFS": str(prefix / "fex-emu" / "RootFS" / "ArchLinux"),
            "ThunkGuestLibs": str(fex_dir / "usr" / "share" / "fex-emu" / "GuestThunks"),
            "ThunkHostLibs": str(fex_dir / "usr" / "lib" / "aarch64-linux-gnu" / "fex-emu" / "HostThunks"),
        },
        "ThunksDB": {"Vulkan": 1, "GL": 1},
    }
    # Arch rootfs libraries live in /usr/lib; the shipped ThunksDB template uses
    # @PREFIX_LIB@/libvulkan.so.1 which does not expand to that path.
    thunk_db = {"DB": {
        "Vulkan": {"Library": "libvulkan-guest.so",
                   "Overlay": ["/usr/lib/libvulkan.so.1", "/usr/lib/libvulkan.so"]},
        "GL": {"Library": "libGL-guest.so",
               "Overlay": ["/usr/lib/libGL.so.1", "/usr/lib/libGL.so"]},
    }}
    for path, data in ((home / ".fex-emu" / "Config.json", config),
                       (home / ".fex-emu" / "ThunksDB.json", thunk_db)):
        if path.exists():
            log(f"keeping existing {path}")
            continue
        ensure_file(path, json.dumps(data, indent=2) + "\n", manifest, args.dry_run)


BINFMT_CONF = Path("/etc/binfmt.d/FEX-x86_64.conf")
# systemd-binfmt wants the escaped text form; writing the binary NUL form
# directly to /proc/sys/fs/binfmt_misc/register truncates the rule and makes it
# match every ELF, which breaks exec system-wide (seen on this machine).
def binfmt_rule(prefix: Path) -> str:
    return (
    ":FEX-x86_64:M:0:"
    "\\x7fELF\\x02\\x01\\x01\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00"
    "\\x02\\x00\\x3e\\x00:"
    "\\xff\\xff\\xff\\xff\\xff\\xfe\\xfe\\x00\\x00\\x00\\x00"
    "\\xff\\xff\\xff\\xff\\xff\\xfe\\xff\\xff\\xff:"
    f"{prefix}/fex/usr/bin/FEX:POCF\n"
    )


def install_binfmt(manifest: Manifest, args: argparse.Namespace) -> None:
    """Register FEX as the x86_64 ELF interpreter via systemd-binfmt."""
    ensure_file(BINFMT_CONF, binfmt_rule(args.prefix), manifest, args.dry_run)
    if not args.dry_run:
        subprocess.run(["systemctl", "restart", "systemd-binfmt"], check=False)


def fex_package_name() -> str:
    try:
        features = open("/proc/cpuinfo").read()
    except OSError:
        return "fex-emu-armv8.0"
    line = next((l for l in features.splitlines() if l.startswith("Features")), "")
    f = set(line.split(":", 1)[-1].split())
    if {"fcma", "jscvt", "lrcpc", "paca", "pacg"} <= f:
        return "fex-emu-armv8.4"
    if {"atomics", "asimdrdm", "crc32", "dcpop"} <= f:
        return "fex-emu-armv8.2"
    return "fex-emu-armv8.0"


def ensure_prefix(prefix: Path, user: pwd.struct_passwd, dry: bool) -> None:
    for sub in ("", "downloads", "bin", "lib", "share"):
        p = prefix / sub if sub else prefix
        if not dry:
            p.mkdir(parents=True, exist_ok=True)
            os.chown(p, user.pw_uid, user.pw_gid)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prefix", default="/opt/steamos")
    ap.add_argument("--user", default=os.environ.get("SUDO_USER") or "lf")
    ap.add_argument("--skip-client", action="store_true")
    ap.add_argument("--skip-rootfs", action="store_true")
    ap.add_argument("--skip-proton", action="store_true")
    ap.add_argument("--skip-fex", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if os.uname().machine != "aarch64":
        fail(f"this installer targets aarch64, got {os.uname().machine}")
    if os.geteuid() != 0:
        fail("run this installer with sudo (it writes /opt and /usr/share/guestos)")
    try:
        user = pwd.getpwnam(args.user)
    except KeyError:
        fail(f"user {args.user} does not exist")

    prefix = Path(args.prefix)
    home = Path(user.pw_dir)
    if prefix == Path("/") or not str(prefix).startswith("/"):
        fail("refusing to use unsafe prefix")

    ensure_prefix(prefix, user, args.dry_run)
    manifest = Manifest(prefix / "INSTALL-MANIFEST.tsv")

    if not args.skip_client:
        install_client(prefix, user, args, manifest)
    rootfs = prefix / "fex-emu" / "RootFS" / "ArchLinux"
    if not args.skip_rootfs:
        rootfs = install_rootfs(prefix, user, args)
    if not args.skip_proton:
        install_proton(prefix, args)

    ensure_symlink(Path(GUEST_LINK), str(rootfs), manifest, args.dry_run)
    write_launcher(prefix, manifest, args)
    write_user_files(prefix, home, manifest, args)
    if not args.skip_fex:
        install_fex(prefix, home, manifest, args)
        install_binfmt(manifest, args)
    for d in ("/usr/share/guestos", str(home / ".steam"),
              str(home / ".config" / "environment.d"),
              str(home / ".config" / "fex-emu"),
              str(home / ".local" / "share" / "applications")):
        if Path(d).is_dir():
            manifest.add("dir", d)
    manifest.save(args.dry_run)

    if not args.dry_run:
        subprocess.run(["chown", "-R", f"{user.pw_name}:{user.pw_gid}", str(prefix)], check=False)
        # Steam refuses to write its IPC pid file if ~/.steam is root-owned,
        # which breaks `steam -applaunch` (it starts a second client instead).
        for p in (home / ".steam", home / ".config" / "environment.d",
                  home / ".config" / "fex-emu", home / ".local" / "share" / "applications"):
            if p.exists():
                subprocess.run(["chown", "-R", f"{user.pw_name}:{user.pw_gid}", str(p)], check=False)
        for f in (home / ".config" / "environment.d" / "steam-fex.conf",
                  home / ".local" / "share" / "applications" / "steam.desktop"):
            if f.exists():
                subprocess.run(["chown", f"{user.pw_name}:{user.pw_gid}", str(f)], check=False)
        log(f"done. launcher: {prefix}/bin/steam")
        log("next: sudo ./scripts/bootstrap.py   (or run the launcher and sign in)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
