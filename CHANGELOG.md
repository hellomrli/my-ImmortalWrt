# 更新日志

所有重要的项目变更都会记录在此文件中。

## [Unreleased]

### 性能
- 🚀 预置 `/etc/sysctl.d/99-performance.conf`：启用 BBR + fq。`kmod-tcp-bbr` 此前已编入固件却从未激活（仓库里没有任何 sysctl 配置），系统一直在用 cubic。这一项对本固件特别相关——dae 在本机终结客户端 TCP 后会自行向代理服务器建立连接，这些出站连接使用路由器自身的拥塞控制，在有损长 RTT 的国际链路上 BBR 优势明显。
- 🚀 抬高套接字缓冲区上限（16 MiB）、`netdev_max_backlog` 与 `somaxconn`；只改上限、保留接近原厂的默认值，让 Linux 自动调节，避免单连接内存膨胀。
- 🚀 关闭 `tcp_slow_start_after_idle`、开启 `tcp_mtu_probing`：代理连接空闲后突发时不再每次重新慢启动；隧道/代理路径常见的 ICMP 黑洞导致的 PMTU 失败也能规避。
- 🚀 conntrack 上限提到 131072 并同步抬高哈希桶（约 max/4）——代理场景下每条客户端连接消耗两个条目。只提上限不提桶会拖慢每次查表。
- 🚀 扩大临时端口范围，并显式保留 `2023,50080,50081,50530,50531`——扩大后的范围覆盖了本固件的服务端口，不保留的话服务重启时可能因端口被临时连接占用而启动失败。
- 🩹 新增 `/etc/init.d/perf-tune`（START=99）重新应用一次 sysctl 配置：`kmod-nf-conntrack` 没有 AutoLoad，要到防火墙 START=19 才加载，而 `/etc/init.d/sysctl` 在 START=11 用 `sysctl -e` 静默跳过不存在的键——否则 conntrack 两项会毫无提示地不生效。
- 🚀 AdGuardHome 工作目录从 `/var/lib/adguardhome-*` 移到 `/srv/adguardhome-*`。`/var` 是指向 tmpfs 的软链接，原先每次重启都要重新下载全部过滤规则，期间 DNS 拦截不生效。放 `/srv` 同时避免查询日志被 `sysupgrade -c` 卷进备份包。

### 构建产物
- 📦 去除重复的 rootfs 压缩包：`CONFIG_TARGET_ROOTFS_TARGZ` 会用两个名字产出同一份归档（上次发布的两份 sha256 完全相同），每次构建白传约 81 MiB。删除前用 `cmp` 验证内容确实相同，并同步剔除 `sha256sums` 中的对应行。
- 📦 关闭无消费者的 DRM/fb/backlight 共 15 个 kmod：`kmod-drm-i915` 早已关闭且未选任何其它 GPU 驱动。本地控制台不受影响——x86 内核内建 `CONFIG_VGA_CONSOLE=y`，而 `FB_EFI` / `SYSFB_SIMPLEFB` / `DRM_SIMPLEDRM` 均未内建，控制台从未依赖这些模块。
- ⚠️ `CONFIG_KERNEL_DEBUG_INFO` 刻意保留：它看似是配置里最昂贵的一项，但 `DEBUG_INFO_BTF` 依赖它，而 dae/daed 需要内核 BTF；且 BTF 与 `DEBUG_INFO_REDUCED` 互斥，没有折中方案。

### CI / 构建可靠性
- 🧱 第三方包改为经个人镜像 `hellomrli/my-openwrt-packages` 获取（清单见 `.github/packages.json`），上游删库/改名/转私有不再中断构建；镜像不可达时自动回退上游并告警。只抽取清单内的子目录，避免镜像中未使用的 `golang` / `adguardhome-dual` 等包与官方 feed 和本固件 overlay 方案冲突。
- ⚡ 修复 ccache 缓存**从第二次构建起永不更新**的问题：原 key 只由配置文件内容哈希决定，主 key 必然命中，`actions/cache` 因此跳过保存，ccache 长期停留在首次构建的内容。改为 key 追加 `run_id` 轮转 + 前缀 `restore-keys`。
- ⚡ 移除 `dl/` 缓存：仓库缓存总配额只有 10 GB，`dl` + ccache × 2 分支必然超额并触发 LRU 驱逐（连带挤掉 update-checker 的 commit 标记，导致上游没更新也重复构建）。重新下载只花几分钟，冷 ccache 要花几小时。顺带移除了曾两次引发 daed 构建错误的 `go-mod-cache` 排除逻辑。
- ⏱️ 重写编译重试策略：原「多线程 → 单线程全量 → `make clean` + 单线程全量」中，第三档在 runner 的 6 小时上限内不可能完成，只会白烧一整个 runner。改为「并行 → 并行增量重试 → 单线程 `V=s` 增量」，全部增量执行，并给编译步骤加 320 分钟上限（步骤级超时会保留后续步骤，job 级超时不会）。
- 🪵 启用 `CONFIG_BUILD_LOG`，构建失败时把 `logs/` 和 `.config` 作为 artifact 上传，不必再靠整轮 `make -j1 V=s` 重跑取日志。
- 🔁 「已构建」标记改由构建成功后写入：原先 update-checker 在 dispatch 之后立刻缓存 commit hash，构建失败也算已完成，必须等上游再次提交才会重试。
- 💽 移除从未被使用的 `/workdir`（P3TERX 模板残留），并清理更多预装目录；编译前后都输出 `df`。
- 🔐 workflow 权限收敛为默认 `contents: read`，仅发布相关 job 提升；`apt-get`、`make download`、README 推送均加入重试；`make download` 删除截断文件后会重新下载，不再把补下载推迟到编译阶段。
- 🧹 保留 20 条构建运行记录（原为 2 条，失败日志几乎立刻被删导致无法排障）。
- 📉 README 构建表去掉实时「构建中」状态：该瞬时状态每个构建周期产生 4-5 个提交，仓库历史绝大部分是表格抖动。同时移除失效的 `release:` 触发器（GITHUB_TOKEN 创建的 release 不会触发 workflow）。
- 🗑️ 删除已死且已漂移的 `diy-part2.sh`（缺少 `openssh-sftp-server` / `adguardhome` 的强制启用）。
- 🔗 `99-adh-dual` 改为从 `/rom` 恢复 init 脚本，`my-sysupgrade-backup` 改为直接读 `/lib/upgrade/keep.d/my-immortalwrt`，消除同一份内容的三处重复；CI 断言补齐原先遗漏的 `/etc/config/lucky` 与 `/etc/crontabs/root`。

