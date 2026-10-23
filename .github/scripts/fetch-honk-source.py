#!/usr/bin/env python3
"""Materialize the mirrored Honk package and its hash-locked release assets.

The OpenWrt wrapper (``honk/`` and ``luci-app-honk/``) is copied out of
hellomrli/my-openwrt-packages by ``fetch-packages.py``.  That copy carries
``honk-source.json``, which the mirror's release-driven sync writes after it
has verified the upstream assets and re-uploaded them to a release of the
mirror.  This script is the build-side gate:

* the pin must describe a release of the mirror, never upstream;
* the wrapper's ``CORE_COMMIT``, the release provenance and the hashes inside
  ``generated-stage.mk`` / ``generated-doona-stage.mk`` must agree with it;
* both stage files must point their ``PKG_SOURCE_URL`` at the mirror;
* only then are the pinned tarballs downloaded into ``dl/`` and checked again
  (SHA256 and archive layout) before ``make download`` ever sees them.

Failing here is intentional: a wrapper without its matching verified assets
would otherwise fall back to the upstream ``staging`` release with ``SKIP``
hashes, which is exactly what the mirror exists to prevent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request

MIRROR_REPOSITORY = "https://github.com/hellomrli/my-openwrt-packages.git"
MIRROR_SLUG = "hellomrli/my-openwrt-packages"
PIN = "package/honk/honk-source.json"
ARCH_ASSETS = {
    "x86_64": "honk_x86_64",
    "aarch64": "honk_aarch64",
    "armv7": "honk_armv7",
}
REQUIRED_LAYOUT = {
    "honk": ("honk-core", "LICENSE"),
    "doona": ("index.html", "LICENSE", "NOTICE", "SOURCE", "THIRD-PARTY-NOTICES.txt"),
}
REQUIRED_FEATURES = {"ebpf", "rprx", "native-api"}
FETCH_ATTEMPTS = 3


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
        for attempt in range(FETCH_ATTEMPTS):
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "my-ImmortalWrt-build"})
                with urllib.request.urlopen(request, timeout=180) as response, partial.open("wb") as handle:
                    shutil.copyfileobj(response, handle)
                verify_hash(partial, expected)
                partial.replace(destination)
                break
            except (OSError, urllib.error.URLError, RuntimeError, TimeoutError):
                partial.unlink(missing_ok=True)
                if attempt == FETCH_ATTEMPTS - 1:
                    raise
                time.sleep(5)
    verify_hash(destination, expected)
    print(f"Verified {destination.name}: {expected}", flush=True)


def verify_layout(path: Path, kind: str) -> None:
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getnames()
    roots = {name.split("/")[0] for name in members}
    if len(roots) != 1:
        raise RuntimeError(f"Unexpected archive layout: {path.name}")
    root = roots.pop()
    names = {name[len(root) + 1 :] for name in members if name.startswith(root + "/")}
    missing = [name for name in REQUIRED_LAYOUT[kind] if name not in names]
    if missing:
        raise RuntimeError(f"{path.name} is missing required package files: {missing}")


def load_pin(tree: Path) -> dict:
    path = tree / PIN
    if not path.is_file():
        raise RuntimeError(
            f"{PIN} is missing; the mirror did not deliver the Honk package "
            "(packages-honk.json is mirror-only, so there is no upstream fallback)"
        )
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise RuntimeError(f"{PIN} is not valid JSON: {exc}") from exc


def validate_sources(tree: Path, pin: dict, architecture: str = "x86_64") -> None:
    if not isinstance(pin, dict):
        raise RuntimeError("Honk pin must be a JSON object")
    if pin.get("format") != 1:
        raise RuntimeError("Unsupported Honk pin format")
    if pin.get("mirror_repository") != MIRROR_REPOSITORY:
        raise RuntimeError("Honk pin does not describe the package mirror")
    if architecture not in ARCH_ASSETS:
        raise RuntimeError(f"Unsupported Honk architecture: {architecture}")
    release_url = pin.get("release_url", "")
    expected_url = f"https://github.com/{MIRROR_SLUG}/releases/download/{pin.get('mirror_release', '')}"
    if release_url != expected_url or not pin.get("mirror_release"):
        raise RuntimeError(f"Honk pin release URL is not the mirror: {release_url}")
    if "kenzok8/openwrt-honk" in release_url:
        raise RuntimeError("Honk pin still points at the upstream project")

    assets = pin.get("assets")
    if not isinstance(assets, dict):
        raise RuntimeError("Honk pin has no asset map")
    needed = (ARCH_ASSETS[architecture], "doona")
    for key in needed:
        asset = assets.get(key) or {}
        name = asset.get("name", "")
        if not name or name != Path(name).name or not re.fullmatch(r"[0-9a-f]{64}", asset.get("sha256", "")):
            raise RuntimeError(f"Honk pin has an invalid asset entry: {key}")

    core = pin.get("core")
    if not isinstance(core, dict):
        raise RuntimeError("Honk pin has no core description")
    core_commit = core.get("commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", core_commit):
        raise RuntimeError("Honk pin has no core commit")
    features = {item.strip() for item in core.get("features", "").split(",") if item.strip()}
    if not REQUIRED_FEATURES <= features:
        raise RuntimeError(f"Honk core lacks required features: {sorted(REQUIRED_FEATURES - features)}")
    if architecture not in core.get("architectures", []):
        raise RuntimeError(f"Honk release does not provide {architecture}")

    core_dir = tree / "package/honk/honk"
    luci_dir = tree / "package/honk/luci-app-honk"
    if make_value(core_dir / "Makefile", "PKG_NAME") != "honk":
        raise RuntimeError("Unexpected Honk core package")
    if make_value(core_dir / "Makefile", "CORE_COMMIT") != core_commit:
        raise RuntimeError("Honk wrapper CORE_COMMIT does not match the mirrored core")
    if make_value(luci_dir / "Makefile", "PKG_NAME") != "luci-app-honk":
        raise RuntimeError("Unexpected Honk LuCI package")

    provenance = json.loads((core_dir / "generated-provenance.json").read_text())
    mirrored_core = provenance.get("core") or {}
    if mirrored_core.get("commit") != core_commit or architecture not in mirrored_core.get("architectures", []):
        raise RuntimeError("Honk provenance does not match the pinned core/architecture")
    provenance_features = {item.strip() for item in mirrored_core.get("features", "").split(",") if item.strip()}
    if not REQUIRED_FEATURES <= provenance_features:
        raise RuntimeError("Honk provenance lacks eBPF, Reality/Vision or native API support")

    stage = core_dir / "generated-stage.mk"
    if make_value(stage, "PKG_SOURCE_URL").rstrip("/") != release_url:
        raise RuntimeError("Honk core stage file does not use the mirror release")
    core_asset = assets[ARCH_ASSETS[architecture]]
    suffix = architecture.upper()
    if make_value(stage, f"HONK_ASSET_{suffix}") != core_asset["name"] or make_value(
        stage, f"HONK_HASH_{suffix}"
    ) != core_asset["sha256"]:
        raise RuntimeError("Honk core stage file does not match the pinned asset")

    doona_stage = luci_dir / "generated-doona-stage.mk"
    if make_value(doona_stage, "PKG_SOURCE_URL").rstrip("/") != release_url:
        raise RuntimeError("Doona stage file does not use the mirror release")
    doona_asset = assets["doona"]
    if make_value(doona_stage, "PKG_SOURCE") != doona_asset["name"] or make_value(
        doona_stage, "PKG_HASH"
    ) != doona_asset["sha256"]:
        raise RuntimeError("Doona stage file does not match the pinned asset")


def install(tree: Path, pin: dict, cache: Path | None = None, architecture: str = "x86_64") -> list[str]:
    validate_sources(tree, pin, architecture)
    assets = pin["assets"]
    selected = (
        (assets[ARCH_ASSETS[architecture]], "honk"),
        (assets["doona"], "doona"),
    )
    for asset, kind in selected:
        destination = tree / "dl" / asset["name"]
        fetch_asset(f"{pin['release_url']}/{asset['name']}", destination, asset["sha256"], cache)
        verify_layout(destination, kind)
    return [asset["name"] for asset, _ in selected]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--architecture", default="x86_64", choices=sorted(ARCH_ASSETS))
    parser.add_argument("--asset-cache", type=Path, help="Optional local assets; hashes are still mandatory")
    parser.add_argument("--provenance", type=Path)
    args = parser.parse_args()
    tree = args.tree.resolve()
    if not (tree / "scripts/feeds").is_file():
        raise RuntimeError(f"Not an OpenWrt source tree: {tree}")
    pin = load_pin(tree)
    names = install(tree, pin, args.asset_cache, args.architecture)
    core = pin["core"]
    lines = [
        f"Honk wrapper: {pin['mirror_repository']} @ {pin['wrapper_commit']} "
        f"(mirrored from {pin['upstream']} release {pin['upstream_release']})",
        f"Honk core (upstream prebuilt, not locally Rust-compiled): {core['commit']} ({args.architecture})",
        f"Honk assets: {pin['release_url']}",
    ] + [f"  sha256 {pin['assets'][key]['sha256']} {name}" for key, name in zip(
        (ARCH_ASSETS[args.architecture], "doona"), names
    )]
    report = "\n".join(lines) + "\n"
    print(report)
    if args.provenance:
        with args.provenance.open("a") as handle:
            handle.write(report)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, KeyError, tarfile.TarError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        raise SystemExit(1)
