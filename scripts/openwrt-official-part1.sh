#!/bin/bash
#
# Official OpenWrt DIY script part 1 (Before Update feeds)
# Ported from ImmortalWrt version
#
# This is free software, licensed under the MIT License.
#

# Keep the official OpenWrt build focused on router packages. The video and
# telephony feeds are not used by this x86_64 image and have caused metadata
# failures in unrelated packages on OpenWrt main.
if [ -f feeds.conf.default ]; then
    sed -i '/^[[:space:]]*src-git[[:space:]]\+\(video\|telephony\)[[:space:]]/d' feeds.conf.default
fi

# Add luci-app-watchdog for LuCI login failure auto-ban
if [ ! -d package/watchdog ]; then
    git clone --depth 1 https://github.com/sirpdboy/luci-app-watchdog.git package/watchdog
fi

echo "===================="
echo "Official OpenWrt - DIY Part 1"
echo "Disabled feeds: video telephony"
echo "Added: luci-app-watchdog"
echo "===================="
