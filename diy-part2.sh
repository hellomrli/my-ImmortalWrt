#!/bin/bash
#
# https://github.com/P3TERX/Actions-OpenWrt
# File name: diy-part2.sh
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

# 1. 拉取个人 OpenWrt 插件库（Lucky / Watchdog / OpenClash / Daed）
rm -rf \
    package/my-openwrt-packages \
    package/lucky \
    package/watchdog \
    package/openclash \
    package/dae \
    feeds/luci/applications/luci-app-openclash \
    package/feeds/luci/luci-app-openclash
if [ ! -d package/my-openwrt-packages ]; then
    git clone --depth 1 https://github.com/hellomrli/my-openwrt-packages.git package/my-openwrt-packages
fi

# 2. 每次启动编译前刷新 Golang 到最新 26.x（仅随固件构建更新，不作为自动触发源）
rm -rf feeds/packages/lang/golang
git clone --depth 1 https://github.com/sbwml/packages_lang_golang -b 26.x feeds/packages/lang/golang

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


# 3.1. 预置 sysupgrade 额外备份清单，保护第三方插件运行时目录。
# /etc/config 默认会被 sysupgrade 备份；这里显式列出关键插件配置和非 UCI 数据目录，
# 避免 OpenClash 订阅/自定义规则、Daed 数据库、Lucky 配置目录在升级后丢失。
cat > package/base-files/files/etc/sysupgrade.conf << 'SYSUPGRADE'
/etc/config/openclash
/etc/openclash
/etc/config/daed
/etc/daed
/etc/config/lucky
/etc/config/lucky.daji
/etc/config/watchdog
/etc/crontabs/root
SYSUPGRADE

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

# Use the GitHub runner/system Go as the bootstrap toolchain for OpenWrt's Go package.
# Building Go's full bootstrap chain (1.4 -> 1.17 -> 1.20 -> 1.22 -> 1.24) on every
# firmware build is slow and fragile on modern CI images; OpenWrt still builds the
# target host Go from source, but it can start from this external bootstrap root.
if command -v go >/dev/null 2>&1; then
    GO_BOOTSTRAP_ROOT="$(go env GOROOT 2>/dev/null || true)"
    if [ -n "$GO_BOOTSTRAP_ROOT" ] && [ -x "$GO_BOOTSTRAP_ROOT/bin/go" ]; then
        sed -i '/^CONFIG_GOLANG_EXTERNAL_BOOTSTRAP_ROOT=/d;/^CONFIG_GOLANG_BUILD_BOOTSTRAP=y$/d;/^# CONFIG_GOLANG_BUILD_BOOTSTRAP is not set$/d' .config 2>/dev/null || true
        printf 'CONFIG_GOLANG_EXTERNAL_BOOTSTRAP_ROOT="%s"\n' "$GO_BOOTSTRAP_ROOT" >> .config
        echo '# CONFIG_GOLANG_BUILD_BOOTSTRAP is not set' >> .config
        echo "Using external Go bootstrap: $GO_BOOTSTRAP_ROOT"
    else
        echo "ERROR: go is present but GOROOT is not usable; cannot configure external Go bootstrap" >&2
        exit 1
    fi
else
    echo "ERROR: go command is missing; actions/setup-go should provide the external Go bootstrap" >&2
    exit 1
fi

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
    CONFIG_PACKAGE_f2fs-tools; do
    ensure_config_enabled "$symbol"
done

# 6. 构建信息输出
echo "===================="
echo "Custom Build Info"
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
RELEASE
