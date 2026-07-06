# ImmortalWrt x86_64 云编译

[![Build OpenWrt](https://github.com/hellomrli/my-ImmortalWrt/actions/workflows/openwrt-builder.yml/badge.svg)](https://github.com/hellomrli/my-ImmortalWrt/actions/workflows/openwrt-builder.yml)
[![Release](https://img.shields.io/github/v/release/hellomrli/my-ImmortalWrt)](https://github.com/hellomrli/my-ImmortalWrt/releases)
[![License](https://img.shields.io/github/license/hellomrli/my-ImmortalWrt)](LICENSE)
[![Downloads](https://img.shields.io/github/downloads/hellomrli/my-ImmortalWrt/total)](https://github.com/hellomrli/my-ImmortalWrt/releases)

基于 [ImmortalWrt](https://github.com/immortalwrt/immortalwrt) 构建的 x86_64 通用固件，面向虚拟机和 x86 软路由使用，当前主要按 PVE + Intel I226-V 直通网卡场景优化。保留原本两个 ImmortalWrt 镜像不变，并额外新增 `immortalwrt-daed` 镜像。

## 🎯 构建矩阵

| 上游源 | 分支 | 内核 | 包管理 | 默认 IP | 插件 |
|--------|------|------|--------|---------|------|
| **ImmortalWrt** | `master` | 6.18 | APK | 192.168.50.1 | OpenClash + Lucky + Watchdog |
| **ImmortalWrt** | `openwrt-25.12` | 6.18 | APK | 192.168.50.1 | OpenClash + Lucky + Watchdog |
| **immortalwrt-daed** | `master`（ImmortalWrt 主线） | 6.18 | APK | 192.168.50.1 | Daed + Lucky + Watchdog |

> 💡 已移除 Official OpenWrt `main` 构建；原本两个 ImmortalWrt 镜像保持 OpenClash 配置不变，新增的 `immortalwrt-daed` 使用 ImmortalWrt `master` 分支和 Daed。

## 📦 当前构建概览

<!-- BUILD_TABLE_START -->
| 构建目标 | 构建状态 | 最新版本 | 发布时间 | Release | 推荐下载 |
|----------|----------|----------|----------|---------|----------|
| ImmortalWrt `master` | 已发布 | `immortalwrt-master-2026.07.06-1929` | 2026-07-06 19:30 CST | [下载](https://github.com/hellomrli/my-ImmortalWrt/releases/tag/immortalwrt-master-2026.07.06-1929) | `squashfs-combined-efi.img.gz` |
| ImmortalWrt `openwrt-25.12` | 构建中 | `immortalwrt-openwrt-25.12-2026.07.05-1852` | 2026-07-05 18:52 CST | [下载](https://github.com/hellomrli/my-ImmortalWrt/releases/tag/immortalwrt-openwrt-25.12-2026.07.05-1852) | `squashfs-combined-efi.img.gz` |
| OpenWrt Official `main` | 已发布 | `openwrt-main-2026.07.06-1932` | 2026-07-06 19:33 CST | [下载](https://github.com/hellomrli/my-ImmortalWrt/releases/tag/openwrt-main-2026.07.06-1932) | `squashfs-combined-efi.img.gz` |

> 此表由 GitHub Actions 自动更新；新 Release 发布后会同步最新版本和链接。
<!-- BUILD_TABLE_END -->

## 默认参数

| 项目 | 默认值 |
|------|--------|
| **架构** | x86_64 generic |
| **目标设备** | x86/64 Generic |
| **内核版本** | Linux 6.18 |
| **默认 IP** | 192.168.50.1 |
| **默认账号** | root |
| **默认密码** | 无密码（首次登录需设置） |
| **文件格式** | squashfs + rootfs.tar.gz |
| **启动镜像** | GRUB + EFI |
| **包管理** | APK |
| **链接器** | MOLD |

## 已集成的 LuCI 插件

- `luci-app-firewall` — 防火墙管理
- `luci-app-lucky` — Lucky 网络工具 / 端口转发等功能
- `luci-app-openclash` — OpenClash 客户端（原本两个 ImmortalWrt 镜像）
- `luci-app-daed` / `daed` — Daed 透明代理（仅 `immortalwrt-daed`，来自 `QiuSimons/luci-app-daed`）
- `luci-app-sqm` — SQM / CAKE 队列管理
- `luci-app-upnp` — UPnP 端口映射
- `luci-app-watchdog` — LuCI / SSH 登录监控，登录失败可自动加入黑名单

> 📦 **ImmortalWrt 版本额外包含**：`luci-app-package-manager` — 在线包管理（APK 专用）

## 主题

- `luci-theme-bootstrap` — 默认 LuCI 主题

## 主要特性

### 🔌 硬件支持
- ✅ 面向 x86_64 软路由构建，支持 squashfs、rootfs.tar.gz 和 EFI 启动镜像
- ✅ 完整的网卡驱动：Intel I226-V (igc)、8139、e1000/e1000e、igb、ixgbe、r8125/r8168、tg3、vmxnet3 等
- ✅ USB 网卡支持：Asix、RTL8152、RTL8150 等

### 📁 文件系统
- ✅ 面向虚拟机磁盘精简保留 VFAT、squashfs 和 F2FS overlay 支持
- ✅ 关闭额外 USB 存储和桌面显卡驱动，减少软路由固件体积

### ⚡ 性能优化
- ✅ 预置 `/boot` 挂载，避免将只读 squashfs 根分区误作为 extroot
- ✅ 关闭自动挂载扫描，避免虚拟磁盘被误识别或错误挂载
- ✅ 使用 MOLD 链接器，加速编译
- ✅ 启用 `firewall4`、`kmod-nf-flow`、`kmod-nft-offload`、`kmod-nft-fullcone`、`kmod-nft-tproxy`
- ✅ 补齐 x86_64 常用 AES/SHA crypto 模块：硬件加速
- ✅ OpenSSL 启用速度优化、ASM 和 SSE2
- ✅ 集成 SQM / CAKE / IFB / BBR 相关组件
- ✅ 保留 PPPoE 用户态和内核模块，支持常见拨号接入

### 🖥️ 虚拟化
- ✅ 集成 `qemu-ga`，适配 PVE / QEMU Guest Agent

### 🛠️ 实用工具
- ✅ 网络工具：`ethtool`、`iperf3`、`curl`、`wget-ssl`
- ✅ 系统工具：`htop`、`bash`、`jq`、`flock`

### 🌐 国际化
- ✅ 中文语言包支持（zh-cn）

### 🔐 安全
- ✅ 集成 `luci-app-watchdog`，用于公网 LuCI 登录失败监控和自动封禁辅助防护
- ✅ 为 watchdog 补充运行依赖：`bash`、`curl`、`jq`、`flock`

### 📦 第三方插件
- ✅ **OpenClash**：原本两个 ImmortalWrt 镜像保留 `vernesong/OpenClash`
- ✅ **Daed / luci-app-daed**：新增 `immortalwrt-daed` 镜像使用 `QiuSimons/luci-app-daed`
- ✅ **Lucky**：来自 `gdy666/luci-app-lucky`
- ✅ **Watchdog**：来自 `sirpdboy/luci-app-watchdog`
- ✅ **Golang 升级**：使用 `sbwml/packages_lang_golang`
- ✅ **Daed 内核支持**：`immortalwrt-daed` 启用 eBPF / BTF / CGROUP_BPF / XDP_SOCKETS / kmod-xdp-sockets-diag

### ImmortalWrt 版本额外特性
- ✅ 移除 video feed，避免镜像同步不完整导致 `apk update` 拉取失败

## 构建优化（v2.0+）

- ✅ GitHub Actions 缓存加速（DL + Build），二次构建速度提升 60-70%
- ✅ 固定 GitHub Actions 版本，避免上游 main/master 变化导致构建漂移
- ✅ 构建失败自动重试机制
- ✅ 版本信息注入，便于追踪固件来源
- ✅ 多源多分支矩阵构建

## 如何使用

### 手动触发构建

1. 进入 [Actions](https://github.com/hellomrli/my-ImmortalWrt/actions) 页面
2. 选择 `OpenWrt Builder` workflow
3. 点击 `Run workflow`
4. 选择要构建的源和分支（默认 `all` 会构建所有组合）
5. 等待构建完成，从 [Releases](https://github.com/hellomrli/my-ImmortalWrt/releases) 下载

可选值：
- `sources`: `immortalwrt`、`immortalwrt-daed` 或 `all`
- `branches`: `master`、`openwrt-25.12` 或 `all`

### 下载已构建的固件

直接访问 [Releases](https://github.com/hellomrli/my-ImmortalWrt/releases) 页面下载最新构建的固件。

Release tag 格式：
- 原本 ImmortalWrt 镜像：`immortalwrt-master-YYYY.MM.DD-HHMM`、`immortalwrt-openwrt-25.12-YYYY.MM.DD-HHMM`
- 新增 Daed 镜像：`immortalwrt-daed-master-YYYY.MM.DD-HHMM`

### 升级建议

- PVE / UEFI 环境优先下载 `squashfs-combined-efi.img.gz`
- Legacy BIOS 环境下载 `squashfs-combined.img.gz`
- 升级前先备份配置：`sysupgrade -b /tmp/backup-before-upgrade.tar.gz`
- 更新后确认 `/` 使用持久 overlay，不应显示为 `overlayfs:/tmp/root`

## 项目结构

```
.
├── .github/workflows/
│   ├── openwrt-builder.yml        # 多源多分支构建
│   └── update-checker.yml         # 更新检查
├── configs/
│   ├── immortalwrt.config         # 原本 ImmortalWrt / OpenClash 配置文件
│   ├── immortalwrt-daed.config    # 新增 Daed 镜像配置文件
│   └── openwrt-official.config    # 历史保留配置（workflow 不再引用）
├── scripts/                       # 历史保留脚本（workflow 不再引用）
├── diy-part1.sh                   # ImmortalWrt DIY 脚本 part 1
├── diy-part2.sh                   # 原本 ImmortalWrt / OpenClash DIY 脚本 part 2
├── diy-part2-daed.sh              # 新增 Daed 镜像 DIY 脚本 part 2
└── README.md
```

## 版本详细对比

| 对比项 | ImmortalWrt master | ImmortalWrt openwrt-25.12 | immortalwrt-daed master |
|--------|-------------------|---------------------------|--------------------------|
| **软件源** | ImmortalWrt | ImmortalWrt | ImmortalWrt |
| **包管理器** | APK | APK | APK |
| **内核版本** | 6.18 | 6.18 | 6.18 |
| **插件** | OpenClash + Lucky + Watchdog | OpenClash + Lucky + Watchdog | Daed + Lucky + Watchdog |
| **驱动** | 完整 | 完整 | 完整 |
| **优化** | 完整 | 完整 | 完整 + Daed eBPF/BTF/XDP 支持 |

### 选择建议

#### 选择 ImmortalWrt master，如果你：
- ✅ 接受 ImmortalWrt 软件源
- ✅ 需要最新的开发版功能
- ✅ 希望保持原本 OpenClash 镜像不变

#### 选择 ImmortalWrt openwrt-25.12，如果你：
- ✅ 接受 ImmortalWrt 软件源
- ✅ 需要 ImmortalWrt 的稳定分支
- ✅ 希望保持原本 OpenClash 镜像不变

#### 选择 immortalwrt-daed master，如果你：
- ✅ 需要 Daed / luci-app-daed
- ✅ 需要 daed 所需的 eBPF / BTF / XDP 内核支持

> 💡 原本两个 ImmortalWrt 镜像保持不变，`immortalwrt-daed` 是新增镜像。

## 致谢

- [ImmortalWrt](https://github.com/immortalwrt/immortalwrt)
- [P3TERX/Actions-OpenWrt](https://github.com/P3TERX/Actions-OpenWrt)
- [gdy666/luci-app-lucky](https://github.com/gdy666/luci-app-lucky)
- [vernesong/OpenClash](https://github.com/vernesong/OpenClash)
- [QiuSimons/luci-app-daed](https://github.com/QiuSimons/luci-app-daed)
- [sirpdboy/luci-app-watchdog](https://github.com/sirpdboy/luci-app-watchdog)
- [sbwml/packages_lang_golang](https://github.com/sbwml/packages_lang_golang)
