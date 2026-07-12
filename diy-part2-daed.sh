#!/bin/bash
#
# https://github.com/P3TERX/Actions-OpenWrt
# File name: diy-part2-daed.sh
# Description: OpenWrt DIY script part 2 (After Update feeds)
#
# Copyright (c) 2019-2024 P3TERX <https://p3terx.com>
#
# This is free software, licensed under the MIT License.
# See /LICENSE for more information.
#

set -euo pipefail

# Modify default IP
sed -i 's/192.168.1.1/192.168.50.1/g' package/base-files/files/bin/config_generate

# Modify default theme
#sed -i 's/luci-theme-bootstrap/luci-theme-argon/g' feeds/luci/collections/luci/Makefile

# Modify hostname
#sed -i 's/OpenWrt/P3TERX-Router/g' package/base-files/files/bin/config_generate

# 1. 拉取第三方插件源头仓库（不再克隆个人聚合包仓库）。
rm -rf \
    package/lucky \
    package/watchdog \
    package/dae \
    package/luci-app-daed

git clone --depth 1 https://github.com/gdy666/luci-app-lucky.git package/lucky
git clone --depth 1 https://github.com/sirpdboy/luci-app-watchdog.git package/watchdog

# QiuSimons/luci-app-daed 同时提供 daed 后端和 LuCI。必须移除 feeds install
# 生成的官方同名入口，否则 OpenWrt 的包扫描顺序可能静默选回官方旧版本。
rm -rf \
    package/feeds/packages/daed \
    package/feeds/luci/luci-app-daed

git clone --depth 1 --branch kix \
    https://github.com/QiuSimons/luci-app-daed.git package/dae

# 构建前立即验证来源和版本元数据；任一文件缺失都拒绝继续，避免回退。
qiu_daed_makefile="package/dae/daed/Makefile"
qiu_luci_makefile="package/dae/luci-app-daed/Makefile"
for makefile in "$qiu_daed_makefile" "$qiu_luci_makefile"; do
    if [ ! -s "$makefile" ]; then
        echo "ERROR: QiuSimons package Makefile is missing: $makefile" >&2
        exit 1
    fi
done
if ! grep -q '^PKG_SOURCE_URL:=https://github.com/daeuniverse/daed.git$' "$qiu_daed_makefile" ||
   ! grep -q '^CORE_VERSION:=core-' "$qiu_daed_makefile"; then
    echo "ERROR: package/dae/daed is not the expected QiuSimons daed package" >&2
    exit 1
fi
for official_entry in package/feeds/packages/daed package/feeds/luci/luci-app-daed; do
    if [ -e "$official_entry" ] || [ -L "$official_entry" ]; then
        echo "ERROR: official daed package entry still exists: $official_entry" >&2
        exit 1
    fi
done

echo "Using QiuSimons daed packages:"
grep -E '^(PKG_VERSION|DAED_VERSION|WING_VERSION|CORE_VERSION):=' "$qiu_daed_makefile"
grep -E '^(PKG_VERSION|PKG_RELEASE):=' "$qiu_luci_makefile"

# 2. 使用 ImmortalWrt 官方 packages feed 自带的 Golang。
# 官方 master / openwrt-25.12 的 packages/lang/golang 已默认 Go 1.26.x。
# 不额外覆盖官方 Golang，以保持 QiuSimons daed 与 OpenWrt Go helper 的兼容性。
if [ ! -d feeds/packages/lang/golang ]; then
    echo "ERROR: feeds/packages/lang/golang is missing after feeds install" >&2
    exit 1
fi

# 3. 生成自定义 fstab 配置文件，只保留 /boot 挂载，避免把只读 squashfs 根分区当作 extroot
mkdir -p package/base-files/files/etc/config
cat > package/base-files/files/etc/config/fstab << 'FSTAB'
config global
	option anon_swap '0'
	option anon_mount '0'
	option auto_swap '0'
	option auto_mount '1'
	option delay_root '5'
	option check_fs '0'

config mount
	option target '/boot'
	option device '/dev/sda1'
	option enabled '1'
FSTAB


# 3.1. 升级保留规则由 files/lib/upgrade/keep.d/my-immortalwrt 提供。
# 不覆盖 /etc/sysupgrade.conf：该文件留给用户添加设备专属路径；keep.d 位于只读 ROM，
# 不会被旧固件保留下来的 overlay 文件遮蔽，后续规则修复也能随新固件生效。

# 4. 保持 APK 默认源由 ImmortalWrt 构建系统生成，避免混入目录格式源导致 apk update 拉取 APKINDEX.tar.gz
# 不要预置 /etc/apk/repositories.d/customfeeds.list：该文件由 apk-openssl 包提供，
# 放进 base-files 会在 package/install 阶段触发文件归属冲突。
mkdir -p package/base-files/files/etc/apk
cat > package/base-files/files/etc/apk/repositories << 'APKREPOS'
# OpenWrt apk feeds are managed in /etc/apk/repositories.d/distfeeds.list
# Add custom feeds to /etc/apk/repositories.d/customfeeds.list
APKREPOS

# 5. 移除 video 软件源；当前镜像的 video/packages.adb 容易同步不完整，导致 apk update 失败
sed -i '/^CONFIG_FEED_video=y/d' .config 2>/dev/null || true
sed -i '/^# CONFIG_FEED_video is not set/d' .config 2>/dev/null || true
echo '# CONFIG_FEED_video is not set' >> .config

# Ensure x86 squashfs images can initialize and mount persistent F2FS overlay on first boot.
# Without mkfs.f2fs, mount_root falls back to tmpfs overlay and all configuration is lost after reboot.
ensure_config_enabled() {
    local symbol="$1"
    sed -i "/^${symbol}=y$/d;/^# ${symbol} is not set$/d" .config 2>/dev/null || true
    echo "${symbol}=y" >> .config
}

for symbol in \
    CONFIG_PACKAGE_kmod-fs-f2fs \
    CONFIG_PACKAGE_mkf2fs \
    CONFIG_PACKAGE_f2fsck \
    CONFIG_PACKAGE_f2fs-tools \
    CONFIG_PACKAGE_openssh-sftp-server \
    CONFIG_PACKAGE_adguardhome; do
    ensure_config_enabled "$symbol"
done

# 6. 构建信息输出
echo "===================="
echo "ImmortalWrt Custom Build Info"
echo "Branch: $(git -C . describe --tags --always 2>/dev/null || echo 'unknown')"
echo "Build Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Build Host: GitHub Actions"
echo "===================="

# 7. 创建版本标识文件（注入到固件）
mkdir -p package/base-files/files/etc
cat > package/base-files/files/etc/openwrt_release_custom << RELEASE
BUILD_DATE="$(date '+%Y%m%d%H%M')"
BUILD_REPO="hellomrli/my-ImmortalWrt"
BUILD_DESC="ImmortalWrt x86_64 for PVE, default IP 192.168.50.1"
BUILD_PLUGINS="Daed+Dual-AdGuardHome+Lucky+Watchdog+SFTP"
RELEASE
