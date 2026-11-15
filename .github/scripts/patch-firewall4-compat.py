#!/usr/bin/env python3
"""Refresh the FullCone patch after firewall4 removed obsolete IPv6 comments."""

import argparse
from pathlib import Path
import re
import sys


# OpenWrt 358d4214 removed the comments; ImmortalWrt a4ba8240 still carries
# the old FullCone configuration hunk for this firewall4 source revision.
SOURCE_VERSION = "3722eadc088c3ab81389596ca9796112b436583a"
PATCH_NAME = "001-firewall4-add-support-for-fullcone-nat.patch"
STALE_CONTEXT = " # Uncomment this line to disable ipv6 rules\n #\toption disable_ipv6\t1\n"
STALE_HUNK = (
    "--- a/root/etc/config/firewall\n"
    "+++ b/root/etc/config/firewall\n"
    "@@ -5,6 +5,10 @@ config defaults\n"
    " \toption forward\t\tREJECT\n"
    + STALE_CONTEXT
    + "+\toption flow_offloading\t1\n"
    "+\toption flow_offloading_hw\t1\n"
    "+\toption fullcone\t\t1\n"
    "+\toption fullcone6\t0\n"
    " \n"
    " config zone\n"
    " \toption name\t\tlan\n"
)
REFRESHED_HUNK = STALE_HUNK.replace(
    "@@ -5,6 +5,10 @@", "@@ -5,4 +5,8 @@", 1
).replace(STALE_CONTEXT, "", 1)


def patch(tree: Path) -> bool:
    package = tree / "package/network/config/firewall4"
    makefile = (package / "Makefile").read_text(encoding="utf-8")
    version = re.search(r"^PKG_SOURCE_VERSION[ \t]*:?=[ \t]*(\S+)[ \t]*$", makefile, re.MULTILINE)
    if version is None:
        raise RuntimeError("Cannot read the firewall4 source version; re-check the compatibility workaround")
    if version.group(1) != SOURCE_VERSION:
        print("firewall4 uses a different source revision; leaving upstream patches unchanged.")
        return False

    path = package / "patches" / PATCH_NAME
    if not path.exists():
        print("firewall4 has no separate FullCone patch; no context refresh needed.")
        return False
    text = path.read_text(encoding="utf-8")
    if text.count(STALE_HUNK) == 1 and text.count(STALE_CONTEXT) == 1:
        path.write_text(text.replace(STALE_HUNK, REFRESHED_HUNK, 1), encoding="utf-8")
        print("firewall4: refreshed obsolete IPv6 comment context; FullCone and flow-offloading changes retained.")
        return True
    if STALE_CONTEXT not in text:
        print("firewall4 FullCone patch no longer uses the obsolete IPv6 comments; no refresh needed.")
        return False
    raise RuntimeError(f"Unrecognized stale configuration hunk in {path}; re-check the FullCone patch")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tree", type=Path)
    args = parser.parse_args()
    try:
        patch(args.tree)
    except (OSError, RuntimeError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        raise SystemExit(1)
