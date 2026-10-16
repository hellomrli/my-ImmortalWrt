#!/usr/bin/env python3
"""Reject a Honk test image that loses the DNS baseline or NFQUEUE support."""

import argparse
from pathlib import Path
import re
import sys

REQUIRED = (
    "honk", "luci-app-honk", "kmod-nft-queue", "kmod-nfnetlink-queue",
    "kmod-sched", "kmod-sched-bpf", "kmod-veth", "sqlite3-cli", "coreutils-stat",
    "adguardhome", "lucky", "luci-app-lucky", "watchdog", "luci-app-watchdog",
    "kmod-fs-f2fs", "mkf2fs", "f2fsck", "openssh-sftp-server", "qemu-ga",
)
OLD_PROXY = re.compile(r"^(?:dae(?:[-_].*)?|daed(?:[-_].*)?|luci-app-dae(?:d|de)?(?:[-_].*)?)$")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def make_version(makefile: Path) -> str:
    text = makefile.read_text()
    version = re.search(r"^PKG_VERSION:=(.+)$", text, re.MULTILINE)
    release = re.search(r"^PKG_RELEASE:=(.+)$", text, re.MULTILINE)
    require(bool(version and release), f"Missing package version in {makefile}")
    return f"{version.group(1).strip()}-r{release.group(1).strip()}"


def check(tree: Path, manifest: Path | None = None) -> None:
    config = set((tree / ".config").read_text().splitlines())
    selected = {line.removeprefix("CONFIG_PACKAGE_").rsplit("=", 1)[0]
                for line in config if line.startswith("CONFIG_PACKAGE_") and line.endswith(("=y", "=m"))}
    for package in REQUIRED:
        require(f"CONFIG_PACKAGE_{package}=y" in config, f"Honk test package was lost: {package}")
    require(not any(OLD_PROXY.fullmatch(name) for name in selected), "Old dae/daed package remains selected")
    require(bool({"dnsmasq", "dnsmasq-full"} & selected), "DHCP/local DNS service is missing")
    for symbol in ("CONFIG_KERNEL_DEBUG_INFO_BTF", "CONFIG_KERNEL_CGROUP_BPF", "CONFIG_KERNEL_NETKIT", "CONFIG_KERNEL_XDP_SOCKETS"):
        require(f"{symbol}=y" in config, f"Required eBPF option was lost: {symbol}")
    for package in ("honk", "luci-app-honk"):
        makefile = tree / "package/honk" / package / "Makefile"
        require(makefile.is_file(), f"Missing fixed Honk wrapper: {makefile}")
    for feed in ("packages", "luci"):
        for name in ("dae", "daed", "luci-app-dae", "luci-app-daed", "luci-app-daede", "honk", "luci-app-honk"):
            path = tree / "package/feeds" / feed / name
            require(not path.exists() and not path.is_symlink(), f"Conflicting proxy feed entry: {path}")
    keep = (tree / "files/lib/upgrade/keep.d/my-immortalwrt").read_text().splitlines()
    for path in ("/etc/config/honk", "/etc/honk", "/etc/AdGuardHome-direct.yaml", "/etc/AdGuardHome-proxy.yaml"):
        require(path in keep, f"Missing Honk/DNS upgrade retention: {path}")
    for name in ("adh-direct", "adh-proxy"):
        path = tree / "files/etc/init.d" / name
        require(path.is_file() and bool(path.stat().st_mode & 0o111), f"Missing dual ADH service: {name}")
    if manifest:
        packages = {}
        for line in manifest.read_text().splitlines():
            fields = line.split()
            if len(fields) >= 2:
                packages[fields[0]] = fields[-1]
        require(set(REQUIRED) <= packages.keys(), f"Honk firmware packages missing: {set(REQUIRED) - packages.keys()}")
        require(not any(OLD_PROXY.fullmatch(name) for name in packages), "Firmware still contains old dae/daed packages")
        require(bool({"dnsmasq", "dnsmasq-full"} & packages.keys()), "Firmware is missing dnsmasq DHCP/local DNS")
        for package in ("honk", "luci-app-honk"):
            expected = make_version(tree / "package/honk" / package / "Makefile")
            require(packages[package] == expected, f"Unexpected {package} version: {packages[package]}, expected {expected}")
    print("Honk test validated: no dae/daed, dual ADH + DHCP retained, Honk/NFQUEUE selected.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tree", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    try:
        check(args.tree, args.manifest)
    except (OSError, RuntimeError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        raise SystemExit(1)
