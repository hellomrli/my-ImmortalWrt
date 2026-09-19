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

repo_root="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

# Modify default IP
sed -i 's/192.168.1.1/192.168.50.1/g' package/base-files/files/bin/config_generate

# ImmortalWrt carries an optional concurrent-PPPoE hook that probes a syncdial
# UCI package even when it is not installed.  Make the probe quiet and use a
# string comparison so normal PPPoE reconnects do not emit UCI/arithmetic errors.
python3 "$repo_root/.github/scripts/patch-ppp-syncdial.py" \
    package/network/services/ppp/files/ppp.sh

# Modify default theme
#sed -i 's/luci-theme-bootstrap/luci-theme-argon/g' feeds/luci/collections/luci/Makefile

# Modify hostname
#sed -i 's/OpenWrt/P3TERX-Router/g' package/base-files/files/bin/config_generate

# 1. 从项目包镜像 hellomrli/my-openwrt-packages 取第三方插件。
# 镜像每 6 小时同步一次上游，上游删库/改名/转私有时构建仍可继续；只有镜像本身
# 不可达才回退直连上游。包清单见 .github/packages.json。
rm -rf \
    package/lucky \
    package/watchdog \
    package/dae \
    package/luci-app-daed \
    package/luci-app-daede

# kenzok8/openwrt-daede 同时提供 dae、daed 和 luci-app-daede。移除 feeds
# 生成的所有潜在同名/旧版入口，确保包扫描只能选择 kenzok8 的定义。
rm -rf \
    package/feeds/packages/dae \
    package/feeds/packages/daed \
    package/feeds/luci/luci-app-daed \
    package/feeds/luci/luci-app-daede

# ImmortalWrt 官方 packages feed 近期给 freeradius3 引入 kconfig 递归依赖
# （choice depends on PACKAGE_freeradius3-common，而主包 select 它、又 depends
# 于该 choice 成员），make defconfig 解析期整体报错。本固件明确不编译
# freeradius3（# CONFIG_PACKAGE_freeradius3 is not set），直接移除 feed 条目。
rm -rf \
    package/feeds/packages/freeradius3 \
    feeds/packages/net/freeradius3

python3 "$repo_root/.github/scripts/fetch-packages.py" \
    --config "$repo_root/.github/packages.json" \
    --tree "$PWD" \
    --provenance "$PWD/package-provenance.txt"

# dae/daed 的源码包发布在滚动 release（dae-src / daed-src）上，上游只保留最新 3 个
# 资产：镜像里固定的 PKG_SOURCE 一旦被轮换删除，构建就会在下载阶段 404（2026-09-17
# 那次失败即为此）。这里在下载前把 pin 拉回可用资产，并把源码取进 dl/ 校验
# sha256 与目录结构，把上游的意外变成两分钟内的失败。
# GitHub API 不可达时保留镜像原 pin，交给后面的 make download 判定。
python3 "$repo_root/.github/scripts/pin-daede-source.py" \
    --tree "$PWD" \
    --provenance "$PWD/package-provenance.txt"

# dae 的 response_ttl 必须由二进制实现：dae 的配置解析器拒绝未知键
# （config/parser.go: "unexpected key: %v"），而 luci-app-daede 的表单、
# gen-dae-config.sh 与默认配置模板都会写入该键——补丁缺失时带 response_ttl 的
# 配置会让 dae 直接起不来。
#
# 镜像里带的是上游那份照 2026.09.12 源码写的补丁。dae-src 是滚动 release，
# pin-daede-source.py 一旦采用新资产（2026.09.19 起），上游补丁的 hunk 就全部
# 失配：上游把 NormalizeAndCacheDnsResp_ 拆进了 control/dns_controller_cache.go，
# 运行时可调项移到了 control/dns_controller_runtime.go，并且不再把 A/AAAA 应答
# TTL 归零。所以这里用仓库内维护的重建版覆盖镜像那份，保持 pin 自适应上游轮换。
dae_patch_dir="package/dae/dae/patches"
mkdir -p "$dae_patch_dir"
install -m644 "$repo_root/.github/patches/010-dns-response-ttl.patch" \
    "$dae_patch_dir/010-dns-response-ttl.patch"

# 用 pin-daede-source.py 刚取进 dl/ 的源码预检补丁：上游再次重组源码时，这里在
# 两分钟内失败并打印失配的 hunk，而不是拖到两小时后的编译阶段才发现
# （2026.09.19 那次失败即是如此）。取不到 tar 包时只告警，交给后面的下载步骤判定。
dae_src_archives=(dl/dae-src-*.tar.gz)
dae_src_archive="${dae_src_archives[0]}"
if [ -f "$dae_src_archive" ]; then
    dae_patch_check="$(mktemp -d)"
    tar --strip-components=1 -C "$dae_patch_check" -xzf "$dae_src_archive"
    if patch -p1 --dry-run --forward -s -d "$dae_patch_check/core" \
            < "$dae_patch_dir/010-dns-response-ttl.patch"; then
        echo "response_ttl patch applies cleanly to $dae_src_archive"
    else
        echo "ERROR: $dae_patch_dir/010-dns-response-ttl.patch no longer applies to" >&2
        echo "       $dae_src_archive; rebase .github/patches/010-dns-response-ttl.patch" >&2
        echo "       (see the recipe in its header) before rebuilding." >&2
        patch -p1 --dry-run --forward -d "$dae_patch_check/core" \
            < "$dae_patch_dir/010-dns-response-ttl.patch" 2>&1 |
            grep -E 'patching file|FAILED|Hunk' >&2 || true
        rm -rf "$dae_patch_check"
        exit 1
    fi
    rm -rf "$dae_patch_check"
