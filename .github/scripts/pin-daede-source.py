#!/usr/bin/env python3
"""Keep the dae/daed source tarball pins resolvable.

kenzok8/openwrt-daede publishes the assembled dae and daed source trees as
assets of two *rolling* releases (``dae-src`` and ``daed-src``) and keeps only
the newest three tarballs.  The Makefiles mirrored from upstream pin one exact
tarball name, so a tarball rotating out breaks the build without any upstream
commit touching that name.  That is exactly what happened on 2026-09-17: the
pin still pointed at ``dae-src-2026.09.12-187058462a1f.tar.gz`` while the
release only carried the 2026.09.18/2026.09.19 tarballs, so every run died with
a bare 404 in the download stage.

Run this after the third-party packages are materialized and before
``make download``:

* the pinned tarball is still published -> keep the pin untouched, so nothing
  changes until upstream really rotates it out;
* it is gone                            -> adopt the newest asset of that
  release and rewrite PKG_VERSION / PKG_RELEASE / PKG_SOURCE / PKG_HASH;
* the GitHub API is unreachable         -> keep the mirrored pin and let the
  fetch below decide whether it is still published.

The tarball is then fetched into ``dl/`` and verified three ways: the sha256
against the digest reported by the GitHub API, the 12-hex content id embedded
in the file name, and the directory layout the package Makefile expects
(``core/`` + ``outbound/`` + ``quic-go/`` for dae, ``wing/`` for daed).
Verifying here turns an upstream surprise into a two-minute failure instead of
a two-hour one, and leaves the source in ``dl/`` so ``make download`` reuses it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

API_ROOT = "https://api.github.com"
SOURCE_URL_RE = re.compile(
    r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/releases/download/(?P<tag>[^/]+)/?$"
)
ASSET_RE = re.compile(
    r"^(?P<name>[a-z0-9][a-z0-9-]*)-src-(?P<version>\d{4}\.\d{2}\.\d{2})-(?P<asset_id>[0-9a-f]{12})\.tar\.gz$"
)

# Directory layout each Makefile's Build/Prepare expects in the tarball, i.e.
# the paths that survive `tar --strip-components=1`.
PACKAGES = (
    {
        "makefile": "package/dae/dae/Makefile",
        "layout": ("core/go.mod", "outbound/go.mod", "quic-go/go.mod"),
    },
    {
        "makefile": "package/dae/daed/Makefile",
        "layout": ("wing/go.mod",),
    },
)

DOWNLOAD_ATTEMPTS = 3


class PinError(RuntimeError):
    pass


class ApiUnavailable(RuntimeError):
    pass


def log(message: str) -> None:
    print(message, flush=True)


def warn(message: str) -> None:
    # ::warning:: is understood by GitHub Actions and is plain text elsewhere.
    print(f"::warning::{message}", flush=True)


def makefile_value(text: str, key: str) -> str:
    match = re.search(rf"^{re.escape(key)}:=(.*)$", text, re.MULTILINE)
    if not match:
        raise PinError(f"missing {key}:= in Makefile")
    return match.group(1).strip()


def makefile_set(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}:=.*$", re.MULTILINE)
    if not pattern.search(text):
        raise PinError(f"missing {key}:= in Makefile")
    return pattern.sub(f"{key}:={value}", text, count=1)


def api_json(path: str, token: str | None) -> dict:
    request = urllib.request.Request(f"{API_ROOT}{path}")
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("User-Agent", "my-ImmortalWrt-build")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 429) or exc.code >= 500:
            raise ApiUnavailable(f"GitHub API returned HTTP {exc.code} for {path}") from exc
        raise PinError(f"GitHub API returned HTTP {exc.code} for {path}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ApiUnavailable(f"cannot reach the GitHub API: {exc}") from exc


def release_assets(owner: str, repo: str, tag: str, token: str | None) -> dict[str, dict]:
    release = api_json(f"/repos/{owner}/{repo}/releases/tags/{tag}", token)
    assets: dict[str, dict] = {}
    for asset in release.get("assets", []):
        name = asset.get("name", "")
        match = ASSET_RE.match(name)
        digest = asset.get("digest") or ""
        assets[name] = {
            "name": name,
            "created_at": asset.get("created_at") or "",
            "url": asset.get("browser_download_url") or "",
            "bytes": asset.get("size") or 0,
            "sha256": digest.removeprefix("sha256:") if digest.startswith("sha256:") else None,
            "match": match.groupdict() if match else None,
            "asset_id": (match.groupdict().get("asset_id") if match else None),
        }
    if not assets:
        raise PinError(f"release {owner}/{repo}@{tag} carries no assets")
    return assets


def pick_asset(pinned: str, assets: dict[str, dict]) -> tuple[dict, str]:
    """Return the asset to build from and whether the mirrored pin was kept."""
    if pinned in assets:
        return assets[pinned], "kept"
    candidates = [asset for asset in assets.values() if asset["match"] and asset["sha256"]]
    if not candidates:
        names = sorted(assets)
        shown = ", ".join(names[:5]) + (f", ... (+{len(names) - 5} more)" if len(names) > 5 else "")
        raise PinError(
            f"pinned source {pinned} is gone and the release carries no usable replacement "
            f"(assets: {shown})"
        )
    candidates.sort(key=lambda asset: (asset["created_at"], asset["name"]))
    return candidates[-1], "adopted"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path) -> None:
    partial = destination.with_suffix(destination.suffix + ".part")
    last_error: Exception | None = None
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        request = urllib.request.Request(url)
        request.add_header("User-Agent", "my-ImmortalWrt-build")
        try:
            with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
            partial.replace(destination)
            return
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            last_error = exc
            partial.unlink(missing_ok=True)
            if attempt < DOWNLOAD_ATTEMPTS:
                log(f"   download attempt {attempt}/{DOWNLOAD_ATTEMPTS} failed ({exc}); retrying")
                time.sleep(5)
    raise PinError(f"cannot download {url}: {last_error}")


def verify_layout(path: Path, required: tuple[str, ...]) -> None:
    """Check the tarball still holds the trees Build/Prepare expects."""
    try:
        with tarfile.open(path, "r:gz") as archive:
            entries = archive.getmembers()
    except (tarfile.TarError, OSError) as exc:
        raise PinError(f"{path.name} is not a readable gzipped tarball: {exc}") from exc

    # Build/Prepare untars with --strip-components=1, so exactly one top-level
    # directory may exist.  Archive metadata files (pax_global_header and the
    # like) sit next to it and are dropped by that same option, so they do not
    # count as a second root.
    tops = set()
    for entry in entries:
        name = entry.name
        if not name or name.startswith("/"):
            continue
        head = name.split("/", 1)[0]
        if head == name and not entry.isdir():
            continue
        tops.add(head)

    if len(tops) != 1:
        raise PinError(
            f"{path.name} must hold exactly one top-level directory, found {sorted(tops)}"
        )
    top = tops.pop()
    members = {entry.name for entry in entries}
    missing = [item for item in required if f"{top}/{item}" not in members]
    if missing:
        raise PinError(
            f"{path.name} no longer matches the layout the package Makefile expects; "
            f"missing: {', '.join(missing)}"
        )


def resolve(
    package: dict, tree: Path, dl_dir: Path, token: str | None, fetch: bool
) -> dict:
    makefile = tree / package["makefile"]
    if not makefile.is_file():
        raise PinError(
            f"{makefile} is missing; the package mirror did not deliver openwrt-daede"
        )

    text = makefile.read_text(encoding="utf-8")
    name = makefile_value(text, "PKG_NAME")
    version = makefile_value(text, "PKG_VERSION")
    source = makefile_value(text, "PKG_SOURCE")
    source_url = makefile_value(text, "PKG_SOURCE_URL").split()[0]
    pinned_hash = makefile_value(text, "PKG_HASH").lower()

    match = SOURCE_URL_RE.match(source_url)
    if not match:
        raise PinError(f"{name}: unsupported PKG_SOURCE_URL {source_url!r}")
    owner, repo, tag = match.group("owner"), match.group("repo"), match.group("tag")

    api_down = False
    try:
        asset, pin_state = pick_asset(source, release_assets(owner, repo, tag, token))
    except ApiUnavailable as exc:
        api_down = True
        pin_state = "unverified"
        warn(f"{name}: {exc}; keeping the mirrored pin and downloading it directly")
        detail = ASSET_RE.match(source)
        asset = {
            "name": source,
            "created_at": "",
            "url": f"{source_url}/{source}",
            "bytes": 0,
            "sha256": pinned_hash,
            "match": detail.groupdict() if detail else None,
            "asset_id": detail.groupdict().get("asset_id") if detail else None,
        }

    if pin_state == "adopted":
        log(
            f"   {name}: pinned {source} is no longer published by {owner}/{repo}@{tag}; "
            f"adopting {asset['name']}"
        )

    # The file name carries the version and the first 12 hex digits of the
    # sha256, so the Makefile metadata is derived from the asset, never guessed.
    detail = asset["match"] or {}
    if detail.get("version"):
        version = detail["version"]
        if version != makefile_value(text, "PKG_VERSION") or pin_state == "adopted":
            text = makefile_set(text, "PKG_VERSION", version)
            text = makefile_set(text, "PKG_RELEASE", "1")
    text = makefile_set(text, "PKG_SOURCE", asset["name"])
    if asset["sha256"] and asset["sha256"] != pinned_hash:
        if pin_state == "kept":
            warn(
                f"{name}: {asset['name']} now reports sha256 {asset['sha256']}, "
                f"the pin said {pinned_hash}; using the published digest"
            )
        text = makefile_set(text, "PKG_HASH", asset["sha256"])
    makefile.write_text(text, encoding="utf-8")

    expected = (asset["sha256"] or pinned_hash).lower()
    if asset["asset_id"] and not expected.startswith(asset["asset_id"]):
        raise PinError(
            f"{name}: {asset['name']} digest {expected} does not start with its "
            f"content id {asset['asset_id']}"
        )

    record = {
        "name": name,
        "source": asset["name"],
        "version": version,
        "pin": pin_state,
    }
    target = dl_dir / asset["name"]
    if target.is_file() and sha256_file(target) == expected:
        log(f"   {name}: {asset['name']} already in dl/ and verified")
    elif not fetch:
        record["state"] = "pinned"
        return record
    else:
        log(f"   {name}: fetching {asset['name']} ({asset['bytes'] // (1024 * 1024)} MiB)")
        dl_dir.mkdir(parents=True, exist_ok=True)
        try:
            download(asset["url"], target)
        except PinError as exc:
            if api_down:
                raise PinError(
                    f"{name}: {exc}. The GitHub API was unavailable too, so the pin could "
                    f"not be refreshed; check for a rotated {tag} asset."
                ) from exc
            raise

    actual = sha256_file(target)
    if actual != expected:
        target.unlink(missing_ok=True)
        raise PinError(f"{name}: {asset['name']} has sha256 {actual}, expected {expected}")
    verify_layout(target, package["layout"])
    record["state"] = "verified"
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tree", type=Path, default=Path.cwd(), help="OpenWrt source tree (default: cwd)"
    )
    parser.add_argument(
        "--provenance", type=Path, help="append the resolved pins to this report"
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="re-pin the Makefiles only and leave downloading to `make download`",
    )
    args = parser.parse_args()

    tree = args.tree.resolve()
    if not (tree / "scripts" / "feeds").exists():
        raise PinError(f"{tree} does not look like an OpenWrt source tree")
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or None

    records = [
        resolve(package, tree, tree / "dl", token, not args.no_fetch) for package in PACKAGES
    ]
    for record in records:
        log(
            f"   {record['name']}: {record['source']} "
            f"(version {record['version']}, pin {record['pin']}, {record['state']})"
        )

    if args.provenance:
        with args.provenance.open("a", encoding="utf-8") as handle:
            handle.write("kenzok8/openwrt-daede source tarballs:\n")
            for record in records:
                handle.write(
                    f"  {record['name']} -> {record['source']} "
                    f"(version {record['version']}, pin {record['pin']}, {record['state']})\n"
                )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PinError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
