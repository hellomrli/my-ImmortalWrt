#!/usr/bin/env python3
"""Silence the optional syncdial probe when no UCI package is installed."""

from pathlib import Path
import sys


UNSAFE = '[ "$(uci get syncdial.config.enabled)" -eq "1" ] && {'
SAFE = '[ "$(uci -q get syncdial.config.enabled 2>/dev/null)" = "1" ] && {'


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} PPP_PROTO_SCRIPT", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    if not path.is_file():
        raise RuntimeError(f"PPP protocol script is missing: {path}")

    text = path.read_text(encoding="utf-8")
    if text.count(UNSAFE) == 1:
        path.write_text(text.replace(UNSAFE, SAFE), encoding="utf-8")
        print(f"Patched optional syncdial probe in {path}.")
        return 0

    if SAFE in text or "syncdial.config.enabled" not in text:
        print(f"PPP syncdial probe is already safe in {path}.")
        return 0

    raise RuntimeError(f"unrecognized syncdial probe in {path}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
