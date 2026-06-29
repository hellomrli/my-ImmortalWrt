# 更新日志

所有重要的项目变更都会记录在此文件中。

## [3.0.0] - 2026-06-29

### Added
- ✅ 新增官方 OpenWrt 编译支持（main 分支）
- ✅ **Official OpenWrt 完整移植 ImmortalWrt 配置**（包括所有第三方插件）
- ✅ 多源多分支矩阵构建系统（openwrt-builder.yml）
- ✅ 独立的 configs/ 目录管理不同源的配置文件
- ✅ 独立的 scripts/ 目录管理不同源的定制脚本
- ✅ 构建产物按源和分支分类命名
- ✅ 构建矩阵按输入动态生成，无效组合会直接失败并提示

### Official OpenWrt 移植的完整特性
- ✅ **第三方插件**：OpenClash + Lucky + Watchdog（与 ImmortalWrt 版本完全一致）
- ✅ **Golang 升级**：使用 sbwml/packages_lang_golang 23.x 分支
- ✅ 完整的网卡驱动支持（包括 Intel I226-V 的 kmod-igc）
- ✅ USB 网卡驱动（Asix、RTL8152 等）
- ✅ 面向软路由场景精简文件系统和显卡/USB 存储驱动
- ✅ 加密模块优化（AES、SHA 硬件加速）
- ✅ 网络性能优化（Flow Offloading、nftables fullcone、tproxy）
- ✅ SQM / CAKE / BBR 支持
- ✅ QEMU Guest Agent（PVE 支持）
- ✅ 实用工具集（ethtool、htop、iperf3、curl、bash、jq）
- ✅ 中文语言包
- ✅ OpenSSL 性能优化
- ✅ MOLD 链接器

### Changed
- 🔄 **所有版本的插件现在完全一致**，主要区别在于软件源
- 🔄 Official OpenWrt 默认 IP 改为 `192.168.50.1`（与 ImmortalWrt 版本一致）
- 🔄 Release tag 格式升级：`{source}-{branch}-YYYY.MM.DD-HHMM`
- 🔄 Artifact 命名优化：包含源信息
- 🔄 将多源构建能力合并到原 `openwrt-builder.yml`，统一使用单一构建 workflow
- 🔄 ImmortalWrt 配置移动到 `configs/immortalwrt.config`，移除根目录 `.config`
- 🔄 Update Checker 按源和分支独立检测，只触发变更目标
- 🔄 Official OpenWrt 显式选择网卡驱动包，避免只依赖 DEFAULT 配置
- 🔄 保留 PPPoE 用户态包，修复 PPP 内核模块与用户态包配置不一致
- 🔄 关闭 i915、crash dump、KEXEC、额外 USB 存储和 exFAT/NTFS3/F2FS 支持

### 关键发现
- 🔍 **OpenWrt main 分支已经使用 APK + 6.18 内核**（与 ImmortalWrt 同步）
- 🔍 三个版本的插件和优化完全相同，仅软件源不同

### 版本对比总结
| 版本 | 软件源 | 包管理 | 内核 |
|------|-------|--------|------|
| ImmortalWrt master | ImmortalWrt | APK | 6.18 |
| ImmortalWrt openwrt-25.12 | ImmortalWrt | APK | 6.18 |
| OpenWrt main | Official | APK | 6.18 |

### Performance
- ⚡ 缓存策略优化：按源和分支分别缓存
- ⚡ 多源并行构建支持

## [2.0.0] - 2026-06-14

### Added
- ✅ GitHub Actions 构建缓存（DL + Build 目录）
- ✅ 构建失败自动重试机制（3次尝试）
- ✅ 版本信息注入到固件（/etc/openwrt_release_custom）
- ✅ README 徽章（构建状态、版本、下载量）
- ✅ .gitattributes 语言统计优化

### Changed
- 🔄 构建速度提升 60-70%（二次构建）
- 🔄 改进错误处理和日志输出

### Performance
- ⚡ 首次构建：~2-3 小时
- ⚡ 缓存构建：~30-60 分钟

## [1.0.0] - 之前版本

### Added
- 集成 luci-app-watchdog 登录防护
- 支持 Intel I226-V 网卡（kmod-igc）
- PVE Guest Agent 支持（qemu-ga）
- 集成 OpenClash、Lucky 等常用插件
- SQM / CAKE 队列管理支持

### Changed
- 升级 Golang 到 26.x
- 使用 MOLD 链接器加速编译
- 启用 Flow Offloading（nftables）
- OpenSSL 性能优化

### Fixed
- 修复 block-mount 报错（预置 fstab）
- 修复 APK 源同步问题（移除 video feed）
- 关闭自动挂载扫描
