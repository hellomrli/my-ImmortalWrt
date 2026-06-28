#!/bin/bash
#
# Official OpenWrt DIY script part 1 (Before Update feeds)
# Ported from ImmortalWrt version
#
# This is free software, licensed under the MIT License.
#

# Add luci-app-watchdog for LuCI login failure auto-ban
if [ ! -d package/watchdog ]; then
    git clone --depth 1 https://github.com/sirpdboy/luci-app-watchdog.git package/watchdog
fi

echo "===================="
echo "Official OpenWrt - DIY Part 1"
echo "Added: luci-app-watchdog"
echo "===================="
