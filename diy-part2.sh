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

# Modify default IP
#sed -i 's/192.168.1.1/192.168.50.5/g' package/base-files/files/bin/config_generate

# Modify default theme
#sed -i 's/luci-theme-bootstrap/luci-theme-argon/g' feeds/luci/collections/luci/Makefile

# Modify hostname
#sed -i 's/OpenWrt/P3TERX-Router/g' package/base-files/files/bin/config_generate

# 1. 拉取 lucky 源码 (根据你说的情况，这是必须的)
git clone https://github.com/gdy666/luci-app-lucky.git package/lucky

# 2. 强制升级 Golang 版本 (命脉：否则 daed 很大几率编译失败)
rm -rf feeds/packages/lang/golang
git clone https://github.com/sbwml/packages_lang_golang -b 26.x feeds/packages/lang/golang

# 3. 生成自定义 fstab 配置文件 (修复 block-mount 报错)
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
BUILD_DESC="ImmortalWrt x86_64 for PVE"
RELEASE
