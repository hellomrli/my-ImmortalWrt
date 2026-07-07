<div align="center">

# ImmortalWrt — x86_64 软路由固件云编译

[![Build OpenWrt](https://img.shields.io/github/actions/workflow/status/hellomrli/my-ImmortalWrt/openwrt-builder.yml?branch=main&style=for-the-badge&logo=github-actions&label=Build)](https://github.com/hellomrli/my-ImmortalWrt/actions/workflows/openwrt-builder.yml)
[![Release](https://img.shields.io/github/v/release/hellomrli/my-ImmortalWrt?style=for-the-badge&color=32C955)](https://github.com/hellomrli/my-ImmortalWrt/releases)
[![Downloads](https://img.shields.io/github/downloads/hellomrli/my-ImmortalWrt/total?style=for-the-badge&color=orange)](https://github.com/hellomrli/my-ImmortalWrt/releases)
[![License](https://img.shields.io/github/license/hellomrli/my-ImmortalWrt?style=for-the-badge&color=blueviolet)](LICENSE)

[![](https://img.shields.io/badge/-目录:-696969.svg)](#readme)
[![](https://img.shields.io/badge/-项目说明-FFFFFF.svg)](#项目说明-)
[![](https://img.shields.io/badge/-快速使用-FFFFFF.svg)](#快速使用)
[![](https://img.shields.io/badge/-固件特色-FFFFFF.svg)](#固件特色-)
[![](https://img.shields.io/badge/-固件下载-FFFFFF.svg)](#固件下载-)
[![](https://img.shields.io/badge/-插件说明-FFFFFF.svg)](#插件说明-)
[![](https://img.shields.io/badge/-定制编译-FFFFFF.svg)](#定制编译-)
[![](https://img.shields.io/badge/-项目结构-FFFFFF.svg)](#项目结构-)
[![](https://img.shields.io/badge/-特别提示-FFFFFF.svg)](#特别提示-)
[![](https://img.shields.io/badge/-鸣谢-FFFFFF.svg)](#鸣谢-)

</div>


## 项目说明 [![](https://img.shields.io/badge/-项目基本介绍-FFFFFF.svg)](#项目说明-)

- 固件源码：[![ImmortalWrt](https://img.shields.io/badge/Source-ImmortalWrt-32C955.svg?style=flat&logo=openwrt)](https://github.com/immortalwrt/immortalwrt) [![Actions](https://img.shields.io/badge/Build-GitHub%20Actions-blueviolet.svg?style=flat&logo=github-actions)](https://github.com/features/actions) [![P3TERX](https://img.shields.io/badge/Base-P3TERX-orange.svg?style=flat)](https://github.com/P3TERX/Actions-OpenWrt)
- 本项目使用 GitHub Actions 自动拉取 ImmortalWrt 源码，编译适用于 x86_64 软路由 / PVE / QEMU 的固件。
- 默认管理地址：`192.168.50.1`，默认用户：`root`，默认密码：空密码（首次登录后请及时设置）。
- 当前保留两个原版 ImmortalWrt / OpenClash 镜像，并额外新增一个 `immortalwrt-daed` 镜像。
- 常用第三方插件统一来自 [`hellomrli/my-openwrt-packages`](https://github.com/hellomrli/my-openwrt-packages)，该仓库定时同步上游插件源码；插件库更新本身不触发固件编译，固件构建开始时会拉取当时最新版插件。
- 本项目仅保留 ImmortalWrt 构建目标：两个 OpenClash 镜像和一个 Daed 镜像。
- Release 仅发布 `squashfs` 相关镜像和 `rootfs.tar.gz`，不再发布 ext4 combined 镜像。
- 每个 Release 附带最终 `.config` 和 kernel `.config`，便于追踪实际构建配置。


## 快速使用

1. 在 [Releases](https://github.com/hellomrli/my-ImmortalWrt/releases) 下载对应构建目标的 `squashfs-combined-efi.img.gz`。
2. 首次全新安装可写盘到虚拟磁盘 / 物理盘；升级已有系统请优先使用 LuCI 或 `sysupgrade`。
3. 首次登录地址：`http://192.168.50.1`，用户 `root`，默认空密码，登录后请立即设置密码。
4. 如果使用 PVE / QEMU，推荐下载 UEFI 镜像，并确认 `qemu-ga` 正常运行。
5. 每次升级前先执行 `sysupgrade -b /tmp/backup-before-upgrade.tar.gz`，并把备份下载到电脑或 NAS。

| 使用场景 | 推荐文件 | 备注 |
|---|---|---|
| PVE / UEFI x86_64 | `squashfs-combined-efi.img.gz` | 默认推荐 |
| Legacy BIOS | `squashfs-combined.img.gz` | 老机器或非 UEFI 环境 |
| 容器 / chroot / 自定义磁盘 | `rootfs.tar.gz` | 需要自行处理启动与分区 |

> 想保留配置时，不要用 `dd`、PVE 重新导入整盘或写盘工具覆盖旧磁盘；这些方式会覆盖原 overlay。请使用 LuCI / `sysupgrade`，或先导出备份后再恢复。


## 固件特色 [![](https://img.shields.io/badge/-本项目固件特色-FFFFFF.svg)](#固件特色-)

1. 面向 x86_64 软路由构建，适配 PVE / QEMU / 常规 x86 设备。
2. 默认 IP 固定为 `192.168.50.1`，避免和常见上级路由 `192.168.1.1` 冲突。
3. 保留原本 OpenClash 版本，同时新增 Daed 版本，方便按需求选择。
4. Daed 镜像单独启用 eBPF / BTF / CGROUP_BPF / XDP_SOCKETS 等内核选项。
5. 集成 Intel I226-V / I225 / e1000e / igb / ixgbe / r8125 / r8168 / vmxnet3 等常用网卡驱动。
6. 集成 `qemu-ga`，便于 PVE / QEMU 虚拟机识别、关机和状态管理。
7. 使用 `firewall4`、nftables flow offload、fullcone、tproxy 等网络组件。
8. 集成 SQM / CAKE / IFB / BBR 相关组件，适合软路由 QoS 场景。
9. 使用 MOLD 链接器和 GitHub Actions 缓存，加快云编译速度。
10. 预置 `/boot` 挂载配置，并保留 F2FS overlay 支持，适合 squashfs 固件升级使用。


## 固件下载 [![](https://img.shields.io/badge/-编译状态及下载链接-FFFFFF.svg)](#固件下载-)

点击下表中的 [![](https://img.shields.io/badge/下载-Release-blueviolet.svg?style=flat&logo=github)](https://github.com/hellomrli/my-ImmortalWrt/releases) 可跳转到对应固件发布页面。

| 构建目标 | 分支 | 插件方案 | 配置文件 | DIY 脚本 | 固件下载 |
| :---: | :---: | :---: | :---: | :---: | :---: |
| [![](https://img.shields.io/badge/ImmortalWrt-master-32C955.svg?logo=openwrt)](https://github.com/hellomrli/my-ImmortalWrt/actions/workflows/openwrt-builder.yml) | `master` | OpenClash + Lucky + Watchdog | [`immortalwrt.config`](configs/immortalwrt.config) | [`diy-part2.sh`](diy-part2.sh) | [![](https://img.shields.io/badge/下载-Release-blueviolet.svg?style=flat&logo=github)](https://github.com/hellomrli/my-ImmortalWrt/releases?q=immortalwrt-master-) |
| [![](https://img.shields.io/badge/ImmortalWrt-25.12-32C955.svg?logo=openwrt)](https://github.com/hellomrli/my-ImmortalWrt/actions/workflows/openwrt-builder.yml) | `openwrt-25.12` | OpenClash + Lucky + Watchdog | [`immortalwrt.config`](configs/immortalwrt.config) | [`diy-part2.sh`](diy-part2.sh) | [![](https://img.shields.io/badge/下载-Release-blueviolet.svg?style=flat&logo=github)](https://github.com/hellomrli/my-ImmortalWrt/releases?q=immortalwrt-openwrt-25.12-) |
| [![](https://img.shields.io/badge/ImmortalWrt--Daed-master-orange.svg?logo=openwrt)](https://github.com/hellomrli/my-ImmortalWrt/actions/workflows/openwrt-builder.yml) | `master` | Daed + Lucky + Watchdog | [`immortalwrt-daed.config`](configs/immortalwrt-daed.config) | [`diy-part2-daed.sh`](diy-part2-daed.sh) | [![](https://img.shields.io/badge/下载-Release-blueviolet.svg?style=flat&logo=github)](https://github.com/hellomrli/my-ImmortalWrt/releases?q=immortalwrt-daed-master-) |

### 当前构建概览

<!-- BUILD_TABLE_START -->
| 构建目标 | 构建状态 | 最新版本 | 发布时间 | Release | 推荐下载 |
|----------|----------|----------|----------|---------|----------|
| ImmortalWrt `master` | 已发布 | `immortalwrt-master-2026.07.07-0608` | 2026-07-07 06:08 CST | [下载](https://github.com/hellomrli/my-ImmortalWrt/releases/tag/immortalwrt-master-2026.07.07-0608) | `squashfs-combined-efi.img.gz` |
| ImmortalWrt `openwrt-25.12` | 已发布 | `immortalwrt-openwrt-25.12-2026.07.07-0642` | 2026-07-07 06:43 CST | [下载](https://github.com/hellomrli/my-ImmortalWrt/releases/tag/immortalwrt-openwrt-25.12-2026.07.07-0642) | `squashfs-combined-efi.img.gz` |
| ImmortalWrt Daed `master` | 已发布 | `immortalwrt-daed-master-2026.07.07-0627` | 2026-07-07 06:27 CST | [下载](https://github.com/hellomrli/my-ImmortalWrt/releases/tag/immortalwrt-daed-master-2026.07.07-0627) | `squashfs-combined-efi.img.gz` |

> 此表由 GitHub Actions 自动更新；新 Release 发布后会同步最新版本和链接。
<!-- BUILD_TABLE_END -->

### 下载建议

- PVE / UEFI 环境优先下载：`squashfs-combined-efi.img.gz`
- Legacy BIOS 环境下载：`squashfs-combined.img.gz`
- 如需容器 / chroot / 手工制作磁盘，可下载：`rootfs.tar.gz`
- 升级前建议备份：`sysupgrade -b /tmp/backup-before-upgrade.tar.gz`
- 更新后确认 `/` 使用持久 overlay，不应显示为 `overlayfs:/tmp/root`


### 防止升级后配置丢失

本仓库的 x86_64 squashfs 镜像已经做了两层防护：

1. 固件构建时强制启用 `kmod-fs-f2fs`、`mkf2fs`、`f2fsck`、`f2fs-tools`，确保首次启动能创建并挂载持久化 F2FS overlay；如果缺少这些包，CI 会直接失败，避免发布“重启后配置丢失”的镜像。
2. 固件内预置 `/etc/sysupgrade.conf`，额外保留 OpenClash、Daed、Lucky、Watchdog 等插件的运行时配置目录，例如 `/etc/openclash`、`/etc/daed`、`/etc/config/lucky.daji`。

升级建议：

```bash
# 升级前先导出备份，下载到电脑或其他安全位置
sysupgrade -b /tmp/backup-before-upgrade.tar.gz

# 查看将会被备份的文件清单，确认包含你的插件配置
sysupgrade -l | sort | grep -E 'openclash|daed|lucky|watchdog|network|dhcp|firewall|passwd|shadow'

# 通过 LuCI / sysupgrade 正常升级，并保留配置；不要使用 -n
sysupgrade -v /tmp/immortalwrt-xxx-squashfs-combined-efi.img.gz
```

注意：如果你把 `*.img.gz` 解压后用 `dd`、PVE 重新导入磁盘、写盘工具或“全盘覆盖”的方式刷入，新镜像会覆盖原磁盘分区，旧 overlay 必然丢失。要保留配置，请优先走 LuCI/`sysupgrade`，或先导出备份并在新系统中恢复。


## 默认参数 [![](https://img.shields.io/badge/-固件默认信息-FFFFFF.svg)](#默认参数-)

| 项目 | 默认值 |
| :---: | :---: |
| 架构 | `x86_64 generic` |
| 目标设备 | `x86/64 Generic` |
| 默认 IP | `192.168.50.1` |
| 默认账号 | `root` |
| 默认密码 | 空密码（首次登录后设置） |
| 包管理 | `APK` |
| 固件格式 | `squashfs-combined*.img.gz` / `rootfs.tar.gz` |
| 启动方式 | GRUB + EFI |
| 默认主题 | `luci-theme-bootstrap` |
| 链接器 | MOLD |


## 插件说明 [![](https://img.shields.io/badge/-LuCI%20插件及组件-FFFFFF.svg)](#插件说明-)

<details open>
<summary><b>├── 原本 ImmortalWrt / OpenClash 镜像</b></summary>
<br/>

- `luci-app-openclash` — OpenClash 客户端，来自 `vernesong/OpenClash`
- `luci-app-lucky` — Lucky 网络工具 / 端口转发等功能
- `luci-app-watchdog` — LuCI / SSH 登录监控，登录失败自动加入黑名单
- `luci-app-sqm` — SQM / CAKE 队列管理
- `luci-app-upnp` — UPnP 端口映射
- `luci-app-firewall` — 防火墙管理
- `luci-app-package-manager` — APK 在线包管理

</details>

<details open>
<summary><b>├── 新增 immortalwrt-daed 镜像</b></summary>
<br/>

- `daed` / `luci-app-daed` — Daed 透明代理，来自 `QiuSimons/luci-app-daed`
- `luci-app-lucky` — Lucky 网络工具 / 端口转发等功能
- `luci-app-watchdog` — LuCI / SSH 登录监控，登录失败自动加入黑名单
- `luci-app-sqm` — SQM / CAKE 队列管理
- `luci-app-upnp` — UPnP 端口映射
- `luci-app-firewall` — 防火墙管理
- `luci-app-package-manager` — APK 在线包管理

Daed 版本额外开启：

```text
CONFIG_DEVEL=y
CONFIG_BPF_TOOLCHAIN_HOST=y
CONFIG_KERNEL_DEBUG_INFO=y
CONFIG_KERNEL_DEBUG_INFO_BTF=y
CONFIG_KERNEL_CGROUPS=y
CONFIG_KERNEL_CGROUP_BPF=y
CONFIG_KERNEL_BPF_EVENTS=y
CONFIG_KERNEL_XDP_SOCKETS=y
CONFIG_PACKAGE_kmod-xdp-sockets-diag=y
```

</details>

<details>
<summary><b>├── 常用系统组件</b></summary>
<br/>

- 网络工具：`ethtool`、`iperf3`、`curl`、`wget-ssl`
- 系统工具：`htop`、`bash`、`jq`、`flock`、`lsblk`、`nano`、`nohup`、`openssh-sftp-server`
- 虚拟化：`qemu-ga`
- 文件系统：VFAT、squashfs、F2FS overlay
- 网络优化：nftables、`ipset`、`kmod-nft-socket`、flow offload、fullcone、tproxy、SQM / CAKE / IFB / BBR
- 加密优化：AES / SHA 常用 crypto 模块、OpenSSL ASM / SSE2 / speed optimize

</details>


## 定制编译 [![](https://img.shields.io/badge/-项目基本编译教程-FFFFFF.svg)](#定制编译-)

1. Fork 本项目到自己的 GitHub 仓库。
2. 按需求修改 `configs/` 中的配置文件，或修改对应的 `diy-part*.sh` 脚本。
3. 进入仓库的 **Actions** 页面，选择 `OpenWrt Builder`。
4. 点击 `Run workflow`，填写需要编译的目标：

   ```text
   sources:  immortalwrt / immortalwrt-daed / all
   branches: master / openwrt-25.12 / all
   ```

5. 等待编译完成后，在 [Releases](https://github.com/hellomrli/my-ImmortalWrt/releases) 下载固件。

<details>
<summary><b>&nbsp;手动触发示例</b></summary>
<br/>

只编译 Daed 镜像：

```text
sources: immortalwrt-daed
branches: master
```

只编译原本 ImmortalWrt 25.12 镜像：

```text
sources: immortalwrt
branches: openwrt-25.12
```

编译全部 3 个目标：

```text
sources: all
branches: all
```

</details>

<details>
<summary><b>&nbsp;本地配置文件说明</b></summary>
<br/>

| 文件 | 用途 |
| :--- | :--- |
| `configs/immortalwrt.config` | 原本两个 ImmortalWrt / OpenClash 镜像配置 |
| `configs/immortalwrt-daed.config` | 新增 Daed 镜像配置 |
| `diy-part1.sh` | feeds 更新前脚本 |
| `diy-part2.sh` | 原本 OpenClash 镜像定制脚本，拉取 `my-openwrt-packages` |
| `diy-part2-daed.sh` | 新增 Daed 镜像定制脚本，拉取 `my-openwrt-packages` |

</details>


## 项目结构 [![](https://img.shields.io/badge/-仓库文件说明-FFFFFF.svg)](#项目结构-)

```text
.
├── .github/
│   ├── workflows/
│   │   ├── openwrt-builder.yml              # 固件编译 workflow
│   │   ├── update-checker.yml               # 上游更新检查
│   │   └── update-readme-build-table.yml    # README 构建表自动更新
│   └── scripts/
│       └── update-readme-build-table.py     # 构建状态表生成脚本
├── configs/
│   ├── immortalwrt.config                   # 原本 ImmortalWrt / OpenClash 配置
│   └── immortalwrt-daed.config              # 新增 Daed 镜像配置
├── diy-part1.sh                             # feeds 更新前脚本
├── diy-part2.sh                             # 原本 OpenClash 镜像脚本
├── diy-part2-daed.sh                        # 新增 Daed 镜像脚本
└── README.md
```


## 特别提示 [![](https://img.shields.io/badge/-使用前请阅读-FFFFFF.svg)](#特别提示-)

- 本项目仅用于个人学习和自用固件编译，请自行承担刷机和升级风险。
- 固件来自上游滚动分支，最新版插件或内核可能存在兼容性问题，稳定使用时无需频繁追新。
- 首次使用建议全新写盘；跨版本升级前务必备份配置。
- Daed 依赖 eBPF / BTF / XDP 等内核能力，如遇 daed 运行异常，请优先检查内核模块和日志。
- 请遵守当地法律法规，本项目不对任何使用后果承担责任。


## 鸣谢 [![](https://img.shields.io/badge/-感谢开源项目-FFFFFF.svg)](#鸣谢-)

- [ImmortalWrt](https://github.com/immortalwrt/immortalwrt)
- [hellomrli/my-openwrt-packages](https://github.com/hellomrli/my-openwrt-packages)
- [P3TERX/Actions-OpenWrt](https://github.com/P3TERX/Actions-OpenWrt)
- [vernesong/OpenClash](https://github.com/vernesong/OpenClash)
- [QiuSimons/luci-app-daed](https://github.com/QiuSimons/luci-app-daed)
- [gdy666/luci-app-lucky](https://github.com/gdy666/luci-app-lucky)
- [sirpdboy/luci-app-watchdog](https://github.com/sirpdboy/luci-app-watchdog)
- [sbwml/packages_lang_golang](https://github.com/sbwml/packages_lang_golang)
- [haiibo/OpenWrt](https://github.com/haiibo/OpenWrt) — README 排版风格参考
