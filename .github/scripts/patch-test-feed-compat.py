#!/usr/bin/env python3
"""Work around known stale miniupnpd 2.3.11 feed patches, only for Honk test."""

import argparse
import hashlib
from pathlib import Path
import re
import sys

STALE_PATCHES = {
    # 020/030 fixes are already in 2.3.11. Upstream has since rebased
    # 040-improve-logging.patch onto 2.3.11, so it applies cleanly and is kept.
    "020-descr-filter-fix.patch": "4e0f8ddf58cb130044a5f3b92bdf3a8859f8c15e0edbcbcb2b8df42f99e41da1",
    "030-allow-private-fix.patch": "c667bfaa2f1028d1dc44547d4dd4302891799fc0de271a17618eff537b1a2339",
}


def patch(tree: Path) -> list[str]:
    package = tree / "feeds/packages/net/miniupnpd"
    makefile = (package / "Makefile").read_text()
    if not re.search(r"^PKG_VERSION:=2\.3\.11$", makefile, re.MULTILINE):
        print("miniupnpd is not 2.3.11; leaving upstream patches unchanged.")
        return []
    if "PKG_HASH:=91994b127da735b2c97f19992e34420648c0e8c4ace8a4bcb0596e7685c48678" not in makefile:
        raise RuntimeError("miniupnpd 2.3.11 source changed; re-check the compatibility workaround")
    paths = [package / "patches" / name for name in STALE_PATCHES]
    for path in paths:
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() != STALE_PATCHES[path.name]:
            raise RuntimeError(f"Upstream changed {path.name}; refusing to discard an unknown patch")
    removed = []
    for path in paths:
        if path.exists():
            path.unlink()
            removed.append(path.name)
    print("miniupnpd 2.3.11: use upstream parser/private-IP fixes and upstream logging; keep IGD/XML compatibility patches.")
    return removed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tree", type=Path)
    args = parser.parse_args()
    try:
        patch(args.tree)
    except (OSError, RuntimeError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        raise SystemExit(1)
