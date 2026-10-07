#!/bin/bash
set -euo pipefail
repo_root="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

sed -i 's/192.168.1.1/192.168.50.250/g' package/base-files/files/bin/config_generate
python3 "$repo_root/.github/scripts/patch-ppp-syncdial.py" package/network/services/ppp/files/ppp.sh

# Same upstream feed metadata workaround as master; no daemon/proxy packages
# from the master's package manifest or overlay are imported into this profile.
rm -rf package/feeds/packages/freeradius3 feeds/packages/net/freeradius3
# Current master also carries a squeezelite-custom/WMA Kconfig cycle. This
# dedicated IPTV image does not use Squeezelite; omit that feed entry entirely.
rm -rf package/feeds/packages/squeezelite feeds/packages/sound/squeezelite
python3 "$repo_root/.github/scripts/fetch-packages.py" \
    --config "$repo_root/.github/packages-iptv.json" --tree "$PWD" \
    --provenance "$PWD/package-provenance.txt"
for package in gxmobile-scan luci-app-gxmobile; do
    mkdir -p "package/$package"
    cp -a "$repo_root/packages/$package/." "package/$package/"
done
printf '\nLocal packages: gxmobile-scan + luci-app-gxmobile (repository source)\n' >> package-provenance.txt

# Reuse only these unchanged maintenance helpers, not the master's proxy files.
mkdir -p files/usr/sbin files/etc/apk files/etc/uci-defaults
cp -a "$repo_root/files/usr/sbin/my-sysupgrade-backup" files/usr/sbin/
cp -a "$repo_root/files/etc/apk/repositories" files/etc/apk/
cp -a "$repo_root/files/etc/uci-defaults/98-fstab-single-boot" files/etc/uci-defaults/
