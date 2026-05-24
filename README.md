# ImmortalWrt x86_64 云编译

基于 [ImmortalWrt](https://github.com/immortalwrt/immortalwrt) 构建的 x86_64 通用固件，面向虚拟机和 x86 软路由使用，当前主要按 PVE + Intel I226-V 直通网卡场景优化。

## 默认参数

| 项目 | 默认值 |
|------|--------|
| **架构** | x86_64 generic |
| **目标设备** | x86/64 Generic |
| **内核版本** | Linux 6.18 |
| **默认 IP** | 192.168.1.1 |
| **默认账号** | root |
| **默认密码** | 无密码（首次登录需设置） |
| **文件格式** | ext4 + squashfs + rootfs.tar.gz |
| **启动镜像** | GRUB + EFI |
| **包管理** | APK |
| **软件源** | 使用 ImmortalWrt 构建系统生成的 APK 源 |
| **链接器** | MOLD |

## 编译分支

| 分支 | 说明 |
|------|------|
| `master` | ImmortalWrt 最新开发版 |
| `openwrt-25.12` | ImmortalWrt 25.12 分支 |

## 已集成的 LuCI 插件

- `luci-app-firewall` — 防火墙管理
- `luci-app-lucky` — Lucky 网络工具 / 端口转发等功能
- `luci-app-openclash` — OpenClash 客户端
- `luci-app-package-manager` — 在线包管理
- `luci-app-sqm` — SQM / CAKE 队列管理
- `luci-app-upnp` — UPnP 端口映射
- `luci-app-watchdog` — LuCI / SSH 登录监控，登录失败可自动加入黑名单

## 主题

- `luci-theme-bootstrap` — 默认 LuCI 主题

## 主要特性

- ✅ 面向 x86_64 软路由构建，支持 ext4、squashfs、rootfs.tar.gz 和 EFI 启动镜像
- ✅ 使用 ImmortalWrt 默认生成的 APK 软件源，不额外覆盖为第三方目录源
- ✅ 移除 video feed，避免镜像同步不完整导致 `apk update` 拉取失败
- ✅ 预置 `/etc/config/fstab`，修复部分环境下 `block-mount` 报错
- ✅ 关闭自动挂载扫描，避免虚拟磁盘被误识别或错误挂载
- ✅ 关闭独立 var 分区模式，单盘部署更省心
- ✅ 使用 MOLD 链接器，加速编译
- ✅ 启用 `firewall4`、`kmod-nf-flow`、`kmod-nft-offload`，使用新版 nftables Flow Offloading 方向
- ✅ 保留 Intel I226-V 所需的 `kmod-igc` 驱动，并集成 `ethtool` 便于查看网卡状态
- ✅ 集成 `qemu-ga`，适配 PVE / QEMU Guest Agent，方便 PVE 识别虚拟机 IP 和执行优雅关机/重启
- ✅ 补齐 x86_64 常用 AES/SHA crypto 模块：`kmod-crypto-aes`、`cbc`、`ctr`、`gcm`、`ghash`、`sha256`、`sha512`
- ✅ OpenSSL 启用速度优化、ASM 和 SSE2：`OPENSSL_OPTIMIZE_SPEED`、`OPENSSL_WITH_ASM`、`OPENSSL_WITH_SSE2`
- ✅ 集成 `luci-app-watchdog`，用于公网 LuCI 登录失败监控和自动封禁辅助防护
- ✅ 为 watchdog 补充运行依赖：`bash`、`curl`、`jq`、`flock`
- ✅ 集成 SQM / CAKE / IFB / BBR 相关组件，便于按需开启延迟优化

## 致谢

- [ImmortalWrt](https://github.com/immortalwrt/immortalwrt)
- [P3TERX/Actions-OpenWrt](https://github.com/P3TERX/Actions-OpenWrt)
- [gdy666/luci-app-lucky](https://github.com/gdy666/luci-app-lucky)
- [sirpdboy/luci-app-watchdog](https://github.com/sirpdboy/luci-app-watchdog)
- [sbwml/packages_lang_golang](https://github.com/sbwml/packages_lang_golang)
