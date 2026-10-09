#!/usr/bin/env python3
"""Point the Lucky core package at the vendor's own release service.

Lucky went closed source with the 3.x line: ``gdy666/lucky`` stopped publishing
GitHub releases at v2.27.2, and everything newer is served from
https://release.66666.host/ as prebuilt binaries plus OpenWrt APKs.  The package
mirror carries a Makefile for that service (``overrides/luci-app-lucky/lucky``
in hellomrli/my-openwrt-packages), but its pin is only a snapshot of whichever
release was current when it was written.  A release lives at
``v<release>/<version>_lucky/`` and lists per-architecture digests in
``checksums.txt``.

Run this after the third-party packages are materialized and before
``make download``:

* the service answers -> adopt its newest release and rewrite PKG_VERSION,
  PKG_RELEASE, PKG_SOURCE_URL and the per-architecture hash map in
  ``package/lucky/lucky/Makefile``, so ``make download`` fetches exactly the
  bytes the vendor published (this firmware builds x86_64, but the map covers
  every architecture the Makefile knows about);
* the service is unreachable -> keep the mirrored pin and let the download
  stage decide, exactly like ``pin-daede-source.py`` does for dae/daed;
* the service answers but no usable release exists -> fail, because silently
  building an unverified pin is worse than a two-minute failure.

Set ``LUCKY_VERSION=3.1.4`` to hold a known-good version when the newest
published build is broken.  Everything else follows the service.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = "https://release.66666.host"
PRODUCT = "lucky"
MAKEFILE = "package/lucky/lucky/Makefile"

ARCH_MAP_START = "# >>> ARCH MAP"
ARCH_MAP_END = "# <<< ARCH MAP"
ARCH_MAP_RE = re.compile(
    rf"^{re.escape(ARCH_MAP_START)}\n(?P<body>.*?)^{re.escape(ARCH_MAP_END)}$",
    re.MULTILINE | re.DOTALL,
)

# Architecture names the vendor uses in lucky_<version>_Linux_<arch>.tar.gz.
VENDOR_ARCHES = (
    "arm64",
    "armv5",
    "armv6",
    "armv7",
    "i386",
    "x86_64",
    "riscv64",
    "mips_softfloat",
    "mips_hardfloat",
    "mipsle_softfloat",
    "mipsle_hardfloat",
)

RELEASE_DIR_RE = re.compile(r"^v(?P<version>[0-9][A-Za-z0-9._+-]*)$")
NUMERIC_VERSION_RE = re.compile(r"^v(?P<version>[0-9]+(?:\.[0-9]+)*)")
PRODUCT_DIR_RE = re.compile(rf"^(?P<version>[0-9][A-Za-z0-9._+-]*)_{PRODUCT}$")
CHECKSUM_RE = re.compile(r"^(?P<sha256>[0-9a-f]{64})\s+(?P<name>\S+)$")
HREF_RE = re.compile(r"""href\s*=\s*["']([^"']*)["']""")

FETCH_ATTEMPTS = 3


class PinError(RuntimeError):
    """The pin cannot be refreshed and the build must not continue silently."""


class SiteUnavailable(RuntimeError):
    """The vendor service could not be reached; the mirrored pin is kept."""


def log(message: str) -> None:
    print(message, flush=True)


def warn(message: str) -> None:
    # ::warning:: is understood by GitHub Actions and is plain text elsewhere.
    print(f"::warning::{message}", flush=True)


def makefile_value(text: str, key: str) -> str:
    match = re.search(rf"^{re.escape(key)}:=(.*)$", text, re.MULTILINE)
    if not match:
        raise PinError(f"missing {key}:= in {MAKEFILE}")
    return match.group(1).strip()


def makefile_set(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}:=.*$", re.MULTILINE)
    if not pattern.search(text):
        raise PinError(f"missing {key}:= in {MAKEFILE}")
    return pattern.sub(lambda _: f"{key}:={value}", text, count=1)


def version_key(version: str) -> tuple:
    """Order release versions numerically, plain releases above their pre-releases.

    The vendor directory names carry suffixes (``v3.1.4beta``), and a string
    sort would put ``v3.1.9`` below ``v3.1.10``, so split the numeric part off
    and compare it as integers.
    """
    match = re.match(r"^v?(?P<numeric>[0-9]+(?:\.[0-9]+)*)(?P<suffix>.*)$", version)
    if not match:
        return ((0,), 1, version)
    numeric = tuple(int(part) for part in match.group("numeric").split("."))
    suffix = match.group("suffix")
    return (numeric, 0 if not suffix else 1, suffix)


def numeric_version(version: str) -> tuple[int, ...]:
    """Return the core version, ignoring the channel suffix the vendor appends.

    ``LUCKY_VERSION`` names the core version the package builds (``3.1.4``),
    while the release directory carries a channel suffix (``v3.1.4beta``), so
    the two can only be compared on the numeric part.
    """
    match = re.match(r"^v?(?P<numeric>[0-9]+(?:\.[0-9]+)*)", version)
    if not match:
        raise PinError(f"{version!r} does not start with a numeric version")
    return tuple(int(part) for part in match.group("numeric").split("."))


def fetch(url: str) -> str:
    request = urllib.request.Request(url)
    request.add_header("User-Agent", "my-ImmortalWrt-build")
    last_error: Exception | None = None
    for attempt in range(1, FETCH_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = response.read()
            return payload.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            last_error = exc
            # A missing directory or checksums.txt is a layout problem, not a
            # network flake; retrying only delays the report.
            if exc.code == 404:
                raise PinError(f"{url} returned HTTP 404") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
        if attempt < FETCH_ATTEMPTS:
            log(f"   {url} attempt {attempt}/{FETCH_ATTEMPTS} failed ({last_error}); retrying")
            time.sleep(5)
    raise SiteUnavailable(f"cannot reach {url}: {last_error}")


def list_dir(url: str) -> list[str]:
    """Return the entry names of a vendor directory listing.

    The service is Lucky itself, which exposes ``.lucky-browse.json`` next to
    every directory.  Its own installer scrapes the HTML instead, so fall back
    to that when the JSON listing is missing (a plain file server in front of
    the same tree) or unreadable.
    """
    directory = url.rstrip("/")
    try:
        entries = json.loads(fetch(f"{directory}/.lucky-browse.json"))
    except SiteUnavailable:
        raise
    except (PinError, json.JSONDecodeError, UnicodeDecodeError, TypeError):
        entries = None

    if isinstance(entries, list):
        names = [entry["name"] for entry in entries if isinstance(entry, dict) and "name" in entry]
        if names:
            return names

    html = fetch(f"{directory}/")
    names = set()
    for raw in HREF_RE.findall(html):
        value = raw.strip()
        if value.startswith("./"):
            value = value[2:]
        if value.endswith("/"):
            value = value[:-1]
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]*", value):
            names.add(value)
    if not names:
        raise PinError(f"{directory}/ has no JSON listing and no usable links")
    return sorted(names)


def pick_release(requested: str | None) -> tuple[str, str, dict[str, str]]:
    """Return the ``(release dir, product dir, checksums)`` to build from.

    The vendor names the release directory after the core version plus an
    optional channel suffix (``v3.1.4beta`` holds ``3.1.4_lucky``), so the
    product directory is derived from the directory name first and the release
    directory is only listed when that guess has no ``checksums.txt``.  The
    service sits behind a CDN that is markedly slower for some directory
    listings, and this keeps the common path down to two small requests.
    """
    releases: list[tuple[tuple, str]] = []
    for name in list_dir(BASE_URL):
        match = RELEASE_DIR_RE.match(name)
        if match:
            releases.append((version_key(match.group("version")), name))
    if not releases:
        raise PinError(f"{BASE_URL} carries no v<version> release directories")

    releases.sort(reverse=True)
    if requested:
        wanted = numeric_version(requested)
        releases = [item for item in releases if numeric_version(item[1]) == wanted]
        if not releases:
            raise PinError(f"{BASE_URL} has no release directory for LUCKY_VERSION={requested}")

    rejected: list[str] = []
    for _, release in releases:
        # Try the derived product name before listing the release directory:
        # that listing is generated on demand and a CDN miss on it can take
        # minutes, while checksums.txt is a static file.
        candidates: list[str] = []
        numeric = NUMERIC_VERSION_RE.match(release)
        if numeric:
            candidates.append(f"{numeric.group('version')}_{PRODUCT}")

        found = try_products(release, candidates, rejected)
        if found is not None:
            return found

        try:
            names = list_dir(f"{BASE_URL}/{release}")
        except SiteUnavailable:
            raise
        except PinError as exc:
            rejected.append(f"{release} ({exc})")
            continue
        listed = [
            name
            for name in sorted(names)
            if PRODUCT_DIR_RE.match(name) and name not in candidates
        ]
        if not listed:
            rejected.append(f"{release} (no <version>_{PRODUCT} directory)")
            continue
        found = try_products(release, listed, rejected)
        if found is not None:
            return found

    raise PinError(
        "no release on the vendor service carries usable "
        f"{PRODUCT} checksums; checked: {', '.join(rejected) or 'nothing'}"
    )


def try_products(
    release: str, products: list[str], rejected: list[str]
) -> tuple[str, str, dict[str, str]] | None:
    """Return the first product directory that has usable checksums."""
    for product in products:
        try:
            return release, product, fetch_checksums(release, product)
        except SiteUnavailable:
            raise
        except PinError as exc:
            rejected.append(f"{release}/{product} ({exc})")
    return None


def fetch_checksums(release: str, product: str) -> dict[str, str]:
    url = f"{BASE_URL}/{release}/{product}/checksums.txt"
    digests: dict[str, str] = {}
    for line in fetch(url).splitlines():
        match = CHECKSUM_RE.match(line.strip())
        if match:
            digests[match.group("name")] = match.group("sha256")
    if not digests:
        raise PinError(f"{url} lists no sha256 digests")
    return digests


def arch_map(version: str, digests: dict[str, str]) -> tuple[str, list[str]]:
    """Render the ARCH MAP block and report architectures the vendor dropped."""
    hashes: dict[str, str] = {}
    missing: list[str] = []
    for arch in VENDOR_ARCHES:
        digest = digests.get(f"lucky_{version}_Linux_{arch}.tar.gz")
        if digest:
            hashes[arch] = digest
        else:
            hashes[arch] = "skip"
            missing.append(arch)

    if len(missing) == len(VENDOR_ARCHES):
        raise PinError(
            f"checksums.txt for {version} lists no lucky_{version}_Linux_<arch>.tar.gz at all; "
            f"the vendor renamed the artefacts (found: {', '.join(sorted(digests)[:5])} ...)"
        )

    def line(arch: str, indent: str) -> str:
        note = "  # not in the vendor checksums.txt" if hashes[arch] == "skip" else ""
        return f"{indent}LUCKY_HASH:={hashes[arch]}{note}"

    body = [
        "# Generated by .github/scripts/pin-lucky-source.py from the vendor",
        "# checksums.txt; only the marker lines around this block are hand-written.",
        "LUCKY_ARCH:=",
        "LUCKY_HASH:=",
        "",
        "ifeq ($(ARCH),aarch64)",
        "  LUCKY_ARCH:=arm64",
        line("arm64", "  "),
        "endif",
        "ifeq ($(ARCH),arm)",
        "  ifeq ($(CONFIG_arm_v7),y)",
        "    LUCKY_ARCH:=armv7",
        line("armv7", "    "),
        "  else ifeq ($(CONFIG_arm_v6),y)",
        "    LUCKY_ARCH:=armv6",
        line("armv6", "    "),
        "  else ifneq ($(filter arm_arm926ej-s arm_xscale,$(ARCH_PACKAGES)),)",
        "    LUCKY_ARCH:=armv5",
        line("armv5", "    "),
        "  endif",
        "endif",
        "ifeq ($(ARCH),i386)",
        "  LUCKY_ARCH:=i386",
        line("i386", "  "),
        "endif",
        "ifeq ($(ARCH),x86_64)",
        "  LUCKY_ARCH:=x86_64",
        line("x86_64", "  "),
        "endif",
        "ifeq ($(ARCH),riscv64)",
        "  LUCKY_ARCH:=riscv64",
        line("riscv64", "  "),
        "endif",
        "ifeq ($(ARCH),mips)",
        "  ifeq ($(CONFIG_SOFT_FLOAT),y)",
        "    LUCKY_ARCH:=mips_softfloat",
        line("mips_softfloat", "    "),
        "  else",
        "    LUCKY_ARCH:=mips_hardfloat",
        line("mips_hardfloat", "    "),
        "  endif",
        "endif",
        "ifeq ($(ARCH),mipsel)",
        "  ifeq ($(CONFIG_SOFT_FLOAT),y)",
        "    LUCKY_ARCH:=mipsle_softfloat",
        line("mipsle_softfloat", "    "),
        "  else",
        "    LUCKY_ARCH:=mipsle_hardfloat",
        line("mipsle_hardfloat", "    "),
        "  endif",
        "endif",
    ]
    return "\n".join(body), missing


def resolve(tree: Path, requested: str | None) -> dict:
    makefile = tree / MAKEFILE
    if not makefile.is_file():
        raise PinError(f"{makefile} is missing; the package mirror did not deliver luci-app-lucky")

    text = makefile.read_text(encoding="utf-8")
    name = makefile_value(text, "PKG_NAME")
    if name != "lucky":
        raise PinError(f"{MAKEFILE} defines PKG_NAME:={name}, expected lucky")
    if not ARCH_MAP_RE.search(text):
        raise PinError(
            f"{MAKEFILE} has no {ARCH_MAP_START} / {ARCH_MAP_END} block, so it does not "
            "point at the vendor service. Check that hellomrli/my-openwrt-packages is "
            "reachable: fetch-packages.py falls back to upstream gdy666/luci-app-lucky, "
            "whose lucky core is still the GitHub-only 2.27.2."
        )
    pinned_version = makefile_value(text, "PKG_VERSION")
    pinned_url = makefile_value(text, "PKG_SOURCE_URL").split()[0]

    try:
        release, product, digests = pick_release(requested)
    except SiteUnavailable as exc:
        warn(f"lucky: {exc}; keeping the mirrored pin {pinned_version} from {pinned_url}")
        return {
            "version": pinned_version,
            "release": pinned_url,
            "state": "unverified",
            "missing": [],
            "changed": False,
        }

    version = PRODUCT_DIR_RE.match(product).group("version")
    block, missing = arch_map(version, digests)

    source_url = f"{BASE_URL}/{release}/{product}"
    changed = (
        version != pinned_version
        or source_url != pinned_url
        or block not in text
    )
    text = makefile_set(text, "PKG_VERSION", version)
    text = makefile_set(text, "PKG_RELEASE", "1")
    text = makefile_set(text, "PKG_SOURCE_URL", source_url)
    text = ARCH_MAP_RE.sub(lambda _: f"{ARCH_MAP_START}\n{block}\n{ARCH_MAP_END}", text, count=1)
    makefile.write_text(text, encoding="utf-8")

    if changed:
        log(f"   lucky: pin {'adopted' if version != pinned_version else 'refreshed'} -> {version}")
    else:
        log(f"   lucky: pin already at {version}")

    return {
        "version": version,
        "release": f"{release}/{product}",
        "state": "pinned",
        "missing": missing,
        "changed": changed,
        "digest": digests.get(f"lucky_{version}_Linux_x86_64.tar.gz", ""),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tree", type=Path, default=Path.cwd(), help="OpenWrt source tree (default: cwd)"
    )
    parser.add_argument("--provenance", type=Path, help="append the resolved pin to this report")
    args = parser.parse_args()

    tree = args.tree.resolve()
    if not (tree / "scripts" / "feeds").exists():
        raise PinError(f"{tree} does not look like an OpenWrt source tree")

    requested = os.environ.get("LUCKY_VERSION", "").strip() or None
    record = resolve(tree, requested)

    log(f"   lucky: {record['version']} from {record['release']} ({record['state']})")
    for arch in record["missing"]:
        warn(
            f"lucky: the vendor checksums.txt has no {arch} build for {record['version']}; "
            f"that architecture falls back to PKG_HASH=skip"
        )

    if args.provenance:
        with args.provenance.open("a", encoding="utf-8") as handle:
            handle.write("Lucky core package (release.66666.host):\n")
            handle.write(
                f"  lucky -> {record['version']} ({record['release']}, pin {record['state']})\n"
            )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PinError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
