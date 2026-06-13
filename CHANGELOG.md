# 更新日志

所有重要的项目变更都会记录在此文件中。

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
