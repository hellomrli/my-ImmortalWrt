# ImmortalWrt x86_64 固件

本仓库为 x86_64 软路由及 PVE/QEMU 用户构建 ImmortalWrt 固件，分别提供 Honk 主路由和独立 IPTV 设备配置。

[![Build](https://github.com/hellomrli/my-ImmortalWrt/actions/workflows/openwrt-builder.yml/badge.svg)](https://github.com/hellomrli/my-ImmortalWrt/actions/workflows/openwrt-builder.yml)
[![MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## 下载并选择设备用途

在 [Releases](https://github.com/hellomrli/my-ImmortalWrt/releases) 按目标选择固件：

| 目标 | 适用场景 | 新装管理地址 |
|---|---|---|
| `immortalwrt-master-*` | Honk + Doona 主路由，双 AdGuardHome DNS 后端 | `192.168.50.1` |
| `immortalwrt-iptv-*` | 独立 IPTV 上联、Lucky 转发和 LuCI 扫描 | `192.168.50.250` |

EFI 设备选 `squashfs-combined-efi.img.gz`，Legacy BIOS 选 `squashfs-combined.img.gz`。全新部署写入新的系统磁盘或新建虚拟机；已有设备先按 [备份与升级指南](docs/upgrading.md) 操作，写盘会覆盖目标磁盘。

新装连接对应 LAN 后，以 `root` 登录 LuCI 并立即设置密码。Honk 默认停用，IPTV 的拨号账号和 Lucky 规则也需自行配置。构建产物不会携带设备私有配置。完成密码设置后，master 设备可用 SSH 连接：

```sh
ssh root@192.168.50.1
```

## 查找已发布构建

<!-- BUILD_TABLE_START -->
| 构建目标 | 构建状态 | 最新版本 | 发布时间 | Release | 推荐下载 |
|----------|----------|----------|----------|---------|----------|
| ImmortalWrt `master`（Honk） | 已发布 | `immortalwrt-master-2026.11.05-1723` | 2026-11-05 17:23 CST | [下载](https://github.com/hellomrli/my-ImmortalWrt/releases/tag/immortalwrt-master-2026.11.05-1723) | `squashfs-combined-efi.img.gz` |
| ImmortalWrt `iptv`（上游 master） | 已发布 | `immortalwrt-iptv-2026.11.05-1701` | 2026-11-05 17:01 CST | [下载](https://github.com/hellomrli/my-ImmortalWrt/releases/tag/immortalwrt-iptv-2026.11.05-1701) | `squashfs-combined-efi.img.gz` |

> 此表由 GitHub Actions 自动更新；新 Release 发布后会同步最新版本和链接。
<!-- BUILD_TABLE_END -->

表格只显示已发布版本；实时构建进度在 [Actions](https://github.com/hellomrli/my-ImmortalWrt/actions/workflows/openwrt-builder.yml)。仓库代码分支是 `main`，表中的 `master`、`iptv` 是固件目标，两者均基于上游 `master`，旧 test/25.12 目标停止构建。

## 配置自己的设备

- [文档入口](docs/index.md)
- [master 配置与组件](docs/firmware.md) · [Honk 行为与 NFQUEUE](docs/honk.md)
- [双 AdGuardHome 管理与验证](docs/adguardhome.md)
- [IPTV 设置、扫描及独立安装](docs/iptv.md)
- [升级时保留配置](docs/upgrading.md)
- [构建、包来源与版本固定](docs/building.md)
- [性能参数及实机检查](docs/performance.md)

固件编入的功能不等于设备已经启用；保留配置升级会沿用用户设置，也不会自动采用新版 DNS 默认值。内核模块必须与设备实际内核匹配。

## 来源与反馈

- [ImmortalWrt](https://github.com/immortalwrt/immortalwrt)
- [P3TERX/Actions-OpenWrt](https://github.com/P3TERX/Actions-OpenWrt)
- [kenzok8/openwrt-honk](https://github.com/kenzok8/openwrt-honk)
- [AdGuardHome](https://github.com/AdguardTeam/AdGuardHome)
- [OpenWrt packages](https://github.com/openwrt/packages)
- [gdy666/luci-app-lucky](https://github.com/gdy666/luci-app-lucky)
- [Lucky 官方发布页](https://release.66666.host/)
- [sirpdboy/luci-app-watchdog](https://github.com/sirpdboy/luci-app-watchdog)
- [hellomrli/my-openwrt-packages](https://github.com/hellomrli/my-openwrt-packages)（第三方包镜像）

本仓库构建脚本采用 [MIT License](LICENSE)，固件及第三方组件使用各自许可证。问题请提交 [Issue](https://github.com/hellomrli/my-ImmortalWrt/issues)，提供目标、Release 标签、内核、错误日志和复现步骤，移除设备账户、订阅及密钥。变更记录见 [CHANGELOG.md](CHANGELOG.md)。
