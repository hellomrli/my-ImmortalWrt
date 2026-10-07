# IPTV 专用固件与 LuCI 扫描组件

`iptv` 是本仓库的固件构建目标，源码分支为 ImmortalWrt 上游最新 `master`。
仓库代码仍统一维护在 `main`，无需在上游寻找名为 `iptv` 的分支。
原 `master` 固件的配置、DIY 脚本、代理/DNS 预置文件保持不变，`25.12` 不再进入构建或更新检查。

| 项目 | IPTV 配置 |
| --- | --- |
| 架构 | x86_64，QEMU / PVE |
| 管理及恢复地址 | `192.168.50.250/24` |
| 主机名 | `ImmortalWrt-IPTV` |
| LAN / IPTV 上联 | `br-lan`（eth0）/ eth1 PPPoE |
| 转发 | Lucky，沿用现有规则 |
| 扫描 | `gxmobile-scan` + `luci-app-gxmobile` |
| 默认计划 | 每周一 04:20，全量扫描，Asia/Shanghai |
| 并发 | 4 个 CID 探测，2 个视频片段读取 |
| LAN 服务 | DHCP、DHCPv6、RA 关闭，不劫持 DNS |
| 网络优化 | BBR + fq、按需 TCP 缓冲、64K conntrack |
| 运维 | QEMU Guest Agent、SFTP、磁盘管理、tcpdump、iperf3 |

固件不内置拨号密码、root 密码或 Lucky 私有配置。保留配置升级会恢复原设备的设置；
全新安装需设置管理密码、填写 IPTV 拨号账号，勾选 WAN 的“开机自动运行”，并配置或恢复 Lucky 规则。
新装 WAN 默认不自动拨空账号，管理口仍可通过 LAN 访问。

## Web 操作

登录 `http://192.168.50.250/cgi-bin/luci/admin/services/gxmobile`，或进入 **服务 → IPTV 扫描**。

- **快速扫描**：探测设置范围内的 CID，对比新增、消失和恢复的信号源；只读取新增源的视频片段。
- **全量扫描**：同时重测所有在线源的码率，可能占用较多上联带宽，适合凌晨执行。
- **定时扫描与扫描设置**：每天或每周、星期、小时、分钟、模式、网关、CID 范围和并发数。
- **频道列表**：搜索、分组筛选、编辑名称/分组、删除频道、查看主信号及在线/失效源数。
- **下载 M3U / 最近扫描报告**：取得去重列表并检查本次变化。删除后再次探测到同一 CID，会以待命名的新频道加入。

订阅地址继续兼容原路径：

```text
http://192.168.50.250/gxmobile/广西移动IPTV_去重版.m3u
```

扫描管理通过 LuCI 登录会话和 rpcd ACL 授权。后台只监听 `127.0.0.1:8081`，
原来的 `http://192.168.50.250:8081` 独立页面不再使用。
播放列表仍可供内网播放器直接订阅，不要求播放器携带 LuCI 会话。

所有手动和定时扫描都提交给同一个后台。旧的 `/usr/bin/gxmobile-scan` cron 命令会迁移为
`/usr/libexec/gxmobile-schedule run`，不再出现 Web 内存基线与独立 CLI 扫描互相覆盖的问题。
迁移只处理扫描程序自己的任务，保留其它 cron 条目；保存设置可重复执行而不生成重复任务。

## 数据保护与边界

- 持久化数据位于 `/etc/gxmobile`，包括频道命名、信号源、M3U 和报告；UCI 设置位于 `/etc/config/gxmobile`。
- `/www/gxmobile` 是发布副本，后台启动时从持久化文件恢复，不依赖备份这个目录。
- 探测异常、全部失败，或范围内超过一半已有在线源失联时，中止更新并保留原列表。
- 只把明确的 HTTP 404/410 当成不存在；200 响应必须是 M3U 内容，登录页或错误页不会当成频道。
- 每个输出文件通过同目录临时文件写完后原子替换；写入错误会报告失败。这不是多个文件之间的数据库事务。
- 扫描使用内核文件锁，进程异常退出后自动释放，不会被残留的 `.scan.lock` 文件永久阻塞。
- 扫描期间不能改名/删除或更改配置；状态查询使用独立快照，不阻塞扫描。
- 码率根据实际 `EXTINF` 时长计算。已有分辨率来自基线，新源不进行解码识别，需自行命名；不保证持续可播放或画面内容正确。
- 每次范围最多 5000 个 CID。并发限制控制同时探测/读取的数量，不是精确的带宽限速。

## 网络优化依据

2026-10-07 实机检查：8 vCPU、约 4 GiB RAM，当前内核 `6.12.50`；
eth0 为 LAN，eth1 为 r8125 网卡，PPPoE 取得 IPTV 专网地址。
实际路径是 **客户端 → Lucky HTTP/HLS 反向代理 → IPTV 服务**，不是 udpxy/IGMP 组播转发。

因此优化重点是本机 TCP 连接、播放与扫描的资源竞争，以及配置持久化：

