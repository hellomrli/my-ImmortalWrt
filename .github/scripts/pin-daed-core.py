#!/usr/bin/env python3
"""Keep daed's bundled dae-core consistent with the revision dae-wing pins.

``kenzok8/openwrt-daede`` assembles ``daed-src-<date>-<id>.tar.gz`` from the
daed repository, whose ``wing/`` submodule (dae-wing) in turn pins
``wing/dae-core`` to one exact dae commit.  The assembly copies dae's *default
branch* into ``wing/dae-core`` instead of that pinned commit, so as soon as dae
main moves on, ``wing/`` no longer compiles against the tree shipped next to it.
That is what happened on 2026-09-19: dae main had dropped
``netutils.FallbackDns`` and the ``dialer.NewFromLink`` wrapper, which ``wing/``
still uses, and the daed package died with six "undefined" errors two hours into
the build (the dae patch failure in front of it had been hiding this one).

Run this after the packages are materialized and after pin-daede-source.py has
fetched ``dl/daed-src-*.tar.gz``, and before ``make download``:

* probe the dae-core the tarball actually carries and leave it untouched when it
  already satisfies every symbol ``wing/`` uses, so an upstream assembly fix is
  picked up for free and nothing is rewritten needlessly;
* otherwise resolve the commit dae-wing really pins -- through daed's ``wing``
  submodule when that is reachable, else dae-wing's default branch -- download
  that archive into ``dl/`` and point the daed Makefile's Build/Prepare at it;
* reuse the previously written pin when the GitHub API is unreachable, so a
  transient API outage cannot break a build that already worked;
* fail loudly when no candidate satisfies the probe, instead of letting the
  compile stage discover it two hours later.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

API_ROOT = "https://api.github.com"
DAED_REPO = "daeuniverse/daed"
WING_REPO = "daeuniverse/dae-wing"
CORE_REPO = "daeuniverse/dae"
ARCHIVE_URL = f"https://github.com/{CORE_REPO}/archive/{{commit}}.tar.gz"

DAED_MAKEFILE = Path("package/dae/daed/Makefile")
WING_CORE_PATH = "wing/dae-core"
MARK_BEGIN = "# DAE_CORE_PIN_BEGIN (written by .github/scripts/pin-daed-core.py)"
MARK_END = "# DAE_CORE_PIN_END"
INSTALL_CALL = "\t$(DaeCore/Install)\n"
GOFLAGS_RE = re.compile(r'^GO_PKG_BUILD_VARS\+= GOFLAGS="([^"]*)"$', re.MULTILINE)
MODULE_MODE_FLAG = "-mod=mod"

# What wing/ takes from dae-core.  Each entry is a directory plus a regular
# expression that must match somewhere below it.  These are the symbols whose
# removal from dae main broke the 2026-09-19 build; together they stand in for
# "the revision wing was written against", which is what the pin has to restore.
PROBES = (
    ("common/netutils", r"FallbackDns"),
    ("component/outbound/dialer", r"func NewFromLink\("),
    ("config", r"func FunctionOrStringToFunction"),
    ("control", r"func SnapshotRuntimeStats"),
    ("control", r"func NewControlPlane"),
    ("control", r"UdpEndpointPool\) Count"),
)

DOWNLOAD_ATTEMPTS = 3


class PinError(RuntimeError):
    pass


class ApiUnavailable(RuntimeError):
    pass


def log(message: str) -> None:
    print(message, flush=True)


def warn(message: str) -> None:
    print(f"::warning::{message}", flush=True)


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


def submodule_sha(repo: str, path: str, ref: str | None, token: str | None) -> str:
    suffix = f"?ref={ref}" if ref else ""
    entry = api_json(f"/repos/{repo}/contents/{path}{suffix}", token)
    if isinstance(entry, list):
        raise PinError(f"{repo}/{path} is a directory, expected a submodule")
    sha = entry.get("sha") or ""
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise PinError(f"{repo}/{path} did not report a commit id (got {sha!r})")
    return sha


def resolve_candidates(token: str | None) -> list[tuple[str, str]]:
    """Return (commit, provenance) pairs, most authoritative first."""
    candidates: list[tuple[str, str]] = []
    name = WING_CORE_PATH.split("/")[-1]
    try:
        wing = submodule_sha(DAED_REPO, "wing", None, token)
        candidates.append((submodule_sha(WING_REPO, name, wing, token), f"{DAED_REPO} wing@{wing[:12]}"))
    except (PinError, ApiUnavailable) as exc:
        warn(f"cannot resolve the dae-core commit through daed's wing submodule: {exc}")
    try:
        candidates.append((submodule_sha(WING_REPO, name, None, token), f"{WING_REPO}@HEAD"))
    except (PinError, ApiUnavailable) as exc:
        warn(f"cannot resolve the dae-core commit through dae-wing: {exc}")

    unique: list[tuple[str, str]] = []
    seen: set[str] = set()
    for commit, origin in candidates:
        if commit not in seen:
            seen.add(commit)
            unique.append((commit, origin))
    return unique


def submodule_paths(root: Path) -> list[str]:
    """Paths declared in the tree's .gitmodules."""
    modules = root / ".gitmodules"
    if not modules.is_file():
        return []
    paths = []
    for line in modules.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(r"\s*path\s*=\s*(\S+)\s*$", line)
        if match:
            paths.append(match.group(1))
    return paths


