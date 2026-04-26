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