### Changed
- 🔄 构建矩阵收敛为两个正式 ImmortalWrt 固件：`immortalwrt/master` 与 `immortalwrt/openwrt-25.12`；产物名称不再使用 `immortalwrt-daed` 后缀。
- 🔄 固件内容统一按当前 `192.168.50.1` 路由器软件结构构建：Daed + 双 AdGuardHome + Lucky + Watchdog + SQM + UPnP + SFTP。
- 🔄 第三方插件不再从个人聚合仓库拉取：Lucky、Watchdog 直接从各自上游仓库克隆；Golang、AdGuardHome 使用 ImmortalWrt 官方 packages feed。
- 🔄 `dae`、`daed` 与统一管理界面 `luci-app-daede` 全部改用 `kenzok8/openwrt-daede`，并在构建前移除 ImmortalWrt feeds 中的官方同名/旧版入口。
- 🔄 Golang 改为直接使用 ImmortalWrt 官方 `packages/lang/golang`（官方 master/openwrt-25.12 已为 Go 1.26.x），不再用第三方 Golang 覆盖官方 feed。
- 🔄 关闭 ext4 rootfs 与 ext4 文件系统包，Release 仅构建并发布 squashfs 相关镜像和 rootfs.tar.gz。

### Fixed
- 💾 关闭 block-mount 的匿名 `auto_mount`，保留唯一的显式 `/boot` 挂载，并通过 uci-defaults 迁移旧配置，避免 `/dev/sda1` 在 `/boot` 上重复挂载。
- 🌐 修正 ImmortalWrt PPP 脚本对可选 `syncdial` UCI 配置的无条件读取，消除正常 PPPoE 重连时的 `uci: Entry not found` 与 `sh: out of range`。
- 🔐 全新安装的双 AdGuardHome 配置在没有用户密码哈希时只监听 loopback；升级时若旧 YAML 仍为无用户状态，也会自动收回 LAN 暴露，已有认证配置保持原监听地址。
- 🛠️ 按当前实机 `dae + 双 AdGuardHome` 链路补丁 `luci-app-daede` 生成器，默认使用 `127.0.0.1:50530/50531`，移除全局 `ipversion_prefer: 4`，并生成 ADH 进程分流规则，避免 LuCI 保存后覆盖有效 DNS 配置。
- 🛡️ dae 表单生成器拒绝覆盖没有自身生成标记的 `/etc/dae/config.dae`，保护实机中 UCI 表单无法完整表达的手工节点组和 routing 规则。
- 🛠️ `luci-app-daede` 默认激活后端改为当前实机使用的 `dae`，仍保留 `daed` 包供手工切换。
- 🛡️ 将项目升级保留清单迁移到只读层 `/lib/upgrade/keep.d/my-immortalwrt`，避免旧 `/etc/sysupgrade.conf` 遮蔽后续保护规则。
- 🛡️ 新增 `my-sysupgrade-backup`，使用 `sysupgrade -c -k -b` 创建备份，并验证关键配置确实进入压缩包。
- 🛠️ 强制启用并校验 F2FS overlay 所需的 `kmod-fs-f2fs`、`mkf2fs`、`f2fsck` 和 `f2fs-tools`，避免 squashfs 镜像重启后配置落到 tmpfs 而丢失。
- 🛡️ 预置 sysupgrade 项目保留规则，额外保留 Daed、双 AdGuardHome、Lucky、Watchdog 等运行时配置；ADH 二进制由官方 `adguardhome` 包提供，不再备份二进制。

### Added
- ✅ 改用官方 `adguardhome` 包提供 ADH Core，并通过 overlay 提供 `adh-direct` / `adh-proxy` 双实例服务与配置。
- ✅ 预装 `openssh-sftp-server`，方便后续 SFTP/SCP 传递文件。
- ✅ Release 产物附带最终 `.config` 和 kernel `.config`，便于追踪实际构建配置。

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
- 🔄 关闭 i915、crash dump、KEXEC、额外 USB 存储和 exFAT/NTFS3 支持

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
