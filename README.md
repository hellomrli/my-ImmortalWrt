<div align="center">

# ImmortalWrt x86_64 软路由固件

[![Build OpenWrt](https://img.shields.io/github/actions/workflow/status/hellomrli/my-ImmortalWrt/openwrt-builder.yml?branch=main&style=for-the-badge&logo=github-actions&label=Build)](https://github.com/hellomrli/my-ImmortalWrt/actions/workflows/openwrt-builder.yml)
[![Release](https://img.shields.io/github/v/release/hellomrli/my-ImmortalWrt?style=for-the-badge&color=32C955)](https://github.com/hellomrli/my-ImmortalWrt/releases)
[![License](https://img.shields.io/github/license/hellomrli/my-ImmortalWrt?style=for-the-badge&color=blueviolet)](LICENSE)

</div>

这是一个面向 x86_64 软路由 / PVE / QEMU 的 ImmortalWrt 固件构建仓库。当前固件按实际路由器 `192.168.50.1` 的最终软件结构整理，重点是 **Daed 透明代理 + dnsmasq + 双 AdGuardHome DNS 分流**，并保留常用管理、QoS、UPnP、SFTP 和虚拟化组件。

固件发布名称保持正式的 `immortalwrt`，不再使用额外的 `-daed` 后缀。目前仅保留两个构建分支：

| 固件 | 上游分支 | 推荐下载 |
| --- | --- | --- |
| `immortalwrt-master` | ImmortalWrt `master` | `squashfs-combined-efi.img.gz` |
| `immortalwrt-openwrt-25.12` | ImmortalWrt `openwrt-25.12` | `squashfs-combined-efi.img.gz` |

## 当前构建概览

<!-- BUILD_TABLE_START -->
| 构建目标 | 构建状态 | 最新版本 | 发布时间 | Release | 推荐下载 |
|----------|----------|----------|----------|---------|----------|
| ImmortalWrt `master` | 构建中 | `immortalwrt-master-2026.07.08-0112` | 2026-07-08 01:13 CST | [下载](https://github.com/hellomrli/my-ImmortalWrt/releases/tag/immortalwrt-master-2026.07.08-0112) | `squashfs-combined-efi.img.gz` |
| ImmortalWrt `openwrt-25.12` | 构建中 | `immortalwrt-openwrt-25.12-2026.07.08-0142` | 2026-07-08 01:42 CST | [下载](https://github.com/hellomrli/my-ImmortalWrt/releases/tag/immortalwrt-openwrt-25.12-2026.07.08-0142) | `squashfs-combined-efi.img.gz` |

> 此表由 GitHub Actions 自动更新；新 Release 发布后会同步最新版本和链接。
<!-- BUILD_TABLE_END -->

## 默认参数

| 项目 | 默认值 |
| --- | --- |
| 架构 | `x86_64 generic` |
| 默认地址 | `192.168.50.1` |
| 默认用户 | `root` |
| 默认密码 | 空密码，首次登录后自行设置 |
| 包管理 | `APK` |
| 默认主题 | `luci-theme-bootstrap` |
| 固件格式 | `squashfs-combined*.img.gz` / `rootfs.tar.gz` |
| 启动方式 | GRUB / EFI |

## 固件特性

- 基于 ImmortalWrt x86_64，适合 PVE、QEMU 和常规 x86 软路由。
- 默认 LAN IP 改为 `192.168.50.1`，避免和常见上级路由 `192.168.1.1` 冲突。
- 统一使用 Daed 透明代理方案，不再构建 OpenClash 变体。
- 内置 `dnsmasq + daed + 双 AdGuardHome` DNS 分流结构。
- 双 AdGuardHome 以独立运行时服务形式安装，不使用 `luci-app-adguardhome` 管理。
- 预装 `openssh-sftp-server`，方便后续通过 SFTP / SCP 传递文件。
- 预装 `qemu-ga`，适合 PVE / QEMU 虚拟机管理、关机和状态识别。
- 启用常用 x86 网卡驱动：Intel I225/I226、e1000e、igb、ixgbe、r8125、r8168、vmxnet3 等。
- 启用 SQM / CAKE / IFB / BBR、nftables flow offload、fullcone、tproxy 等网络组件。
- 保留 F2FS overlay 初始化工具，避免 squashfs 固件首次启动后落到 tmpfs overlay 导致重启丢配置。
- Release 附带最终 `.config` 和 kernel `.config`，方便追踪实际构建配置。

## 主要组件

### LuCI / 管理

- `luci-app-daed`
- `luci-app-firewall`
- `luci-app-lucky`
- `luci-app-package-manager`
- `luci-app-sqm`
- `luci-app-upnp`
- `luci-app-watchdog`
- 中文语言包

### DNS / 代理

- `daed`
- `adguardhome-dual`
- `dnsmasq-full`
- `daed-geoip` / `daed-geosite`
- `v2ray-geoip` / `v2ray-geosite`

### 系统工具

- `bash`
- `curl`
- `ethtool`
- `htop`
- `iperf3`
- `jq`
- `openssh-sftp-server`
- `qemu-ga`
- `unzip`
- `ntfs3-mount`
- `lm-sensors`

## DNS 分流结构

当前 DNS 链路设计如下：

```text
LAN clients
  ↓ DNS :53
dnsmasq
  ↓ daed 透明 DNS 接管 / 分流
daed DNS routing
  ├─ 国内 / private 域名 → ADH-direct :50530 → ISP DNS
  └─ 国外 / fallback    → ADH-proxy  :50531 → DoH DNS
```

端口规划：

| 组件 | 地址 | 端口 | 用途 |
| --- | --- | ---: | --- |
| dnsmasq | LAN / loopback | 53 | LAN DNS 入口 |
| ADH-direct DNS | `127.0.0.1` / `::1` | 50530 | 国内 DNS 后端 |
| ADH-proxy DNS | `127.0.0.1` / `::1` | 50531 | 国外 DNS 后端 |
| ADH-direct Web | `192.168.50.1` | 50080 | 国内实例管理 |
| ADH-proxy Web | `192.168.50.1` | 50081 | 国外实例管理 |
| daed Web | `0.0.0.0` / `::` | 2023 | Daed 管理 |

`adguardhome-dual` 来自 [`hellomrli/my-openwrt-packages`](https://github.com/hellomrli/my-openwrt-packages)，安装两个 procd 服务：

- `/etc/init.d/adh-direct`
- `/etc/init.d/adh-proxy`

以及两份配置：

- `/etc/AdGuardHome-direct.yaml`
- `/etc/AdGuardHome-proxy.yaml`

默认模板不会提交现有路由器的 ADH Web 登录密码哈希；全新刷机后请自行设置 Web 登录信息，保留配置升级时则会通过 sysupgrade 继续保留现有 YAML。

更详细的 DNS 方案记录见：[`docs/dnsmasq-daed-dual-adh.md`](docs/dnsmasq-daed-dual-adh.md)。

## Go 工具链

构建时使用 [`my-openwrt-packages/golang`](https://github.com/hellomrli/my-openwrt-packages/tree/main/golang) 覆盖默认 feed 中的 Go 打包目录：

- 打包结构基于 OpenWrt 官方 `packages/lang/golang`。
- Go 源码来自 Go 官方发布源：`go.dev/dl` / `dl.google.com/go`。
- 当前固定版本：Go `1.26.5`。
- CI 通过 `actions/setup-go` 提供外部 bootstrap GOROOT，避免每次从 Go 1.4 开始重建完整 bootstrap 链。

这样避免 ImmortalWrt / OpenWrt feed 中 Go 版本滞后，同时也不依赖第三方 Golang 包仓库；OpenWrt 仍会从源码构建固件使用的 host Go，只是不再重复构建旧 bootstrap 工具链。

## 配置保留与升级

固件内预置 `/etc/sysupgrade.conf`，额外保留关键运行时配置：

```text
/etc/config/daed
/etc/daed
/etc/AdGuardHome-direct.yaml
/etc/AdGuardHome-proxy.yaml
/usr/bin/AdGuardHome
/etc/init.d/adh-direct
/etc/init.d/adh-proxy
/etc/config/lucky
/etc/config/lucky.daji
/etc/config/watchdog
/etc/crontabs/root
```

升级前建议先备份：

```sh
sysupgrade -b /tmp/backup-before-upgrade.tar.gz
```

升级后确认 overlay 不是 tmpfs：

```sh
mount | grep ' /overlay '
```

正常情况下应挂载到持久化 overlay；如果显示类似 `overlayfs:/tmp/root`，说明当前系统没有正确挂载持久化 overlay，重启后配置可能丢失。

> 不要用 `dd`、PVE 重新导入整盘、写盘工具覆盖旧磁盘的方式做“保留配置升级”。这些方式会覆盖原 overlay。要保留配置，请使用 LuCI / `sysupgrade`，或先导出备份后再恢复。

## 鸣谢

- [ImmortalWrt](https://github.com/immortalwrt/immortalwrt)
- [P3TERX/Actions-OpenWrt](https://github.com/P3TERX/Actions-OpenWrt)
- [QiuSimons/luci-app-daed](https://github.com/QiuSimons/luci-app-daed)
- [AdGuardHome](https://github.com/AdguardTeam/AdGuardHome)
- [Go](https://go.dev/dl/)
- [OpenWrt packages](https://github.com/openwrt/packages)
- [hellomrli/my-openwrt-packages](https://github.com/hellomrli/my-openwrt-packages)
