#!/usr/bin/env python3
"""Export the x86 firmware kernel configuration, excluding BPF header builds."""

import argparse
from pathlib import Path
import shutil
import sys


def export_kernel_config(tree: Path, output: Path) -> None:
    candidates = sorted(
        path
        for path in tree.glob("build_dir/target-*/linux-x86_64/linux-[0-9]*/.config")
        if path.is_file()
    )
    if len(candidates) != 1:
        raise RuntimeError(
            f"expected one x86 firmware kernel configuration, found {len(candidates)}: "
            + ", ".join(str(path) for path in candidates)
        )

    config = candidates[0]
    lines = set(config.read_text(encoding="utf-8").splitlines())
    required = {
        "CONFIG_X86_64": ("y",),
        "CONFIG_BPF_SYSCALL": ("y",),
        "CONFIG_CGROUP_BPF": ("y",),
        "CONFIG_DEBUG_INFO_BTF": ("y",),
        "CONFIG_XDP_SOCKETS": ("y",),
        "CONFIG_NET_SCH_FQ": ("y", "m"),
        "CONFIG_TCP_CONG_BBR": ("y", "m"),
    }
    for symbol, values in required.items():
        if not any(f"{symbol}={value}" in lines for value in values):
            raise RuntimeError(f"{config} is missing required kernel support: {symbol}")

    shutil.copyfile(config, output)
    print(f"Exported firmware kernel configuration from {config} to {output}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tree", type=Path, help="OpenWrt source tree")
    parser.add_argument("output", type=Path, help="Release attachment path")
    args = parser.parse_args()
    export_kernel_config(args.tree, args.output)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        raise SystemExit(1)
