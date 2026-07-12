<div align="center">

# ImmortalWrt x86_64 软路由固件

[![Build OpenWrt](https://img.shields.io/github/actions/workflow/status/hellomrli/my-ImmortalWrt/openwrt-builder.yml?branch=main&style=for-the-badge&logo=github-actions&label=Build)](https://github.com/hellomrli/my-ImmortalWrt/actions/workflows/openwrt-builder.yml)
[![Release](https://img.shields.io/github/v/release/hellomrli/my-ImmortalWrt?style=for-the-badge&color=32C955)](https://github.com/hellomrli/my-ImmortalWrt/releases)
[![License](https://img.shields.io/github/license/hellomrli/my-ImmortalWrt?style=for-the-badge&color=blueviolet)](LICENSE)

</div>

这是一个面向 x86_64 软路由 / PVE / QEMU 的 ImmortalWrt 固件构建仓库。当前固件按实际路由器 `192.168.50.1` 的最终软件结构整理，重点是 **dae / daed 双后端透明代理 + dnsmasq + 双 AdGuardHome DNS 分流**，并保留常用管理、QoS、UPnP、SFTP 和虚拟化组件。

固件发布名称保持正式的 `immortalwrt`，不再使用额外的 `-daed` 后缀。目前仅保留两个构建分支：

| 固件 | 上游分支 | 推荐下载 |
| --- | --- | --- |
| `immortalwrt-master` | ImmortalWrt `master` | `squashfs-combined-efi.img.gz` |
| `immortalwrt-openwrt-25.12` | ImmortalWrt `openwrt-25.12` | `squashfs-combined-efi.img.gz` |

## 当前构建概览

<!-- BUILD_TABLE_START -->
| 构建目标 | 构建状态 | 最新版本 | 发布时间 | Release | 推荐下载 |
|----------|----------|----------|----------|---------|----------|
| ImmortalWrt `master` | 已发布 | `immortalwrt-master-2026.07.13-0536` | 2026-07-13 05:36 CST | [下载](https://github.com/hellomrli/my-ImmortalWrt/releases/tag/immortalwrt-master-2026.07.13-0536) | `squashfs-combined-efi.img.gz` |
| ImmortalWrt `openwrt-25.12` | 已发布 | `immortalwrt-openwrt-25.12-2026.07.13-0605` | 2026-07-13 06:06 CST | [下载](https://github.com/hellomrli/my-ImmortalWrt/releases/tag/immortalwrt-openwrt-25.12-2026.07.13-0605) | `squashfs-combined-efi.img.gz` |

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
- 同时内置 `dae` 与 `daed`，通过 `luci-app-daede` 统一管理和切换后端，不再构建 OpenClash 变体。
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

- `luci-app-daede`（统一管理 `dae` / `daed` 双后端）
- `luci-app-firewall`
- `luci-app-lucky`
- `luci-app-package-manager`
- `luci-app-sqm`
- `luci-app-upnp`
- `luci-app-watchdog`
- 中文语言包

### DNS / 代理

- `dae`（独立核心后端，来自 `kenzok8/openwrt-daede`）
- `daed`（Dashboard 整合后端，来自 `kenzok8/openwrt-daede`）
- `adguardhome`（官方包，预置 `adh-direct` / `adh-proxy` 双实例配置）
- `dnsmasq-full`
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

固件使用 ImmortalWrt 官方 `packages/net/adguardhome` 提供 `/usr/bin/AdGuardHome` 二进制，并通过 overlay 预置两个 procd 服务和两个 symlink（用于 daed 按进程名区分 direct/proxy）：

- `/etc/init.d/adh-direct`
- `/etc/init.d/adh-proxy`
- `/usr/bin/AdGuardHome-direct -> /usr/bin/AdGuardHome`
- `/usr/bin/AdGuardHome-proxy -> /usr/bin/AdGuardHome`

以及两份独立配置：

- `/etc/AdGuardHome-direct.yaml`
- `/etc/AdGuardHome-proxy.yaml`

官方单实例 `/etc/init.d/adguardhome` 会在首次启动时被禁用，避免与双实例端口冲突。默认模板不会提交现有路由器的 ADH Web 登录密码哈希；全新刷机后请自行设置 Web 登录信息，保留配置升级时则会通过 sysupgrade 继续保留现有 YAML。

更详细的 DNS 方案记录见：[`docs/dnsmasq-daed-dual-adh.md`](docs/dnsmasq-daed-dual-adh.md)。

## Go 工具链

构建时直接使用 ImmortalWrt 官方 `packages/lang/golang`：

- 已核对 `immortalwrt/packages` 的 `master` 与 `openwrt-25.12` 分支均默认 `GO_DEFAULT_VERSION:=1.26`，当前为 Go 1.26.4。
- 构建脚本不再覆盖 `feeds/packages/lang/golang`，由 ImmortalWrt 官方 Go helper 编译 kenzok8 的 `dae` 与 `daed` 包。
- 不再通过 `actions/setup-go` 强制外部 bootstrap，按官方 Golang 包自身逻辑处理 Go bootstrap。

## 配置保留与升级

### 固件内的保护

项目使用 `/lib/upgrade/keep.d/my-immortalwrt` 保留非标准配置，而不是只依赖
`/etc/sysupgrade.conf`。`keep.d` 位于固件只读层，旧版本遗留的 overlay 文件不会遮蔽后续规则更新；
`/etc/sysupgrade.conf` 仍保留给用户填写设备专属路径。

项目规则包含：

```text
/etc/config/dae
/etc/config/daed
/etc/config/daede
/etc/dae
/etc/daed
/etc/AdGuardHome-direct.yaml
/etc/AdGuardHome-proxy.yaml
/etc/config/lucky
/etc/config/lucky.daji
/etc/config/watchdog
/etc/crontabs/root
```

`/etc/config` 下的 network、dhcp、firewall、SQM、UPnP 等 UCI 配置，以及系统标记为
conffile 的密码、SSH key、证书等文件，仍由标准 sysupgrade 机制处理。**已安装的软件包本身不会
因为“保留配置”而自动保留**，所以备份工具同时用 `-k` 导出软件包清单。

### 下一次升级前必须做的事

> 备份清单由当前正在运行的旧固件生成。刚在仓库或新固件里增加规则，不能补救尚未完成的这次升级。
> 如果当前路由器还没有 `my-sysupgrade-backup`，请直接使用下面的兼容命令；其中 `-c` 会额外保存
> `/etc` 下所有发生过变更的文件，可覆盖旧固件保留规则不完整的问题。

```sh
# 1. 确认当前不是临时 RAM overlay；若命中 /tmp/root，先备份且不要直接重启
mount | grep -E ' /overlay |overlayfs:/tmp/root'

# 2. 生成包含 /etc 本地变更和已安装软件包清单的备份
sysupgrade -c -k -b /tmp/backup-before-upgrade.tar.gz

# 3. 验证压缩包可读取，并抽查关键配置
# 输出路径可能带或不带开头的 /，所以只匹配关键名称
tar -tzf /tmp/backup-before-upgrade.tar.gz >/dev/null
tar -tzf /tmp/backup-before-upgrade.tar.gz | grep -E   '(^|/)etc/(config/(network|dhcp|firewall|daed|lucky|lucky\.daji|watchdog)|daed/|AdGuardHome-(direct|proxy)\.yaml|shadow|passwd)'
sha256sum /tmp/backup-before-upgrade.tar.gz
```

然后立刻通过 SCP/SFTP/LuCI 把备份下载到电脑或 NAS；`/tmp` 位于内存，重启或刷机后会消失。

已经运行本项目新固件时，可用内置工具完成相同操作并自动核验关键路径：

```sh
my-sysupgrade-backup
# 也可直接写到已挂载的持久磁盘：
my-sysupgrade-backup /mnt/sda2/my-router-backup.tar.gz
```

### 安全升级步骤

1. 保持同一构建分支升级：`master → master` 或 `openwrt-25.12 → openwrt-25.12`，不要在一次
   保留配置升级中跨分支迁移。
2. EFI 环境继续使用 `squashfs-combined-efi.img.gz`；Legacy BIOS 使用
   `squashfs-combined.img.gz`。不要使用 `rootfs.tar.gz` 做 sysupgrade。
3. 先测试镜像，再执行升级：

```sh
sysupgrade -T /tmp/immortalwrt-x86-64-generic-squashfs-combined-efi.img.gz
sysupgrade -c -k -v /tmp/immortalwrt-x86-64-generic-squashfs-combined-efi.img.gz
```

不要使用 `-n`（不保留配置）或 `-F`（强制跳过兼容性检查）。LuCI 升级时必须勾选“保留配置”；
对尚未包含本项目 `keep.d` 的旧固件，优先使用上面的 CLI `-c -k` 流程。

升级后检查：

```sh
mount | grep -E ' /overlay |overlayfs:/overlay on / '
sysupgrade -l | grep -E 'AdGuardHome-(direct|proxy)|etc/daed|lucky\.daji'
uci show network >/dev/null
uci show dhcp >/dev/null
/etc/init.d/adh-direct status
/etc/init.d/adh-proxy status
```

正常情况下 `/overlay` 应挂载在持久存储上；若根 overlay 显示为 `overlayfs:/tmp/root`，说明配置
正在写入 RAM，**先把配置备份到外部设备，再排查，期间不要重启**。

> 不要用 `dd`、PVE 重新导入整盘、写盘工具覆盖旧磁盘的方式做“保留配置升级”。这些方式会覆盖
> 原分区和 overlay。若必须重建虚拟磁盘，应先导出备份，在新系统中上传后执行
> `sysupgrade -r /tmp/backup-before-upgrade.tar.gz`，检查无误后再重启。

## 鸣谢

- [ImmortalWrt](https://github.com/immortalwrt/immortalwrt)
- [P3TERX/Actions-OpenWrt](https://github.com/P3TERX/Actions-OpenWrt)
- [kenzok8/openwrt-daede](https://github.com/kenzok8/openwrt-daede)
- [AdGuardHome](https://github.com/AdguardTeam/AdGuardHome)
- [Go](https://go.dev/dl/)
- [OpenWrt packages](https://github.com/openwrt/packages)
- [gdy666/luci-app-lucky](https://github.com/gdy666/luci-app-lucky)
- [sirpdboy/luci-app-watchdog](https://github.com/sirpdboy/luci-app-watchdog)
