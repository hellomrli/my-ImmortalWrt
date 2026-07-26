#!/usr/bin/env python3
"""Materialize third-party packages into an OpenWrt source tree.

The firmware must keep building when an upstream repository is deleted, renamed
or made private, so every third-party package is mirrored into
hellomrli/my-openwrt-packages.  This script prefers that mirror and only falls
back to the upstream repository for packages the mirror does not carry yet.

Only the directories listed in packages.json are copied out of the mirror.  The
mirror also holds packages this firmware deliberately does not build (golang,
adguardhome-dual, openclash, passwall, ...); dropping the whole mirror into
package/ would collide with feeds/packages/lang/golang and with this firmware's
overlay-based dual AdGuardHome setup.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SOURCE_MODES = ("auto", "mirror", "upstream")


class FetchError(RuntimeError):
    pass


def run(cmd: list[str], cwd: Path | None = None) -> str:
    print("+", " ".join(cmd), flush=True)
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.stdout:
        print(result.stdout, end="", flush=True)
    if result.returncode != 0:
        raise FetchError(f"command failed ({result.returncode}): {' '.join(cmd)}")
    return result.stdout.strip()


def clone(repo: str, ref: str | None, dest: Path) -> str:
    """Shallow-clone repo@ref into dest and return the resolved commit."""
    if dest.exists():
        shutil.rmtree(dest)

    # A branch or tag can be cloned directly; a raw commit SHA has to be
    # fetched explicitly because --branch does not accept one.
    if ref and _looks_like_sha(ref):
        dest.mkdir(parents=True)
        run(["git", "init", "--quiet"], cwd=dest)
        run(["git", "remote", "add", "origin", repo], cwd=dest)
        run(["git", "fetch", "--depth", "1", "--quiet", "origin", ref], cwd=dest)
        run(["git", "checkout", "--quiet", "FETCH_HEAD"], cwd=dest)
    else:
        cmd = ["git", "clone", "--depth", "1", "--quiet"]
        if ref:
            cmd += ["--branch", ref]
        cmd += [repo, str(dest)]
        run(cmd)

    return run(["git", "rev-parse", "HEAD"], cwd=dest)


def _looks_like_sha(ref: str) -> bool:
    return len(ref) >= 7 and all(char in "0123456789abcdefABCDEF" for char in ref)


def install(src: Path, target: Path, require: list[str]) -> None:
    """Replace target with src, then check the package layout is intact."""
    missing = [item for item in require if not (src / item).is_file()]
    if missing:
        raise FetchError(f"{src} is missing required files: {', '.join(missing)}")

    if target.exists() or target.is_symlink():
        shutil.rmtree(target, ignore_errors=True)
        if target.exists() or target.is_symlink():
            target.unlink()
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, target, ignore=shutil.ignore_patterns(".git"))

    # copytree already skipped .git, but verify: a nested repository would make
    # the OpenWrt package scanner and later git operations behave unpredictably.
    if (target / ".git").exists():
        shutil.rmtree(target / ".git", ignore_errors=True)


def fetch_mirror(mirror: dict, workdir: Path) -> tuple[Path | None, str | None]:
    repo = mirror["repo"]
    ref = os.environ.get("PKG_MIRROR_REF") or mirror.get("ref") or None
    dest = workdir / "_mirror"
    try:
        commit = clone(repo, ref, dest)
    except FetchError as exc:
        print(f"::warning::Package mirror is unavailable ({exc}); falling back to upstream.")
        return None, None
    print(f"Mirror {repo}@{ref or 'default'} is at {commit}")
    return dest, commit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument(
        "--tree",
        type=Path,
        default=Path.cwd(),
        help="OpenWrt source tree root (default: current directory)",
    )
    parser.add_argument(
        "--provenance",
        type=Path,
        help="write a human-readable source report to this file",
    )
    args = parser.parse_args()

    mode = os.environ.get("PKG_SOURCE", "auto").strip().lower() or "auto"
    if mode not in SOURCE_MODES:
        raise FetchError(f"PKG_SOURCE must be one of {', '.join(SOURCE_MODES)}, got {mode!r}")

    config = json.loads(args.config.read_text(encoding="utf-8"))
    packages = config["packages"]
    tree = args.tree.resolve()
    if not (tree / "scripts" / "feeds").exists():
        raise FetchError(f"{tree} does not look like an OpenWrt source tree")

    records: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="fetch-packages-") as tmp:
        workdir = Path(tmp)

        mirror_dir: Path | None = None
        mirror_commit: str | None = None
        if mode in ("auto", "mirror"):
            mirror_dir, mirror_commit = fetch_mirror(config["mirror"], workdir)
            if mirror_dir is None and mode == "mirror":
                raise FetchError("PKG_SOURCE=mirror was requested but the mirror is unavailable")

        for package in packages:
            name = package["name"]
            target = tree / package["target"]
            require = package.get("require", [])

            source_dir: Path | None = None
            origin = ""
            commit = mirror_commit or ""

            if mirror_dir is not None:
                candidate = mirror_dir / package["mirror_path"]
                if candidate.is_dir():
                    source_dir = candidate
                    origin = f"mirror:{package['mirror_path']}"
                elif mode == "mirror":
                    raise FetchError(
                        f"{name} is not present in the mirror as {package['mirror_path']}"
                    )
                else:
                    print(
                        f"::warning::{name} is not mirrored as "
                        f"{package['mirror_path']} yet; using upstream "
                        f"{package['upstream']}. Add it to the mirror's "
                        f"sources.json so an upstream takedown cannot break the build."
                    )

            if source_dir is None:
                if mode == "mirror":
                    raise FetchError(f"{name} is unavailable from the mirror")
                upstream_dir = workdir / f"_upstream_{name}"
                commit = clone(package["upstream"], package.get("upstream_ref"), upstream_dir)
                source_dir = upstream_dir
                origin = f"upstream:{package['upstream']}"

            install(source_dir, target, require)
            records.append(
                {
                    "name": name,
                    "target": package["target"],
                    "origin": origin,
                    "commit": commit,
                    "description": package.get("description", ""),
                }
            )
            print(f"Installed {name} -> {package['target']} from {origin}")

    lines = ["Third-party package sources:"]
    for item in records:
        short = item["commit"][:12] if item["commit"] else "unknown"
        lines.append(f"  {item['name']} -> {item['target']} ({item['origin']} @ {short})")
    report = "\n".join(lines)
    print()
    print(report)

    if args.provenance:
        args.provenance.write_text(report + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FetchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
