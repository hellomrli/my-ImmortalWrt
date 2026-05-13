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

# 4. 替换 APK 默认源为清华镜像
mkdir -p package/base-files/files/etc/apk
cat > package/base-files/files/etc/apk/repositories << 'APKREPOS'
https://mirrors.tuna.tsinghua.edu.cn/openwrt/snapshots/targets/x86/64/packages
https://mirrors.tuna.tsinghua.edu.cn/openwrt/snapshots/packages/x86_64/base
https://mirrors.tuna.tsinghua.edu.cn/openwrt/snapshots/packages/x86_64/luci
https://mirrors.tuna.tsinghua.edu.cn/openwrt/snapshots/packages/x86_64/packages
https://mirrors.tuna.tsinghua.edu.cn/openwrt/snapshots/packages/x86_64/routing
https://mirrors.tuna.tsinghua.edu.cn/openwrt/snapshots/packages/x86_64/telephony
https://mirrors.tuna.tsinghua.edu.cn/openwrt/snapshots/packages/x86_64/video
APKREPOS