| 调整 | 依据 |
| --- | --- |
| BBR + fq | Lucky 在本机终结 TCP；本机发送端可以使用 BBR 和 pacing。不能改变上游服务器的拥塞控制，也不会加速纯 UDP 转发。 |
| 接收 16 MiB / 发送 8 MiB 上限 | 放宽自动调优上限，保持每条连接初始缓冲大小，避免一开连接就大块占内存。 |
| backlog 8192、连接队列 4096 | 提供适量突发余量，避免照抄透明代理的更大队列。 |
| conntrack 65536 / buckets 16384 | 实测仅数十条连接，无需透明代理 profile 的 262144 条上限。 |
| TCP MTU probing | 辅助处理 PPPoE 路径中 ICMP 丢失导致的 MTU 黑洞；保留防火墙 MSS 修正。 |
| 不设置过激 TCP 超时 / UDP 缓冲 | 实测 UDP 接收错误与 softnet 丢包为 0，无证据支持继续放大。 |
| 停止匿名磁盘自动挂载 | 旧设备 `/dev/vda1` 在 `/boot` 挂载了两次；使用平台启动挂载，避免硬编码 `/dev/sda1`。 |
| 专用服务选择 | 不编译 dae、daed、AdGuardHome、Samba、Avahi；保留 Lucky 和运维组件。 |

旧内核仅提供 reno/cubic，不能把新 master 编译的 BBR 模块装进旧内核；BBR 会随新固件一起生效。
`iptv-perf` 在防火墙加载后重新应用参数，避免开机早期 conntrack 键尚不存在而被静默跳过。
`default_qdisc=fq` 不会强制替换已经显式设置的队列，启动后应核对实际接口：

```sh
sysctl net.ipv4.tcp_congestion_control net.core.default_qdisc
sysctl net.netfilter.nf_conntrack_max net.netfilter.nf_conntrack_buckets
tc qdisc show
logread | grep iptv-perf
```

实机 eth1 的接口累计 dropped 计数非零，但驱动大多数错误计数和 softnet 丢包为 0；
这是累计指标，不能直接归因于缓冲不足，需播放时观察增量后再决定是否调整网卡队列。

### 还应检查的现有规则

旧防火墙有宽泛的 `wan → lan` forwarding；Lucky 的动态链还在 WAN 区域判断之前放行了
8080 和管理端口 18811。对于仅供内网访问的 HLS 代理，应删除不需要的 WAN→LAN 转发，
并在 Lucky 内限制管理/播放监听或来源，而不是只修改 fw4 的 WAN input 策略。
如果有远程观看需求，按实际来源地址单独放行。

新装 IPTV 模板不含 WAN→LAN 放行，关闭 Fullcone 和硬件 flow offload；保留软件 flow offload
用于可能的 LAN→WAN 普通转发，它对 Lucky 本机代理连接没有加速作用。
**保留配置升级会沿用旧 firewall / Lucky 设置**，不会自动替你删除已有业务规则。
当前设备的 WAN、PPPoE、Lucky 规则没有在组件安装过程中更改。

## 构建与独立安装

Actions → OpenWrt Builder → Run workflow，`branches` 填 `iptv`（只编译 IPTV）或 `all`。
Release 标签为 `immortalwrt-iptv-*`，同时附带两个可独立安装的 APK。
更新检查使用上游 `master` commit，但与原 master 固件分别记录发布成功标记。

源码目录：`packages/gxmobile-scan` 和 `packages/luci-app-gxmobile`。
把两个目录复制到 OpenWrt 源码树的 `package/` 下，安装 packages/luci feeds 后选择组件：

```sh
make menuconfig
make package/gxmobile-scan/compile V=s
make package/luci-app-gxmobile/compile V=s
```

针对这台现有 APK 固件，也可只安装本次生成的组件，不升级内核：

```sh
apk add --no-network --allow-untrusted /tmp/gxmobile-scan-1.2.0-r2.apk /tmp/luci-app-gxmobile-1.2.0-r2.apk
```

本地包未签名；只对自行构建/核对过的这两个文件使用 `--allow-untrusted`。
旧路由器已具备 curl、BusyBox flock、rpcd/ucode 依赖；新固件会一并编译相应工具。

## 首次升级前备份

扫描程序原始二进制、原有配置和原始源码已保存在本机私有目录
`/home/lain/codex/iptv-router-backup-20261007`。此目录包含设备私有数据，不进入 Git 仓库。
原始源码来自 `/home/lain/codex/gxmobile-scan`；其中预编译二进制与路由器上的程序 SHA256 相同。

组件安装后另已生成并下载完整备份：
`/home/lain/codex/iptv-router-backup-20261007/sysupgrade-after-plugin-20261007.tar.gz`，
已核验拨号配置、Lucky 规则、频道基线、扫描计划、账户文件和软件包清单均在归档中。
此后若修改配置，刷机前仍需重新备份。

**第一次升级前，必须用旧系统自己的工具生成可恢复的完整 sysupgrade 备份。**
新的 keep.d 规则不能追溯保护已经开始的升级：

```sh
sysupgrade -c -k -b /tmp/iptv-before-upgrade.tar.gz
tar -tzf /tmp/iptv-before-upgrade.tar.gz | grep -E 'etc/(config/(network|lucky|gxmobile)|gxmobile|crontabs)'
```

确认里面包含 `etc/config/network`、`etc/config/lucky.daji/`、`etc/gxmobile/iptv_baseline.json`、
`etc/config/gxmobile`、`etc/crontabs/root`，并把压缩包复制到电脑或 NAS。
本次本地“原始配置归档”方便审计和回滚组件，不代替包含账户/密钥等全部内容的 sysupgrade 备份。

新固件继续使用 256 MiB 内核分区、2048 MiB 根分区和 squashfs/F2FS overlay。
刷写前先 `sysupgrade -T` 检查镜像，升级使用保留配置模式，不能把 rootfs.tar.gz 当作升级镜像。
本次工作没有执行刷机或重启路由器。
