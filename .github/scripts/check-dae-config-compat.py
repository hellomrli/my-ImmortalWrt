#!/usr/bin/env python3
"""Fail the build when daed's embedded dae-core cannot parse dae's own template.

daed builds the dae data plane in-process and parses its stored global / dns /
routing sections with the ``config`` package of the core bundled in
``wing/dae-core``.  That parser rejects unknown keys ("unexpected key: %v"), and
one unknown key aborts the parse of the whole config -- daed then writes
``running=false``, keeps no data plane and looks like it lost every routing
rule, group and dns policy the user had configured.

The dae package ships ``example.dae``, which is where a global section normally
comes from (LuCI's generator and the daed dashboard both write that shape), so
its keys are the minimum the embedded core has to accept.  On 2026-09-20 the
two drifted apart without anything failing at build time: the core pinned for
``wing/`` (85a1fc3c, April 2026) predated ``disable_thp``,
``auto_sniff_punt`` and ``bpf_conn_state_map_size``, and a stored config
carrying the first of them made daed come up with "Routing match set len:
1/1024" -- i.e. direct-only -- while the dashboard still listed the config as
selected.

This check turns that silent runtime failure into a build-time one.  It reads
the archives the build will use and then reproduces what the build does to them,
so it sees exactly what ships:

* the template from the dae package's ``PKG_SOURCE`` archive (``core/example.dae``);
* the accepted keys from the core daed will build -- the pinned
  ``DAE_CORE_SOURCE`` archive when pin-daed-core.py wrote one, otherwise the
  ``wing/dae-core`` tree inside the daed package's own archive -- extracted the
  way ``$(DaeCore/Install)`` extracts it and with ``$(DaeCore/ApplyPatch)``'s
  series replayed in order first.  Reading the archive without the series would
  compare dae's template against an unpatched core and reject every key a compat
  patch adds.

Usage, after pin-daede-source.py and pin-daed-core.py have fetched the archives:

    python3 .github/scripts/check-dae-config-compat.py --tree .

Add ``--dae-archive`` / ``--core-archive`` to check specific tarballs.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

DAE_MAKEFILE = Path("package/dae/dae/Makefile")
DAED_MAKEFILE = Path("package/dae/daed/Makefile")
# Where diy-part2-daed.sh installs the patch series that the daed Makefile's
# $(DaeCore/ApplyPatch) applies to wing/dae-core at build time.
PATCH_DIR = Path("package/dae/daed/dae-core-patches")
TEMPLATE_PATTERN = re.compile(r"^(?:[^/]+/)*(?:core/)?example\.dae$")
# Blocks whose direct keys are fields of the config structs.  Everything else
# (subscription and node entrances, dns upstream names, group names) is
# user-defined text, so its keys must not be compared against the schema.
FIELD_BLOCKS = {
    ("global",),
    ("dns",),
    ("dns", "routing"),
    ("dns", "routing", "request"),
    ("dns", "routing", "response"),
    ("routing",),
}


class CheckError(Exception):
    """A condition that must stop the build."""


def log(message: str) -> None:
    print(f"   daed-config: {message}")


def makefile_variable(text: str, name: str) -> str | None:
    match = re.search(rf"^{re.escape(name)}:=(.*)$", text, re.MULTILINE)
    return match.group(1).strip() if match else None


def read_makefile(tree: Path, relative: Path) -> str:
    path = tree / relative
    if not path.is_file():
        raise CheckError(
            f"{relative} is missing; the daede package was not materialized before this check"
        )
    return path.read_text(encoding="utf-8")


def archive_for(tree: Path, name: str | None, override: Path | None, label: str) -> Path:
    if override is not None:
        if not override.is_file():
            raise CheckError(f"{override} does not exist")
        return override
    if not name:
        raise CheckError(f"cannot tell which {label} archive to read")
    archive = tree / "dl" / name
    if not archive.is_file():
        raise CheckError(
            f"{archive} is missing; pin-daede-source.py should have fetched it before this check"
        )
    return archive


def read_members(archive: Path, pattern: re.Pattern[str]) -> dict[str, str]:
    """Return the text of every archive member matching pattern."""
    found: dict[str, str] = {}
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            if not member.isfile() or not pattern.match(member.name):
                continue
            handle = tar.extractfile(member)
            if handle is None:
                continue
            found[member.name] = handle.read().decode("utf-8", "replace")
    return found


def extract_core(archive: Path, dest: Path, nested: bool) -> None:
    """Extract the core the way the daed Makefile does before it patches it.

    ``nested`` selects the tree inside the daed package archive; otherwise the
    archive is the standalone dae-core one and carries the core at its root.
    """
    prefix = "wing/dae-core/"
    try:
        with tarfile.open(archive, "r:gz") as tar:
            members = []
            for member in tar.getmembers():
                name = member.name
                if nested:
                    index = name.find("/" + prefix)
                    if index < 0:
                        continue
                    relative = name[index + 1 + len(prefix) :]
                else:
                    if "/" not in name:
                        continue
                    relative = name.split("/", 1)[1]
                if not relative:
                    continue
                member.name = relative
                members.append(member)
            for member in members:
                try:
                    tar.extract(member, dest, filter="data")
                except TypeError:  # Python < 3.12 has no extraction filters.
                    tar.extract(member, dest)
    except (tarfile.TarError, OSError) as exc:
        raise CheckError(f"{archive.name} is not a readable gzipped tarball: {exc}") from exc


def apply_core_patches(
    tree: Path, makefile_text: str, core_root: Path, only_if_series: bool
) -> list[str]:
    """Apply the daed patch series to the extracted core, in the Makefile's order.

    The archives are checked in, but the core daed actually builds is the one
    $(DaeCore/Install) + $(DaeCore/ApplyPatch) produce at build time.  Reading
    the archive alone would compare dae's template against an unpatched April
    core and reject every key a compat patch adds, so the series is replayed
    here exactly as the recipe replays it.
    """
    names = (makefile_variable(makefile_text, "DAE_CORE_PATCHES") or "").split()
    if not only_if_series:
        return []
    applied: list[str] = []
    for name in names:
        patch_file = tree / PATCH_DIR / name
        if not patch_file.is_file():
            raise CheckError(
                f"{patch_file} is missing; diy-part2-daed.sh has to install the daed-core "
                f"patch series before this check runs"
            )
        result = subprocess.run(
            ["patch", "-p1", "-s", "-d", str(core_root), "-i", str(patch_file)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            detail = " ".join((result.stdout + result.stderr).split())[:200]
            raise CheckError(
                f"{name} does not apply to {core_root.name}; rebase .github/patches/{name} "
                f"({detail})"
            )
        applied.append(name)
    return applied


def read_config_sources(core_root: Path) -> dict[str, str]:
    """The config package sources of the extracted, patched core."""
    config_dir = core_root / "config"
    if not config_dir.is_dir():
        raise CheckError(f"{core_root} has no config/ package; the core layout changed")
    return {
        path.name: path.read_text(encoding="utf-8", errors="replace")
        for path in sorted(config_dir.glob("*.go"))
    }


def accepted_keys(core_sources: dict[str, str]) -> set[str]:
    """Keys the embedded core's mapstructure decoder knows.

    config/parser.go hands the parsed sections to mapstructure with
    ErrorUnused, so a key is accepted exactly when some field in the config
    package carries it as a ``mapstructure`` tag.
    """
    if not core_sources:
        raise CheckError("the dae-core sources are empty; cannot derive the accepted keys")
    keys: set[str] = set()
    for name, text in core_sources.items():
        if not name.endswith(".go") or name.endswith("_test.go"):
            continue
        for tag in re.findall(r'mapstructure:"([^"]+)"', text):
            if tag and tag != "_":
                keys.add(tag)
    if not keys:
        raise CheckError("the dae-core sources carry no mapstructure tags; the layout changed")
    return keys


def strip_comment_and_quotes(line: str) -> str:
    """Blank out quoted strings and comments so braces/parens can be counted."""
    out: list[str] = []
    quote = ""
    escaped = False
    for char in line:
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            out.append(" ")
            continue
        if char in "'\"":
            quote = char
            out.append(" ")
            continue
        if char == "#":
            break
        out.append(char)
    return "".join(out)


def template_keys(text: str) -> dict[str, list[tuple[int, str]]]:
    """Collect option keys from the template, per top-level section.

    Keys are only collected at paren depth 0 (function arguments such as
    ``domain(suffix: ...)`` are not schema keys) and only inside blocks whose
    direct entries are struct fields (see FIELD_BLOCKS).
    """
    stack: list[str] = []
    paren_depth = 0
    found: dict[str, list[tuple[int, str]]] = {}
    for number, raw in enumerate(text.splitlines(), 1):
        code = strip_comment_and_quotes(raw)
        stripped = code.strip()
        if not stripped:
            continue
        key_match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:", stripped)
        opens_block = stripped.endswith("{")
        if paren_depth == 0 and key_match and not opens_block:
            path = tuple(stack)
            if path in FIELD_BLOCKS or (len(path) == 2 and path[0] == "group"):
                section = stack[0] if stack else "?"
                found.setdefault(section, []).append((number, key_match.group(1)))
        if opens_block:
            name_match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*\{", stripped)
            stack.append(name_match.group(1) if name_match else "?")
        paren_depth += stripped.count("(") - stripped.count(")")
        paren_depth = max(paren_depth, 0)
        closes = stripped.count("}")
        for _ in range(closes):
            if stack:
                stack.pop()
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tree", type=Path, default=Path.cwd(), help="OpenWrt source tree")
    parser.add_argument("--dae-archive", type=Path, help="override the dae package source archive")
    parser.add_argument("--core-archive", type=Path, help="override the dae-core archive to check")
    args = parser.parse_args()

    tree = args.tree.resolve()
    try:
        dae_makefile = read_makefile(tree, DAE_MAKEFILE)
        daed_makefile = read_makefile(tree, DAED_MAKEFILE)
        dae_archive = archive_for(
            tree, makefile_variable(dae_makefile, "PKG_SOURCE"), args.dae_archive, "dae source"
        )
        core_source = makefile_variable(daed_makefile, "DAE_CORE_SOURCE")
        nested = args.core_archive is None and not core_source
        if not nested:
            core_archive = archive_for(tree, core_source, args.core_archive, "dae-core")
            core_label = f"{core_archive.name} (the core pin-daed-core.py selected)"
        else:
            core_archive = archive_for(
                tree, makefile_variable(daed_makefile, "PKG_SOURCE"), None, "daed source"
            )
            core_label = f"{core_archive.name} (the core the package ships)"

        with tempfile.TemporaryDirectory(prefix="dae-config-compat-") as tmp:
            core_root = Path(tmp)
            extract_core(core_archive, core_root, nested)
            # An explicit --core-archive is a caller override, so that archive is
            # taken as-is; the build path always replays the series.
            applied = apply_core_patches(
                tree, daed_makefile, core_root, only_if_series=args.core_archive is None
            )
            core_sources = read_config_sources(core_root)
        if applied:
            core_label += f", series applied: {', '.join(applied)}"

        templates = read_members(dae_archive, TEMPLATE_PATTERN)
        if not templates:
            raise CheckError(
                f"{dae_archive.name} carries no example.dae; cannot check what dae ships"
            )
        template_name, template_text = min(templates.items(), key=lambda item: item[0].count("/"))
        keys = accepted_keys(core_sources)
        log(f"core: {core_label}, {len(keys)} config keys")
        log(f"template: {template_name} from {dae_archive.name}")

        used = template_keys(template_text)
        missing: list[str] = []
        for section in sorted(used):
            for number, key in used[section]:
                if key not in keys:
                    missing.append(f"{template_name}:{number} {section}.{key}")
        if missing:
            print(
                "ERROR: the dae-core daed builds rejects keys that dae's own example.dae ships.\n"
                "       daed parses its stored config with this core and rejects unknown keys, so\n"
                "       such a config makes it drop the whole stored configuration and run an\n"
                "       empty data plane (direct-only) instead of failing loudly.\n"
                "       Extend .github/patches/dae-core-config-compat.patch (its header has the\n"
                "       recipe) or move the dae-core pin forward:\n",
                file=sys.stderr,
            )
            for entry in missing:
                print(f"         {entry}", file=sys.stderr)
            return 1
        log(f"all {sum(len(v) for v in used.values())} template keys are accepted")
        return 0
    except CheckError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
