# master 默认配置与组件

[返回文档入口](index.md)

本页描述新装模板，已有设备以运行配置为准。当前目标定义见 [targets.json](../.github/targets.json)。

## 新装参数

| 项目 | 默认值 |
| --- | --- |
| 架构 | `x86_64 generic` |
| 默认地址 | `192.168.50.1` |
| 恢复模式地址 | `192.168.50.1` |
| 默认用户 | `root` |
| 默认密码 | 空密码，首次登录后自行设置 |
| 包管理 | `APK` |
| 默认主题 | `luci-theme-bootstrap` |
| 固件格式 | `squashfs-combined*.img.gz` / `rootfs.tar.gz` |
| 启动方式 | GRUB / EFI |
| 内核分区 | 256 MiB |
| 根分区 | 2048 MiB |

> 分区尺寸会直接影响升级行为，详见 [配置保留与升级](upgrading.md)。

## 编入的功能

- 基于 ImmortalWrt x86_64，适合 PVE、QEMU 和常规 x86 软路由。
- 默认 LAN IP 为 `192.168.50.1`，避免和常见上级路由 `192.168.1.1` 冲突。
- 内置 `honk` + `luci-app-honk`（Doona），并编入 `kmod-nft-queue` / `kmod-nfnetlink-queue`。
- 内置 `dnsmasq + Honk + 双 AdGuardHome`；DNS 分流由 Honk 管理。
- 双 AdGuardHome 以独立 procd 服务运行，不使用 `luci-app-adguardhome` 管理。
- 预装 `openssh-sftp-server`，方便通过 SFTP / SCP 传递文件。
- 预装 `qemu-ga`，适合 PVE / QEMU 虚拟机管理、关机和状态识别。
- 启用常用 x86 网卡驱动：Intel I225/I226、e1000e、igb、ixgbe、r8125、r8168、vmxnet3 等。
- 启用 SQM / CAKE / IFB / BBR、nftables flow offload、fullcone、tproxy 等网络组件。
- 强制包含 F2FS overlay 初始化工具，避免 squashfs 固件首次启动落到 tmpfs overlay 导致重启丢配置。
- `/boot` 只使用显式 fstab 项挂载，关闭匿名 block auto-mount，避免同一 FAT 分区被重复挂载。
- 修正上游 PPPoE 脚本在未安装可选 `syncdial` 配置时产生的误导性重连报错。
- Release 附带最终 `.config`、kernel `.config` 和第三方包来源清单。

## 主要组件

### LuCI / 管理

`luci-app-honk`（Doona）、`luci-app-firewall`、`luci-app-lucky`、
`luci-app-package-manager`、`luci-app-sqm`、`luci-app-upnp`、`luci-app-watchdog`、中文语言包。

### DNS / 代理

`honk`、`luci-app-honk`（镜像 `openwrt-honk`，按上游 release 同步 wrapper、Honk core 与
Doona，全部 SHA256 锁定）、`adguardhome`（官方包，预置 `adh-direct` / `adh-proxy` 双实例）、
`dnsmasq-full`、`v2ray-geoip` / `v2ray-geosite`。

### 系统工具

`bash`、`curl`、`ethtool`、`htop`、`iperf3`、`jq`、`openssh-sftp-server`、`qemu-ga`、
`unzip`、`ntfs3-mount`、`lm-sensors`。

DNS 维护见 [双 ADH 指南](adguardhome.md)，IPTV 的独立配置见 [IPTV 文档](iptv.md)。
