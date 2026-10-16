#!/bin/bash
set -euo pipefail

repo_root="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
bash "$repo_root/diy-part1.sh"

# Unused video packages currently introduce a Qt Kconfig dependency cycle.
sed -i '/^[[:space:]]*src-[^[:space:]]*[[:space:]]\+video[[:space:]]/d' feeds.conf.default