def probe_tree(root: Path) -> list[str]:
    """Return the probes the tree does not satisfy."""
    missing = []
    for directory, pattern in PROBES:
        base = root / directory
        matched = False
        if base.is_dir():
            regex = re.compile(pattern)
            for path in base.rglob("*.go"):
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                if regex.search(text):
                    matched = True
                    break
        if not matched:
            missing.append(f"{directory}: /{pattern}/")
    return missing


def _extract(tar: tarfile.TarFile, member: tarfile.TarInfo, dest: Path) -> None:
    try:
        tar.extract(member, dest, filter="data")
    except TypeError:  # Python < 3.12 has no extraction filters.
        tar.extract(member, dest)


def extract_nested(archive: Path, marker: str, dest: Path) -> int:
    """Extract everything below ``*/<marker>/`` with that prefix stripped."""
    needle = f"/{marker}/"
    extracted = 0
    try:
        with tarfile.open(archive, "r:gz") as tar:
            for member in tar.getmembers():
                index = member.name.find(needle)
                if index < 0:
                    continue
                relative = member.name[index + len(needle) :]
                if not relative:
                    continue
                member.name = relative
                _extract(tar, member, dest)
                extracted += 1
    except (tarfile.TarError, OSError) as exc:
        raise PinError(f"{archive.name} is not a readable gzipped tarball: {exc}") from exc
    return extracted


def extract_strip_one(archive: Path, dest: Path) -> int:
    """Extract a GitHub archive the way `tar --strip-components=1` would."""
    try:
        with tarfile.open(archive, "r:gz") as tar:
            members = tar.getmembers()
    except (tarfile.TarError, OSError) as exc:
        raise PinError(f"{archive.name} is not a readable gzipped tarball: {exc}") from exc

    tops = {m.name.split("/", 1)[0] for m in members if m.name and "/" in m.name}
    if len(tops) != 1:
        raise PinError(f"{archive.name} must hold exactly one top-level directory, found {sorted(tops)}")

    extracted = 0
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            if "/" not in member.name:
                continue
            relative = member.name.split("/", 1)[1]
            if not relative:
                continue
            member.name = relative
            _extract(tar, member, dest)
            extracted += 1
    return extracted


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
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            partial.unlink(missing_ok=True)
            if attempt < DOWNLOAD_ATTEMPTS:
                log(f"   retrying {url} after {exc}")
    raise PinError(f"cannot download {url}: {last_error}")


