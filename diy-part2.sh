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

# 0. 补充安装缺失的系统级依赖 (解决 Error 127 的关键)
sudo apt-get update
sudo apt-get install -y quilt

# 1. 拉取 lucky 源码 (根据你说的情况，这是必须的)
git clone https://github.com/gdy666/luci-app-lucky.git package/lucky

# 2. 拉取 daed 源码 (别忘了这个，官方源里也没有)
git clone https://github.com/QiuSimons/luci-app-daed package/dae

# 3. 强制升级 Golang 版本 (命脉：否则 daed 很大几率编译失败)
rm -rf feeds/packages/lang/golang
git clone https://github.com/sbwml/packages_lang_golang -b 26.x feeds/packages/lang/golang

# 4. 强行回答内核编译时的 BPF 交互提问，彻底消灭 [N/y/?] 卡死问题
# 直接向 target/linux/x86/config-6.18 内核底包中注入 eBPF 依赖
# 这样可以彻底绕过 OpenWrt 外层 make defconfig 的无情清理，消灭 [N/y/?] 卡死
echo "CONFIG_NET_SCH_BPF=y" >> target/linux/x86/config-6.18
echo "CONFIG_NET_CLS_BPF=y" >> target/linux/x86/config-6.18
echo "CONFIG_CGROUP_BPF=y" >> target/linux/x86/config-6.18
echo "CONFIG_BPF_SYSCALL=y" >> target/linux/x86/config-6.18
echo "CONFIG_BPF_JIT=y" >> target/linux/x86/config-6.18

# 5. 强制让内核配置自动接受新版本的默认值 (完美适配 6.18 测试内核)
make target/linux/refresh V=s
