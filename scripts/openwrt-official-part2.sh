#!/bin/bash
#
# Official OpenWrt DIY script part 2 (After Update feeds)
# Ported configuration from ImmortalWrt version
#
# This is free software, licensed under the MIT License.
#

set -euo pipefail

# Modify default IP to match ImmortalWrt version
sed -i 's/192.168.1.1/192.168.50.1/g' package/base-files/files/bin/config_generate

# 1. 拉取 lucky 源码（端口转发工具）
if [ ! -d package/lucky ]; then
    git clone --depth 1 https://github.com/gdy666/luci-app-lucky.git package/lucky
fi

# 2. 使用 vernesong/OpenClash（官方 OpenWrt 没有自带）
rm -rf feeds/luci/applications/luci-app-openclash package/feeds/luci/luci-app-openclash package/openclash 2>/dev/null || true
git clone --depth 1 https://github.com/vernesong/OpenClash.git package/openclash

# 3. 强制升级 Golang 版本（OpenClash 编译需要）
rm -rf feeds/packages/lang/golang 2>/dev/null || true
git clone --depth 1 https://github.com/sbwml/packages_lang_golang -b 23.x feeds/packages/lang/golang

# 4. 生成自定义 fstab 配置文件 (修复 block-mount 报错)
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

config mount
	option target '/'
	option device '/dev/sda2'
	option enabled '1'
FSTAB

# 5. 构建信息输出
echo "===================="
echo "Official OpenWrt Custom Build Info (ImmortalWrt config + plugins ported)"
echo "Branch: $(git -C . describe --tags --always 2>/dev/null || echo 'unknown')"
echo "Build Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Build Host: GitHub Actions"
echo "Default IP: 192.168.50.1 (modified from 192.168.1.1)"
echo "OpenClash: vernesong/OpenClash"
echo "Lucky: gdy666/luci-app-lucky"
echo "Watchdog: sirpdboy/luci-app-watchdog"
echo "===================="

# 6. 创建版本标识文件（注入到固件）
mkdir -p package/base-files/files/etc
cat > package/base-files/files/etc/openwrt_release_custom << RELEASE
BUILD_DATE="$(date '+%Y%m%d%H%M')"
BUILD_REPO="hellomrli/my-ImmortalWrt"
BUILD_DESC="Official OpenWrt x86_64 for PVE, default IP 192.168.50.1 (ImmortalWrt config + plugins ported)"
BUILD_SOURCE="openwrt-official"
BUILD_CONFIG="immortalwrt-ported-full"
BUILD_PLUGINS="OpenClash+Lucky+Watchdog"
RELEASE
