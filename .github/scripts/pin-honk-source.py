#!/usr/bin/env python3
"""Install a fixed Honk wrapper and hash-verified, non-rolling release assets."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request

DEFAULT_PIN = Path(__file__).resolve().parents[1] / "honk-source.json"


def make_value(path: Path, key: str) -> str:
    match = re.search(rf"^{re.escape(key)}:=(.+)$", path.read_text(), re.MULTILINE)
    if not match:
        raise RuntimeError(f"{path} has no {key}:= value")
    return match.group(1).strip()


def verify_hash(path: Path, expected: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise RuntimeError(f"Invalid SHA256 pin for {path.name}")
    with path.open("rb") as handle:
        actual = hashlib.file_digest(handle, "sha256").hexdigest()
    if actual != expected:
        raise RuntimeError(f"SHA256 mismatch for {path.name}: expected {expected}, got {actual}")


def fetch_asset(url: str, destination: Path, expected: str, cache: Path | None) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if cache and (cache / destination.name).is_file():
        source = cache / destination.name
        verify_hash(source, expected)
        shutil.copyfile(source, destination)
    elif not destination.is_file():
        partial = destination.with_name(destination.name + ".part")
        for attempt in range(3):
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "my-ImmortalWrt-build"})
                with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as handle:
                    shutil.copyfileobj(response, handle)
                verify_hash(partial, expected)
                partial.replace(destination)
                break
            except (OSError, urllib.error.URLError, RuntimeError):
                partial.unlink(missing_ok=True)
                if attempt == 2:
                    raise
                time.sleep(5)
    verify_hash(destination, expected)
    print(f"Verified {destination.name}: {expected}", flush=True)


def verify_layout(path: Path, required: tuple[str, ...]) -> None:
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getnames()
    roots = {name.split("/")[0] for name in members}
    if len(roots) != 1:
        raise RuntimeError(f"Unexpected archive layout: {path.name}")
    root = roots.pop()
    if any(f"{root}/{name}" not in members for name in required):
        raise RuntimeError(f"{path.name} is missing required package files: {required}")


def validate_sources(tree: Path, pin: dict) -> None:
    core_dir = tree / "package/honk/honk"
    luci_dir = tree / "package/honk/luci-app-honk"
    if make_value(core_dir / "Makefile", "CORE_COMMIT") != pin["core_commit"]:
        raise RuntimeError("Honk wrapper CORE_COMMIT does not match the tested core")
    provenance = json.loads((core_dir / "generated-provenance.json").read_text())
    core = provenance["core"]
    if core["commit"] != pin["core_commit"] or pin["architecture"] not in core["architectures"]:
        raise RuntimeError("Honk release provenance does not match the requested core/architecture")
    if not {"ebpf", "rprx", "native-api"} <= set(core["features"].split(",")):
        raise RuntimeError("Honk release lacks eBPF, Reality/Vision or native API support")
    base_url = pin["repository"].removesuffix(".git") + "/releases/download/" + pin["source_tag"]
    for stage in (core_dir / "generated-stage.mk", luci_dir / "generated-doona-stage.mk"):
        if make_value(stage, "PKG_SOURCE_URL").rstrip("/") != base_url:
            raise RuntimeError(f"{stage.name} uses a different or rolling release")
    assets = {asset["name"]: asset for asset in pin["assets"]}
    stage = core_dir / "generated-stage.mk"
    core_asset = make_value(stage, "HONK_ASSET_X86_64")
    if make_value(stage, "HONK_HASH_X86_64") != assets[core_asset]["sha256"]:
        raise RuntimeError("Honk generated hash does not match the locked core asset")
    stage = luci_dir / "generated-doona-stage.mk"
    doona_asset = make_value(stage, "PKG_SOURCE")
    if make_value(stage, "PKG_HASH") != assets[doona_asset]["sha256"]:
        raise RuntimeError("Doona generated hash does not match the locked UI asset")
    verify_layout(tree / "dl" / core_asset, ("honk-core", "LICENSE"))
    verify_layout(tree / "dl" / doona_asset, ("index.html", "LICENSE", "NOTICE", "SOURCE", "THIRD-PARTY-NOTICES.txt"))


def install(tree: Path, pin: dict, cache: Path | None = None) -> None:
    if pin["architecture"] != "x86_64" or not re.fullmatch(r"[0-9a-f]{40}", pin["wrapper_commit"]):
        raise RuntimeError("This firmware requires a full wrapper commit and x86_64 assets")
    with tempfile.TemporaryDirectory(prefix="honk-wrapper-") as directory:
        checkout = Path(directory)
        commands = (
            ["git", "init", "--quiet"],
            ["git", "fetch", "--quiet", "--depth", "1", pin["repository"], pin["wrapper_commit"]],
            ["git", "checkout", "--quiet", "FETCH_HEAD"],
        )
        for command in commands:
            subprocess.run(command, cwd=checkout, check=True)
        actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=checkout, text=True).strip()
        if actual != pin["wrapper_commit"]:
            raise RuntimeError("Fetched Honk wrapper does not match the pinned commit")
        for package in ("honk", "luci-app-honk"):
            source = checkout / package
            if make_value(source / "Makefile", "PKG_NAME") != package:
                raise RuntimeError(f"Unexpected Honk package: {package}")
            destination = tree / "package/honk" / package
            if destination.exists():
                shutil.rmtree(destination)
            shutil.copytree(source, destination)
    url = pin["repository"].removesuffix(".git") + "/releases/download/" + pin["source_tag"]
    for asset in pin["assets"]:
        destination = Path(asset["destination"])
        if destination.is_absolute() or ".." in destination.parts or destination.name != asset["name"]:
            raise RuntimeError(f"Invalid Honk asset destination: {destination}")
        fetch_asset(f"{url}/{asset['name']}", tree / destination, asset["sha256"], cache)
    validate_sources(tree, pin)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--pin", type=Path, default=DEFAULT_PIN)
    parser.add_argument("--asset-cache", type=Path, help="Optional local assets; hashes are still mandatory")
    parser.add_argument("--provenance", type=Path)
    args = parser.parse_args()
    tree = args.tree.resolve()
    if not (tree / "scripts/feeds").is_file():
        raise RuntimeError(f"Not an OpenWrt source tree: {tree}")
    pin = json.loads(args.pin.read_text())
    install(tree, pin, args.asset_cache)
    lines = [
        f"Honk wrapper: {pin['repository']} @ {pin['wrapper_commit']}",
        f"Honk core (upstream prebuilt, not locally Rust-compiled): {pin['core_commit']} ({pin['architecture']})",
        f"Honk tested release: {pin['tested_release']}; hash-locked assets: {pin['source_tag']}",
    ] + [f"  sha256 {asset['sha256']} {asset['name']}" for asset in pin["assets"]]
    report = "\n".join(lines) + "\n"
    print(report)
    if args.provenance:
        with args.provenance.open("a") as handle:
            handle.write(report)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.CalledProcessError, tarfile.TarError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        raise SystemExit(1)
