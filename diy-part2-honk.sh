#!/bin/bash
# Production master profile: keep the network baseline, replace dae/daed with Honk.
set -euo pipefail

repo_root="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
sed -i 's/192.168.1.1/192.168.50.1/g' package/base-files/files/bin/config_generate
python3 "$repo_root/.github/scripts/patch-ppp-syncdial.py" \
    package/network/services/ppp/files/ppp.sh

# Remove conflicting proxy definitions and unused packages with Kconfig cycles.
python3 - <<'PY'
from pathlib import Path
import shutil
paths = [
    'package/lucky', 'package/watchdog', 'package/dae', 'package/daed', 'package/honk',
    'package/luci-app-daed', 'package/luci-app-daede',
    'package/feeds/packages/freeradius3', 'feeds/packages/net/freeradius3',
    'package/feeds/packages/squeezelite', 'feeds/packages/sound/squeezelite',
]
for feed in ('packages', 'luci'):
    paths.extend(f'package/feeds/{feed}/{name}' for name in
                 ('dae', 'daed', 'luci-app-dae', 'luci-app-daed', 'luci-app-daede', 'honk', 'luci-app-honk'))
for name in paths:
    path = Path(name)
    if path.is_symlink():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
PY

python3 "$repo_root/.github/scripts/patch-miniupnpd-compat.py" "$PWD"
python3 "$repo_root/.github/scripts/fetch-packages.py" \
    --config "$repo_root/.github/packages-honk.json" \
    --tree "$PWD" --provenance "$PWD/package-provenance.txt"
python3 "$repo_root/.github/scripts/fetch-honk-source.py" \
    --tree "$PWD" --provenance "$PWD/package-provenance.txt"
python3 "$repo_root/.github/scripts/pin-lucky-source.py" \
    --tree "$PWD" --provenance "$PWD/package-provenance.txt"

[ -d feeds/packages/lang/golang ] || { echo 'ERROR: official Golang feed is missing' >&2; exit 1; }

# Add Honk retention only to the staged OpenWrt overlay, not the shared source.
for path in /etc/config/honk /etc/honk; do
    grep -qx "$path" files/lib/upgrade/keep.d/my-immortalwrt || \
        echo "$path" >> files/lib/upgrade/keep.d/my-immortalwrt
done

python3 - <<'PY'
from pathlib import Path
path = Path('.config')
lines = path.read_text().splitlines()
enabled = ('BUILD_LOG', 'PACKAGE_honk', 'PACKAGE_luci-app-honk',
           'PACKAGE_kmod-nft-queue', 'PACKAGE_kmod-nfnetlink-queue',
           'PACKAGE_kmod-fs-f2fs', 'PACKAGE_mkf2fs', 'PACKAGE_f2fsck',
           'PACKAGE_f2fs-tools', 'PACKAGE_openssh-sftp-server', 'PACKAGE_adguardhome')
symbols = {f'CONFIG_{name}' for name in enabled} | {'CONFIG_FEED_video'}
lines = [line for line in lines if not any(line.startswith(key + '=') or line == f'# {key} is not set' for key in symbols)]
lines.extend(f'CONFIG_{name}=y' for name in enabled)
lines.append('# CONFIG_FEED_video is not set')
path.write_text('\n'.join(lines) + '\n')
PY

mkdir -p package/base-files/files/etc
cat > package/base-files/files/etc/openwrt_release_custom <<RELEASE
BUILD_DATE="$(date '+%Y%m%d%H%M')"
BUILD_REPO="hellomrli/my-ImmortalWrt"
BUILD_DESC="ImmortalWrt master x86_64 for PVE (Honk), default IP 192.168.50.1"
BUILD_PLUGINS="Honk+Doona+NFQUEUE+Dual-AdGuardHome+Lucky+Watchdog+SFTP"
RELEASE
cat package-provenance.txt