def strip_pin(text: str) -> tuple[str, str]:
    """Remove a previously written block, returning it so its pin can be reused.

    The trailing blank line the block is written with is consumed too, so
    re-running the script leaves the Makefile byte-identical.  The module-mode
    flag the pin adds to GOFLAGS is dropped on the way out for the same reason.
    """
    pattern = re.compile(
        rf"^{re.escape(MARK_BEGIN)}$.*?^{re.escape(MARK_END)}$\n\n?",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    previous = match.group(0) if match else ""
    text = pattern.sub("", text, count=1)
    text = text.replace(INSTALL_CALL, "")
    return drop_module_mode(text), previous


def rewrite_goflags(text: str, add: bool) -> str:
    """Add or remove -mod=mod on the daed Makefile's GOFLAGS line.

    wing/go.sum was written against the dae-core the tarball ships.  The pinned
    revision imports modules that one never did (github.com/bits-and-blooms/
    bloom/v3 and bitset, as of 85a1fc3c), and Go 1.16+ refuses to build a module
    whose go.sum lacks an entry -- OpenWrt runs `go list`/`go install` in that
    readonly mode.  -mod=mod lets those commands record the missing indirect
    requirements and sums themselves instead of failing the build.
    """
    match = GOFLAGS_RE.search(text)
    if not match:
        raise PinError(
            "the daed Makefile no longer sets GO_PKG_BUILD_VARS GOFLAGS the way the "
            "dae-core pin expects"
        )
    flags = [flag for flag in match.group(1).split() if flag != MODULE_MODE_FLAG]
    if add:
        flags.append(MODULE_MODE_FLAG)
    return GOFLAGS_RE.sub(f'GO_PKG_BUILD_VARS+= GOFLAGS="{" ".join(flags)}"', text, count=1)


def drop_module_mode(text: str) -> str:
    match = GOFLAGS_RE.search(text)
    if not match or MODULE_MODE_FLAG not in match.group(1).split():
        return text
    return rewrite_goflags(text, add=False)


def previous_commit(block: str) -> str | None:
    match = re.search(r"^DAE_CORE_COMMIT:=([0-9a-f]{40})$", block, re.MULTILINE)
    return match.group(1) if match else None


def pin_block(commit: str, submodules: list[str]) -> str:
    # The pinned archive comes from GitHub's /archive/<sha>.tar.gz, which does
    # not carry submodule contents, while bpf2go compiles control/kern/tproxy.c
    # and trace/kern/trace.c against the headers submodule.  Stash the ones the
    # tarball shipped materialized and put them back after the swap.
    #
    # The recipe deliberately uses no shell variables.  OpenWrt pulls a package's
    # rules in through `$(eval $(call BuildPackage,...))`, and $(eval) expands its
    # argument twice: a shell variable written as $$path becomes $path on the
    # first pass and $p followed by "ath" on the second, so the emptiness check
    # inspected a directory that never exists.  Everything below is expanded by
    # make ($(foreach), $(PKG_BUILD_DIR), ...) and carries no dollar, which makes
    # the recipe independent of how often it expands.
    paths = " ".join(submodules)
    stash = " ".join(
        f"mkdir -p \"$(PKG_BUILD_DIR)/.dae-core-submodules/{path}\";"
        f" cp -a \"$(PKG_BUILD_DIR)/dae-core/{path}/.\""
        f" \"$(PKG_BUILD_DIR)/.dae-core-submodules/{path}/\";"
        for path in submodules
    )
    restore = " ".join(
        f"rm -rf \"$(PKG_BUILD_DIR)/dae-core/{path}\";"
        f" mkdir -p \"$(PKG_BUILD_DIR)/dae-core/{path}\";"
        f" cp -a \"$(PKG_BUILD_DIR)/.dae-core-submodules/{path}/.\""
        f" \"$(PKG_BUILD_DIR)/dae-core/{path}/\";"
        for path in submodules
    )
    verify = " ".join(
        f"ls -A \"$(PKG_BUILD_DIR)/dae-core/{path}\" 2>/dev/null | grep -q . ||"
        f" {{ echo \"ERROR: dae-core submodule {path} is missing after pinning"
        f" {commit}\";"
        f" echo \"       the daed-src tarball must ship it materialized"
        f" (see .github/scripts/pin-daed-core.py)\"; exit 1; }};"
        for path in submodules
    )
    block = (
        f"{MARK_BEGIN}\n"
        f"# daed-src bundles wing/dae-core from dae's default branch instead of the commit\n"
        f"# dae-wing pins for it, so wing/ stops compiling against it.  Replace that tree with\n"
        f"# the pinned revision; .github/scripts/pin-daed-core.py fetches the archive into dl/\n"
        f"# before the build and only writes this block after probing the tree it contains.\n"
        f"# The archive has no submodule contents, so the header trees the tarball ships are\n"
        f"# kept across the swap -- bpf2go compiles the eBPF sources against them.\n"
        f"# wing/go.sum was written against the tree that ships in the tarball, so the pin\n"
        f"# also puts the Go build in -mod=mod mode further down: the pinned revision pulls\n"
        f"# in modules that one never imported, and readonly mode fails on the missing sums.\n"
        f"DAE_CORE_COMMIT:={commit}\n"
        f"DAE_CORE_SOURCE:=dae-core-{commit[:12]}.tar.gz\n"
        f"DAE_CORE_SUBMODULES:={paths}\n"
        f"define DaeCore/Install\n"
        f"\t@set -e; \\\n"
        f"\trm -rf \"$(PKG_BUILD_DIR)/.dae-core-submodules\"; \\\n"
        f"\t{stash} \\\n"
        f"\trm -rf \"$(PKG_BUILD_DIR)/dae-core\"; \\\n"
        f"\tmkdir -p \"$(PKG_BUILD_DIR)/dae-core\"; \\\n"
        f"\t$(TAR) --strip-components=1 -C \"$(PKG_BUILD_DIR)/dae-core\" -xzf \"$(DL_DIR)/$(DAE_CORE_SOURCE)\"; \\\n"
        f"\t{restore} \\\n"
        f"\t{verify} \\\n"
        f"\trm -rf \"$(PKG_BUILD_DIR)/.dae-core-submodules\"\n"
        f"endef\n"
        f"{MARK_END}\n"
    )
    check_recipe_is_expansion_safe(block)
    return block


def check_recipe_is_expansion_safe(block: str) -> None:
    """The recipe must not carry a dollar the shell could reinterpret.

    OpenWrt inlines a package's rules with `$(eval $(call BuildPackage,...))`,
    and $(eval) expands its argument twice.  With shell variables in the recipe,
    ``$$path`` therefore reached the running shell as ``$p`` followed by ``ath``,
    and the emptiness check inspected a directory that never exists.  Everything
    below is expanded by make, so the block must stay free of ``$$``; asserting
    that here keeps the failure out of a two-hour build if someone reintroduces
    one.
    """
    if "$$" in block:
        raise PinError(
            "the generated dae-core recipe contains a shell-level '$'; use make-level "
            "expansion ($(foreach), $(PKG_BUILD_DIR), ...) instead, because OpenWrt "
            "inlines rules with $(eval $(call BuildPackage,...)) and eval expands twice"
        )


def apply_pin(text: str, commit: str, submodules: list[str]) -> str:
    anchor = re.search(r"^PKG_HASH:=.*$", text, re.MULTILINE)
    if not anchor:
        raise PinError("the daed Makefile has no PKG_HASH line to anchor the dae-core pin on")
    if text[anchor.end() : anchor.end() + 1] != "\n":
        raise PinError("the daed Makefile's PKG_HASH line is not terminated by a newline")
    # Consume the anchor line's own newline and re-add it, so stripping the block
    # restores the file exactly.
    text = (
        text[: anchor.end()]
        + "\n"
        + pin_block(commit, submodules)
        + "\n"
        + text[anchor.end() + 1 :]
    )

    tar_line = re.search(
        r"^\t\$\(TAR\) --strip-components=1 -C \$\(DAED_BUILD_DIR\) -xzf \$\(DL_DIR\)/\$\(PKG_SOURCE\)$",
        text,
        re.MULTILINE,
    )
    if not tar_line:
        raise PinError("the daed Makefile no longer extracts PKG_SOURCE the way this pin expects")
    end = tar_line.end() + 1
    text = text[:end] + INSTALL_CALL + text[end:]
    return rewrite_goflags(text, add=True)


def daed_source_archive(tree: Path, dl_dir: Path) -> Path:
    makefile = tree / DAED_MAKEFILE
    if not makefile.is_file():
        raise PinError(f"{makefile} is missing; the package mirror did not deliver openwrt-daede")
    match = re.search(r"^PKG_SOURCE:=(.*)$", makefile.read_text(encoding="utf-8"), re.MULTILINE)
    if not match:
        raise PinError("the daed Makefile has no PKG_SOURCE line")
    archive = dl_dir / match.group(1).strip()
    if not archive.is_file():
        raise PinError(
            f"{archive} is missing; pin-daede-source.py should have fetched it before this runs"
        )
    return archive


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tree", type=Path, default=Path.cwd(), help="OpenWrt source tree")
    parser.add_argument("--provenance", type=Path, help="append the resolved pin to this report")
    args = parser.parse_args()

    tree = args.tree.resolve()
    if not (tree / "scripts" / "feeds").exists():
        raise PinError(f"{tree} does not look like an OpenWrt source tree")
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or None

    makefile = tree / DAED_MAKEFILE
    original = makefile.read_text(encoding="utf-8")
    stripped, previous = strip_pin(original)
    archive = daed_source_archive(tree, tree / "dl")
    dl_dir = tree / "dl"

    records: list[str] = []
    with tempfile.TemporaryDirectory(prefix="pin-daed-core-") as tmp:
        workdir = Path(tmp)
        shipped = workdir / "shipped"
        shipped.mkdir()
        if extract_nested(archive, WING_CORE_PATH, shipped) == 0:
            raise PinError(f"{archive.name} carries no {WING_CORE_PATH}; the layout changed")

        # GitHub's commit archives have no submodule contents, so the pinned tree
        # arrives with empty control/kern/headers and trace/kern/headers.  The
        # swap keeps the materialized ones from the tarball; without them bpf2go
        # cannot compile the eBPF sources, so refuse to pin when they are absent.
        submodules = submodule_paths(shipped)
        empty = [p for p in submodules if not any((shipped / p).glob("*"))]
        if empty:
            raise PinError(
                f"{archive.name} ships {WING_CORE_PATH} without materialized submodules "
                f"({', '.join(empty)}); pin-daed-core.py cannot restore them"
            )

        missing = probe_tree(shipped)
        if not missing:
            log(f"   daed-core: {archive.name} already satisfies every wing/ probe; leaving it alone")
            if stripped != original:
                makefile.write_text(stripped, encoding="utf-8")
                log("   daed-core: removed the stale pin block from the daed Makefile")
            records.append(
                f"daed dae-core: as shipped in {archive.name} (all {len(PROBES)} probes satisfied)"
            )
        else:
            log(
                f"   daed-core: {archive.name} does not match wing/ "
                f"({len(missing)}/{len(PROBES)} probes missing: {', '.join(missing)})"
            )

            try:
                candidates = resolve_candidates(token)
            except ApiUnavailable as exc:
                warn(f"{exc}; falling back to the previously pinned dae-core")
                candidates = []
            if not candidates:
                fallback = previous_commit(previous)
                if not fallback:
                    raise PinError(
                        "the GitHub API is unreachable and no dae-core pin was written before, so "
                        "the revision wing/ needs cannot be resolved"
                    )
                candidates = [(fallback, "the previous run")]

            chosen: tuple[str, str] | None = None
            for commit, origin in candidates:
                log(f"   daed-core: trying {commit[:12]} ({origin})")
                candidate_archive = dl_dir / f"dae-core-{commit[:12]}.tar.gz"
                if not candidate_archive.is_file():
                    log(f"   daed-core: fetching {candidate_archive.name}")
                    download(ARCHIVE_URL.format(commit=commit), candidate_archive)
                candidate = workdir / f"pinned-{commit[:12]}"
                if candidate.exists():
                    shutil.rmtree(candidate)
                candidate.mkdir()
                if extract_strip_one(candidate_archive, candidate) == 0 or not (
                    candidate / "control"
                ).is_dir():
                    warn(f"dae-core {commit[:12]} does not look like a dae source tree; skipping")
                    continue
                still_missing = probe_tree(candidate)
                if still_missing:
                    warn(
                        f"dae-core {commit[:12]} from {origin} still misses "
                        f"{', '.join(still_missing)}; trying the next candidate"
                    )
                    continue
                chosen = (commit, origin)
                log(
                    f"   daed-core: {candidate_archive.name} "
                    f"(sha256 {sha256_file(candidate_archive)[:16]}...) satisfies every probe"
                )
                break

            if chosen is None:
                raise PinError(
                    "no dae-core candidate satisfies the symbols wing/ uses; upstream moved the API "
                    "again -- update PROBES in .github/scripts/pin-daed-core.py"
                )

            commit, origin = chosen
            makefile.write_text(apply_pin(stripped, commit, submodules), encoding="utf-8")
            log(f"   daed-core: pinned {commit[:12]} from {origin}")
            records.append(
                f"daed dae-core: {commit} from {origin} "
                f"(replaces the tree in {archive.name}, all {len(PROBES)} probes satisfied, "
                f"keeps the shipped {', '.join(submodules) if submodules else 'submodules'})"
            )

    if args.provenance:
        with args.provenance.open("a", encoding="utf-8") as handle:
            for line in records:
                handle.write(f"  {line}\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PinError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
