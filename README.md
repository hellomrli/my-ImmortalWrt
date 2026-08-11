<div align="center">

# ImmortalWrt x86_64 软路由固件

[![Build OpenWrt](https://img.shields.io/github/actions/workflow/status/hellomrli/my-ImmortalWrt/openwrt-builder.yml?branch=main&style=for-the-badge&logo=github-actions&label=Build)](https://github.com/hellomrli/my-ImmortalWrt/actions/workflows/openwrt-builder.yml)
[![Release](https://img.shields.io/github/v/release/hellomrli/my-ImmortalWrt?style=for-the-badge&color=32C955)](https://github.com/hellomrli/my-ImmortalWrt/releases)
[![License](https://img.shields.io/github/license/hellomrli/my-ImmortalWrt?style=for-the-badge&color=blueviolet)](LICENSE)

</div>

面向 x86_64 软路由 / PVE / QEMU 的 ImmortalWrt 固件构建仓库。固件按实际路由器
`192.168.50.1` 的软件结构整理，核心是 **dae / daed 双后端透明代理 + dnsmasq + 双 AdGuardHome
DNS 分流**，并保留常用管理、QoS、UPnP、SFTP 和虚拟化组件。默认激活与实机一致的 `dae`
后端，`daed` 保留为可切换后端。

仅保留两个构建分支，发布名称保持正式的 `immortalwrt`：

| 固件 | 上游分支 | 推荐下载 |
| --- | --- | --- |
| `immortalwrt-master` | ImmortalWrt `master` | `squashfs-combined-efi.img.gz` |
| `immortalwrt-openwrt-25.12` | ImmortalWrt `openwrt-25.12` | `squashfs-combined-efi.img.gz` |

## 当前构建概览

<!-- BUILD_TABLE_START -->
| 构建目标 | 构建状态 | 最新版本 | 发布时间 | Release | 推荐下载 |
|----------|----------|----------|----------|---------|----------|
| ImmortalWrt `master` | 已发布 | `immortalwrt-master-2026.08.12-0021` | 2026-08-12 00:21 CST | [下载](https://github.com/hellomrli/my-ImmortalWrt/releases/tag/immortalwrt-master-2026.08.12-0021) | `squashfs-combined-efi.img.gz` |
| ImmortalWrt `openwrt-25.12` | 已发布 | `immortalwrt-openwrt-25.12-2026.08.03-1521` | 2026-08-03 15:21 CST | [下载](https://github.com/hellomrli/my-ImmortalWrt/releases/tag/immortalwrt-openwrt-25.12-2026.08.03-1521) | `squashfs-combined-efi.img.gz` |

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
| 内核分区 | 256 MiB |
| 根分区 | 2048 MiB |

> 分区尺寸会直接影响升级行为，详见 [配置保留与升级](#配置保留与升级)。

## 固件特性

- 基于 ImmortalWrt x86_64，适合 PVE、QEMU 和常规 x86 软路由。
- 默认 LAN IP 为 `192.168.50.1`，避免和常见上级路由 `192.168.1.1` 冲突。
- 同时内置 `dae` 与 `daed`，通过 `luci-app-daede` 统一管理和切换后端。
- 内置 `dnsmasq + dae（默认）/ daed（可选）+ 双 AdGuardHome` DNS 分流结构。
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

`luci-app-daede`（统一管理 `dae` / `daed` 双后端）、`luci-app-firewall`、`luci-app-lucky`、
`luci-app-package-manager`、`luci-app-sqm`、`luci-app-upnp`、`luci-app-watchdog`、中文语言包。

### DNS / 代理

`dae`、`daed`（均来自 `kenzok8/openwrt-daede`）、`adguardhome`（官方包，预置
`adh-direct` / `adh-proxy` 双实例）、`dnsmasq-full`、`v2ray-geoip` / `v2ray-geosite`。

### 系统工具

`bash`、`curl`、`ethtool`、`htop`、`iperf3`、`jq`、`openssh-sftp-server`、`qemu-ga`、
`unzip`、`ntfs3-mount`、`lm-sensors`。

## DNS 分流结构

```text
LAN clients
  ↓ DNS :53
dnsmasq
  ↓ dae 透明 DNS 接管 / 分流（daed 可选）
dae DNS routing
  ├─ 国内 / private 域名 → ADH-direct :50530 → ISP DNS
  └─ 国外 / fallback    → ADH-proxy  :50531 → DoH DNS
```

| 组件 | 地址 | 端口 | 用途 |
| --- | --- | ---: | --- |
| dnsmasq | LAN / loopback | 53 | LAN DNS 入口 |
| ADH-direct DNS | `127.0.0.1` / `::1` | 50530 | 国内 DNS 后端 |
| ADH-proxy DNS | `127.0.0.1` / `::1` | 50531 | 国外 DNS 后端 |
| ADH-direct Web | `127.0.0.1`（首次启动） | 50080 | 设置认证前仅本机可访问 |
| ADH-proxy Web | `127.0.0.1`（首次启动） | 50081 | 设置认证前仅本机可访问 |
| daed Web | `0.0.0.0` / `::` | 2023 | daed 管理 |

固件使用 ImmortalWrt 官方 `packages/net/adguardhome` 提供的 `/usr/bin/AdGuardHome`
二进制，通过 overlay 预置两个 procd 服务和两个 symlink（供 dae 按进程名区分 direct/proxy）：

- `/etc/init.d/adh-direct`、`/etc/init.d/adh-proxy`
- `/usr/bin/AdGuardHome-direct -> /usr/bin/AdGuardHome`
- `/usr/bin/AdGuardHome-proxy -> /usr/bin/AdGuardHome`
- 配置：`/etc/AdGuardHome-direct.yaml`、`/etc/AdGuardHome-proxy.yaml`

官方单实例 `/etc/init.d/adguardhome` 会在首次启动被禁用，避免端口冲突。默认模板不含 Web
登录密码哈希，因此全新刷机时 Web UI 只监听 loopback，不会把无认证管理界面暴露到 LAN。
已有认证配置在 sysupgrade 时保留原 YAML 和监听地址。

全新安装可先通过 SSH 隧道访问：

```sh
ssh -L 50080:127.0.0.1:50080 -L 50081:127.0.0.1:50081 root@192.168.50.1
```

然后打开 `http://127.0.0.1:50080` / `http://127.0.0.1:50081`。设置认证后如需从 LAN 管理，
把对应 YAML 的 `http.address` 改为 `192.168.50.1:50080` / `:50081` 并重启服务。需要手工生成
bcrypt 哈希时，可在装有 Apache 工具的电脑运行 `htpasswd -nBC 10 root`，取冒号后的哈希填入
YAML 的 `users`。

构建阶段会补丁并校验 `luci-app-daede` 的 dae 配置生成器：默认 DNS 上游固定为两个本地 ADH，
不写入全局 `ipversion_prefer: 4`，并保留 ADH-direct 直连、ADH-proxy 走代理的进程规则。
生成器只覆盖带有自身生成标记的配置——实机那份包含复杂节点组和手工 routing 的
`/etc/dae/config.dae` 会被识别为非托管配置，LuCI 表单保存将安全失败而不会清空规则。

详细方案见 [`docs/dnsmasq-daed-dual-adh.md`](docs/dnsmasq-daed-dual-adh.md)。

## 第三方包来源

编译用到的第三方包不直接克隆上游，而是走个人镜像仓库
[`hellomrli/my-openwrt-packages`](https://github.com/hellomrli/my-openwrt-packages)，
上游删库、改名或转为私有时构建仍可继续。

| 包 | 镜像路径 | 上游 |
| --- | --- | --- |
| `dae` / `daed` / `luci-app-daede` | `openwrt-daede` | `kenzok8/openwrt-daede` |
| `lucky` / `luci-app-lucky` | `luci-app-lucky` | `gdy666/luci-app-lucky` |
| `watchdog` / `luci-app-watchdog` | `luci-app-watchdog` | `sirpdboy/luci-app-watchdog` |

包清单是 [`.github/packages.json`](.github/packages.json)，由
[`.github/scripts/fetch-packages.py`](.github/scripts/fetch-packages.py) 在构建时落地：

- **只抽取清单列出的子目录**，不整仓克隆进 `package/`。镜像同时保存了本固件不编译的包
  （`golang`、`adguardhome-dual`、`openclash`、`passwall` 等），整仓引入会与
  `feeds/packages/lang/golang` 及本固件基于 overlay 的双 ADH 方案冲突。
- **镜像优先、上游兜底**：镜像不可达或尚未收录某包时回退直连上游并打印 `::warning::`，构建不中断。
- 落地后校验每个包的必需 `Makefile`，并把实际来源和 commit 写入 `package-provenance.txt`，
  随 Release 发布为 `*_packages.txt`。

上游改动打断构建时，把 `.github/packages.json` 的 `mirror.ref` 从 `main` 改成某个已知可用的
commit SHA，即可一次性冻结全部第三方包。也可用环境变量临时覆盖：

```sh
PKG_MIRROR_REF=<commit>  # 冻结镜像版本
PKG_SOURCE=upstream      # 绕过镜像直连上游
PKG_SOURCE=mirror        # 强制只用镜像，缺包即失败
```

## 构建流水线

GitHub 托管 runner 有几条硬性限制，流水线是围绕它们设计的：

| 限制 | 应对 |
| --- | --- |
| 单 job 6 小时上限 | 编译步骤设 320 分钟**步骤级**超时（步骤超时会保留后续步骤，job 超时不会），失败时仍能上传日志 |
| 仓库 Actions 缓存共 10 GB | 只缓存 ccache（上限 2 GB、开压缩），不缓存 `dl/`；重新下载只花几分钟，冷 ccache 要花几小时 |
| `actions/cache` 命中主 key 就跳过保存 | ccache 用 run 唯一 key + 前缀恢复，并改用显式 `restore` / `save`，失败的构建也能留下部分预热缓存 |
| 磁盘容易 ENOSPC | 清理 dotnet / android / ghc / CodeQL / boost 等预装目录，编译前后都输出 `df` |
| 网络抖动 | `apt-get`、`make download`、`git push` 均带重试；下载后删除截断文件并重新下载 |

其它行为：

- 编译失败时上传 `openwrt/logs`（已启用 `CONFIG_BUILD_LOG`）和 `.config`，保留 14 天。
  不再靠整轮 `make -j1 V=s` 重跑来取日志。
- 重试阶梯全部增量执行：并行 → 并行重试 → 单线程 `V=s`。不再有 `make clean` 后的全量重建
  （那在 6 小时内不可能完成）。
- Update Checker 每 6 小时比对上游 commit；「已构建」标记在**发布成功后**才写入，
  因此构建失败会在下次检查时重试，而不是等上游再次提交。
- 每个分支保留最近 5 个 Release、最近 20 条运行记录。

手动触发：Actions → `OpenWrt Builder` → Run workflow，可指定 `sources` / `branches`。

## 性能调优

固件预置 [`/etc/sysctl.d/99-performance.conf`](files/etc/sysctl.d/99-performance.conf)，
针对「x86 + dae 透明代理」这个具体场景，而不是通用模板。

**BBR 拥塞控制。** 普通路由器开 BBR 没有意义——转发流量由两端主机的拥塞控制决定。
但 dae 会在本机终结客户端 TCP、再向代理服务器发起新连接，**这些出站连接用的是路由器自己的
拥塞控制**。国际链路通常有丢包，cubic 每次丢包都会大幅收缩窗口，BBR 按实测带宽和 RTT 建模，
在有损长 RTT 路径上吞吐明显更高。配套的 `fq` 只作用于没有显式 qdisc 的接口，
WAN 上的 SQM/cake 不受影响。

**套接字缓冲区。** 按本线路的带宽延迟积（1000 Mbit/s 下行 / 100 Mbit/s 上行）计算，
而不是取一个「够大」的数。单条连接要跑满管道需要 BDP 字节的缓冲：

| | 50 ms | 100 ms | 250 ms |
| --- | ---: | ---: | ---: |
| 下行 1000 Mbit/s | 6 MiB | 12 MiB | 30 MiB |
| 上行 100 Mbit/s | 0.6 MiB | 1.2 MiB | 3.0 MiB |

所以接收上限取 32 MiB（覆盖最差的代理 RTT），发送上限 16 MiB（已是 100 Mbit/s 上行需求的
5 倍余量）。**只抬高上限**，中间那个值是每条连接的起始大小、保持内核默认——Linux 会按需
向上自动调节，上限高不占用内存，而调高默认值会乘以连接数。

**连接跟踪。** 代理场景下每条客户端连接消耗两个 conntrack 条目（客户端→路由器、
路由器→代理服务器），所以上限提到 262144，同时把哈希桶提到约 max/4——只提上限不提桶
会让每次查表变慢。代价：条目按需分配、每条约 300 B，表真填满才用到 75 MiB；桶数组预分配
512 KiB。

**并非所有参数都是越大越好。** `netdev_max_backlog` 保持在 16384 而没有拉满：它是缓冲区，
调大不会增加吞吐，只会让报文在 CPU 处理前排更久的队——这就是 bufferbloat。16384 足以吸收
1 Gbit/s 下的突发。

**临时端口范围。** 代理路由器的出站连接远多于普通路由器，所以扩大了 ephemeral 端口范围。
扩大后的范围覆盖了本固件的服务端口，因此显式保留 `2023,50080,50081,50530,50531`；
否则服务重启时可能出现端口已被临时连接占用而起不来。

> `nf-conntrack` 没有 AutoLoad，要等防火墙（START=19）装规则时才加载，而
> `/etc/init.d/sysctl` 在 START=11 就跑完并且用的是 `sysctl -e`（静默忽略不存在的键）。
> 所以 conntrack 那两项由 [`/etc/init.d/perf-tune`](files/etc/init.d/perf-tune)
> 在 START=99 重新应用一次，否则它们会毫无提示地不生效。

验证：

```sh
sysctl net.ipv4.tcp_congestion_control   # 应为 bbr
sysctl net.netfilter.nf_conntrack_max    # 应为 131072
logread | grep perf-tune
```

**AdGuardHome 工作目录**改到了 `/srv/adguardhome-{direct,proxy}`。原先在
`/var/lib/...`，而 OpenWrt 的 `/var` 是指向 tmpfs 的软链接——意味着每次重启两个实例的
过滤规则全部重新下载，这段时间内 DNS 拦截不生效。放在 `/srv` 既持久化，又不会被
`sysupgrade -c` 把查询日志卷进备份包。

### 需要你自行确认的一项

流量卸载能显著提升纯转发吞吐，但会让已建立的连接走内核快速路径、绕过常规 netfilter 处理，
这与透明代理存在张力。若遇到「个别连接莫名走直连」，这是首要嫌疑：

```sh
uci get firewall.@defaults[0].flow_offloading
```

## 配置保留与升级

### 结论

**用保留配置的方式升级，现有设置不会被清空。** 但 x86 combined 镜像的升级机制有一个前提
需要清楚：配置是靠 **sysupgrade 备份压缩包**存活的，不是靠 overlay 分区原地保留。

x86 的 `platform_do_upgrade` 在镜像分区表与当前磁盘不一致时，会 `dd` **整盘**覆盖——
包括 overlay 分区。分区表一致时才逐分区写入。本固件为 256 MiB 内核 + 2048 MiB 根分区；
如果当前运行的固件分区尺寸不同，升级会重建整个磁盘，届时**只有备份压缩包里的内容能活下来**。

所以下面的备份步骤不是可选项。

### 保留范围（已按各包实际定义核对）

固件用 `/lib/upgrade/keep.d/my-immortalwrt` 声明保留规则。该文件位于只读层，旧版本遗留的
overlay 文件不会遮蔽后续规则更新；`/etc/sysupgrade.conf` 留给你填设备专属路径。
列出目录时 `sysupgrade` 会递归收集其中的文件。

| 数据 | 实际路径 | 覆盖方式 |
| --- | --- | --- |
| dae 配置 | `/etc/config/dae`、`/etc/dae/`（含 `config.dae`、`subscriptions`） | keep.d + 包 conffiles |
| daed 数据库（节点/订阅/路由） | `/etc/config/daed`、`/etc/daed/`（含 `wing.db`） | keep.d + 包 conffiles |
| daede 管理界面 | `/etc/config/daede` | keep.d + 包 conffiles |
| Lucky | `/etc/config/lucky` + 数据目录 `/etc/config/lucky.daji/` | keep.d |
| Watchdog | `/etc/config/watchdog` | keep.d |
| 双 AdGuardHome 设置 | `/etc/AdGuardHome-direct.yaml`、`-proxy.yaml` | keep.d |
| 计划任务 | `/etc/crontabs/root` | keep.d |
| network / dhcp / firewall / SQM / UPnP / 密码 / SSH key / 证书 | `/etc/config/*` 等 | 标准 conffile 机制 |

### 明确**不会**保留的内容

- **已安装的软件包本身。** 保留配置不等于保留软件包。固件内置的包会随新固件一起回来；
  你自己 `apk add` 装的需要重新安装。备份工具用 `-k` 导出软件包清单供比对。
- **AdGuardHome 运行时数据**（`/var/lib/adguardhome-*`）。`/var` 指向 `/tmp`，
  查询日志、统计和已下载的过滤规则内容**每次重启都会丢**，不只是升级。
  真正的设置（上游、过滤器订阅地址、用户密码）在 YAML 里，会保留；重启后规则会重新下载。
- `/tmp`、`/var` 下的其它一切。
- 未列入 keep.d、conffiles，也未被 `-c` 捕获的路径。

### 升级前必做

> 备份清单由**当前正在运行的旧固件**生成。刚在仓库或新固件里加的规则，救不了尚未完成的这次升级。
> 若当前路由器还没有 `my-sysupgrade-backup`，直接用下面的兼容命令；`-c` 会额外保存 `/etc`
> 下所有变更过的文件，可弥补旧固件保留规则的不足。

```sh
# 1. 确认当前不是临时 RAM overlay；若命中 /tmp/root，先备份且不要重启
mount | grep -E ' /overlay |overlayfs:/tmp/root'

# 2. 生成包含 /etc 本地变更和软件包清单的备份
sysupgrade -c -k -b /tmp/backup-before-upgrade.tar.gz

# 3. 验证压缩包可读，并抽查关键配置
tar -tzf /tmp/backup-before-upgrade.tar.gz >/dev/null
tar -tzf /tmp/backup-before-upgrade.tar.gz | grep -E '(^|/)etc/(config/(network|dhcp|firewall|dae|daed|daede|lucky|lucky\.daji)|dae/|daed/|AdGuardHome-(direct|proxy)\.yaml|shadow|passwd)'
sha256sum /tmp/backup-before-upgrade.tar.gz
```

**立刻**通过 SCP / SFTP / LuCI 把备份下载到电脑或 NAS。`/tmp` 位于内存，重启或刷机后消失。

已在运行本项目固件时，用内置工具完成同样的事并自动核验关键路径（它直接读 keep.d，
不会和保留规则脱节）：

```sh
my-sysupgrade-backup
my-sysupgrade-backup /mnt/sda2/my-router-backup.tar.gz   # 直接写到持久磁盘
```

任何一个存在于磁盘、却没进入备份的项目路径都会让它以非零码退出。

### 升级步骤

1. 保持同一分支：`master → master` 或 `openwrt-25.12 → openwrt-25.12`。
   不要在一次保留配置升级中跨分支迁移。
2. EFI 用 `squashfs-combined-efi.img.gz`；Legacy BIOS 用 `squashfs-combined.img.gz`。
   **不要用 `rootfs.tar.gz` 做 sysupgrade。**
3. 先测试镜像再升级：

```sh
sysupgrade -T /tmp/immortalwrt-x86-64-generic-squashfs-combined-efi.img.gz
sysupgrade -c -k -v /tmp/immortalwrt-x86-64-generic-squashfs-combined-efi.img.gz
```

不要用 `-n`（不保留配置）或 `-F`（跳过兼容性检查）。LuCI 升级必须勾选「保留配置」；
对尚未包含本项目 `keep.d` 的旧固件，优先用上面的 CLI `-c -k` 流程。

### 升级后检查

```sh
mount | grep -E ' /overlay |overlayfs:/overlay on / '
sysupgrade -l | grep -E 'AdGuardHome-(direct|proxy)|etc/(dae|daed)|lucky\.daji'
uci show network >/dev/null && uci show dhcp >/dev/null
/etc/init.d/adh-direct status
/etc/init.d/adh-proxy status
```

`/overlay` 应挂载在持久存储上。若根 overlay 显示为 `overlayfs:/tmp/root`，说明配置正在写入
RAM——**先把配置备份到外部设备，再排查，期间不要重启**。

> 不要用 `dd`、PVE 重新导入整盘或写盘工具覆盖旧磁盘来做「保留配置升级」，这些方式会直接覆盖
> 原分区和 overlay。若必须重建虚拟磁盘，先导出备份，在新系统中上传后执行
> `sysupgrade -r /tmp/backup-before-upgrade.tar.gz`，检查无误再重启。

### 已知的取舍

固件更新**不会**刷新已有安装上的 `/etc/AdGuardHome-*.yaml` 默认模板——保留规则让用户的现有
配置胜出。想采用新版默认值时需要手动比对 `/rom/etc/AdGuardHome-direct.yaml`。

## 鸣谢

- [ImmortalWrt](https://github.com/immortalwrt/immortalwrt)
- [P3TERX/Actions-OpenWrt](https://github.com/P3TERX/Actions-OpenWrt)
- [kenzok8/openwrt-daede](https://github.com/kenzok8/openwrt-daede)
- [AdGuardHome](https://github.com/AdguardTeam/AdGuardHome)
- [OpenWrt packages](https://github.com/openwrt/packages)
- [gdy666/luci-app-lucky](https://github.com/gdy666/luci-app-lucky)
- [sirpdboy/luci-app-watchdog](https://github.com/sirpdboy/luci-app-watchdog)
- [hellomrli/my-openwrt-packages](https://github.com/hellomrli/my-openwrt-packages)（第三方包镜像）