else
    echo "WARNING: no dl/dae-src-*.tar.gz yet; cannot pre-verify the response_ttl patch" >&2
fi

python3 "$repo_root/.github/scripts/patch-daede-defaults.py" package/dae

# 构建前立即验证三包来源和版本元数据；任一文件缺失都拒绝继续，避免回退。
kenzok_dae_makefile="package/dae/dae/Makefile"
kenzok_daed_makefile="package/dae/daed/Makefile"
kenzok_luci_makefile="package/dae/luci-app-daede/Makefile"
for makefile in "$kenzok_dae_makefile" "$kenzok_daed_makefile" "$kenzok_luci_makefile"; do
    if [ ! -s "$makefile" ]; then
        echo "ERROR: kenzok8 package Makefile is missing: $makefile" >&2
        exit 1
    fi
done
# fetch-packages.py 已校验来源和必需文件；这里再确认包名，确保镜像里放的确实是
# openwrt-daede 而不是同路径的其它 dae 变体。
if ! grep -q '^PKG_NAME:=dae$' "$kenzok_dae_makefile" ||
   ! grep -q '^PKG_NAME:=daed$' "$kenzok_daed_makefile" ||
   ! grep -q '^PKG_NAME:=luci-app-daede$' "$kenzok_luci_makefile"; then
    echo "ERROR: package/dae is not the expected openwrt-daede source" >&2
    exit 1
fi
for official_entry in \
    package/feeds/packages/dae \
    package/feeds/packages/daed \
    package/feeds/luci/luci-app-daed \
    package/feeds/luci/luci-app-daede; do
    if [ -e "$official_entry" ] || [ -L "$official_entry" ]; then
        echo "ERROR: official/conflicting daede package entry still exists: $official_entry" >&2
        exit 1
    fi
done

echo "Using kenzok8/openwrt-daede packages:"
grep -E '^(PKG_NAME|PKG_VERSION|PKG_RELEASE):=' "$kenzok_dae_makefile"
grep -E '^(PKG_NAME|PKG_VERSION|PKG_RELEASE):=' "$kenzok_daed_makefile"
grep -E '^(PKG_NAME|PKG_VERSION|PKG_RELEASE):=' "$kenzok_luci_makefile"

# 2. 使用 ImmortalWrt 官方 packages feed 自带的 Golang。
# 官方 master / openwrt-25.12 的 packages/lang/golang 已默认 Go 1.26.x。
# 不额外覆盖官方 Golang，以保持 kenzok8 dae/daed 与 OpenWrt Go helper 的兼容性。
if [ ! -d feeds/packages/lang/golang ]; then
    echo "ERROR: feeds/packages/lang/golang is missing after feeds install" >&2
    exit 1
fi

# 3. 单 /boot 挂载的 fstab 与空白 apk repositories 由 files/ 提供：
#    files/etc/config/fstab（只挂 /boot，禁用匿名 auto-mount，避免把只读 squashfs
#    根分区当作 extroot）和 files/etc/apk/repositories（保持 APK 默认源由构建系统生成，
#    不混入目录格式源）。它们随固件打进 rootfs，与其余 files/ 覆盖一致。

# 4. 升级保留规则由 files/lib/upgrade/keep.d/my-immortalwrt 提供。
# 不覆盖 /etc/sysupgrade.conf：该文件留给用户添加设备专属路径；keep.d 位于只读 ROM，
# 不会被旧固件保留下来的 overlay 文件遮蔽，后续规则修复也能随新固件生效。

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

# 开启 per-package 构建日志。云端 runner 有 6 小时上限，用整轮 `make -j1 V=s`
# 重跑来取错误日志的代价太高；logs/ 会在构建失败时作为 artifact 上传。
ensure_config_enabled CONFIG_BUILD_LOG

# 6. 构建信息输出
echo "===================="
echo "ImmortalWrt Custom Build Info"
echo "Branch: $(git -C . describe --tags --always 2>/dev/null || echo 'unknown')"
echo "Build Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Build Host: GitHub Actions"
if [ -s package-provenance.txt ]; then
    cat package-provenance.txt
fi
echo "===================="

# 7. 创建版本标识文件（注入到固件）
mkdir -p package/base-files/files/etc
cat > package/base-files/files/etc/openwrt_release_custom << RELEASE
BUILD_DATE="$(date '+%Y%m%d%H%M')"
BUILD_REPO="hellomrli/my-ImmortalWrt"
BUILD_DESC="ImmortalWrt x86_64 for PVE, default IP 192.168.50.1"
BUILD_PLUGINS="Dae+Daed+Daede+Dual-AdGuardHome+Lucky+Watchdog+SFTP"
RELEASE
