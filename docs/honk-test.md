# Honk 固件

`master` 固件使用 ImmortalWrt **上游 master** 源码，并用 Honk + Doona 替代
dae / daed / luci-app-daede，同时编入 NFQUEUE 内核模块。网络基线、双 AdGuardHome、
dnsmasq DHCP、Lucky、Watchdog 和 F2FS 恢复支持保持不变。

仓库的 `test` Git 分支保留为 Honk 预发布通道：同样基于上游 master，仅手动构建、
单独预发布，不替换正式 master 固件。

## 与旧 daed 固件的区别

| 项目 | 旧 master 固件 | 当前 master / test 固件 |
| --- | --- | --- |
| 代理 | dae / daed + luci-app-daede | Honk + luci-app-honk / Doona |
| NFQUEUE | 未显式要求 | kmod-nft-queue + kmod-nfnetlink-queue |
| DNS 后端 | 双 AdGuardHome | 保留同一双 AdGuardHome 模板与服务 |
| DHCP / 本地域名 | dnsmasq | 保留 dnsmasq，不删除 DHCP 服务 |
| LAN / 恢复地址 | 192.168.50.1 | 不变 |
| PVE、网卡、F2FS、SFTP、Lucky、Watchdog | 原有配置 | 保留 |
| 发布 | 正式 master 标签 | master 为正式标签；test 为独立 immortalwrt-test-* 预发布，不替换 Latest |

去掉 dae/daed 软件包不等于转换它们的用户配置。固件仓库不包含真实节点、订阅、面板密码
或从设备复制的数据库。之前在设备上准备的 Honk 配置属于设备上的用户数据，升级前必须备份。

## DNS 路径

已迁移配置的目标结构是：

```text
LAN 普通 DNS -> Honk 透明接管 / DNS routing
                   |-> ADH-direct :50530 -> 直连 DNS
                   `-> ADH-proxy  :50531 -> 代理 DoH

.lan / 本地反查 -> dnsmasq
DHCP           -> dnsmasq（不变）
```

dnsmasq 仍可监听 53 端口，但透明接管会发生在普通 DNS 交给它处理之前；仅看到监听端口，
不能推断所有 DNS 都经过 dnsmasq。原 daed 实机配置也使用透明 DNS 接管，普通查询并不需要
先经过 dnsmasq。本固件保留双 ADH 的服务、端口和配置，不为 Honk 重写 DHCP、防火墙或网络接口。
最终流量路径仍取决于设备上启用的 Honk DNS/routing 配置，不能把全新安装的空配置当成已迁移配置。

## NFQUEUE 与启动

NFQUEUE 让 nftables 把指定数据包交给用户态程序检查，再由程序决定放行、丢弃或其他处理。
这是内核到用户态的队列接口，不是 DNS 服务器，也不表示全部流量都要走这个队列。

本固件同时编入 `kmod-nft-queue` 和 `kmod-nfnetlink-queue`，并在最终内核配置中检查
`CONFIG_NFT_QUEUE`、`CONFIG_NETFILTER_NETLINK_QUEUE`。模块与本固件内核一起生成，
不能把这些 APK 强装到旧内核固件上。

之前为兼容旧固件准备的 Honk 配置关闭了 NFQUEUE。**保留配置升级不会自动把它打开**，
也不会自动启用或重启 Honk；需要测试时再通过 Honk 管理界面检查相关配置。
Honk 的 `/etc/honk/system.dae` 包含 `nfqueue_enable`，相关 UCI 设置与实际生成的配置应保持一致。
缺少 NFQUEUE 时，关闭对应功能的 Honk 仍可运行；启用时则需要本固件补充的内核支持。

全新安装保持 Honk 上游默认 `enabled=0`、`boot_enabled=0`。保留配置设备的开机状态由
已有 `boot_enabled` 决定，不强制改成开启或关闭。不要同时运行 daed 和 Honk，二者会争用
透明代理的接口/网络命名空间。旧 dae/daed 配置保留用于回滚，但当前固件不再携带其程序。

## 版本与构建检查

- Honk wrapper 固定为 `kenzok8/openwrt-honk@4625dc057dbb9f668b21d37a64d5ae2bea0a4081`。
- Honk core 固定为已测试的 `995a80cd87e780a2a4d63b75008dca70876857b4`，含 `ebpf,rprx,native-api`。
- 核心和 Doona 使用 `v2026.10.16-r38852588947` 对应的 `source-38852588947` 资源，全部校验固定 SHA256，
  不使用可漂移的 staging 资源或 `SKIP` 校验。
- 上游 wrapper 使用预编译的静态 Honk 核心，不是在本工作流里重新编译 Rust；OpenWrt 包装、依赖、
  LuCI 翻译和 NFQUEUE 内核模块由本次固件构建系统生成，不复用其他 SDK 的 APK。
- `make defconfig` 后检查 Honk、NFQUEUE、双 ADH、eBPF、恢复网络；发布前再检查 manifest 与真实 kernel `.config`。
- Release 附带构建配置、内核配置、来源哈希清单及 Honk/LuCI/两个 NFQUEUE 模块的 APK。

Honk 固件兼容处理：移除未选用且存在 Kconfig 循环依赖的 video、freeradius3、squeezelite-custom；
miniupnpd 2.3.11 已包含旧 020/030 补丁的修复，只移除哈希已知的重复补丁；
保留上游已重新适配的 040 日志补丁及 IGD/XML 兼容补丁。不降级 miniupnpd、不移除其上游安全修复；
未知版本或待移除补丁的改动不会被盲目套用。

## 构建

正式 master 固件：

```sh
gh workflow run openwrt-builder.yml --ref main -f sources=immortalwrt -f branches=master
```

`test` 分支的预发布固件：

```sh
gh workflow run openwrt-builder.yml --ref test -f sources=immortalwrt -f branches=test
```

`test` 目标不参加定时上游更新检查。产物标签为 `immortalwrt-test-日期-时间`，只标为预发布；
test 构建不触发写入 main 的 README 更新，也不清理其他分支的构建记录。

刷机前运行 `my-sysupgrade-backup`，将备份下载到其他设备，并额外保存 PVE 虚拟机磁盘快照。
保留列表新增 `/etc/config/honk` 与整个 `/etc/honk`（包含配置、状态数据库），同时保留双 ADH 与旧代理数据。
**从旧固件首次升级到 Honk 固件时，应先确认旧固件的备份也包含这两个 Honk 路径**，新固件的 keep.d 无法反过来
补救旧固件生成的缺项备份。构建工作流只构建固件，不执行刷机。
