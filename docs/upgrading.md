# 备份、升级和恢复配置

[返回文档入口](index.md)

## 理解备份范围

保留配置升级只恢复进入 sysupgrade 备份压缩包的内容，不等于保留整个 overlay。
以下保留清单与 ADH 检查以 master 为例；IPTV 请同时阅读 [IPTV 备份说明](iptv.md)。

当前 x86 的 `legacy-sdcard` 升级逻辑在镜像分区布局变化时可能整盘写入；若检测到额外分区且布局冲突，
默认拒绝写入，而不是擦掉额外分区。如果镜像分区匹配则可以逐分区写入。实际行为取决于执行升级的旧固件。
本固件为 256 MiB 内核 + 2048 MiB 根分区；不要绕过额外分区保护，升级前仍须备份到别的设备。

所以下面的备份步骤不是可选项。

## 保留范围（已按各包实际定义核对）

固件用 `/lib/upgrade/keep.d/my-immortalwrt` 声明保留规则。该文件位于只读层，旧版本遗留的
overlay 文件不会遮蔽后续规则更新；`/etc/sysupgrade.conf` 留给你填设备专属路径。
列出目录时 `sysupgrade` 会递归收集其中的文件。

| 数据 | 实际路径 | 覆盖方式 |
| --- | --- | --- |
| Honk 配置/状态 | `/etc/config/honk`、`/etc/honk/` | keep.d |
| 旧 dae 配置（回滚用） | `/etc/config/dae`、`/etc/dae/`（含 `config.dae`、`subscriptions`） | keep.d（旧数据存在时） |
| 旧 daed 数据库（回滚用） | `/etc/config/daed`、`/etc/daed/`（含 `wing.db`） | keep.d（旧数据存在时） |
| 旧 daede 管理界面（回滚用） | `/etc/config/daede` | keep.d（旧数据存在时） |
| Lucky | `/etc/config/lucky` + 数据目录 `/etc/config/lucky.daji/` | keep.d |
| Watchdog | `/etc/config/watchdog` | keep.d |
| 双 AdGuardHome 设置 | `/etc/adguardhome-direct/`、`/etc/adguardhome-proxy/`，以及 `/etc/AdGuardHome-*.yaml` 旧路径 | keep.d |
| 计划任务 | `/etc/crontabs/root` | keep.d |
| network / dhcp / firewall / SQM / UPnP / 密码 / SSH key / 证书 | `/etc/config/*` 等 | 标准 conffile 机制 |

## 明确不会保留的内容

- 已安装的软件包本身。 保留配置不等于保留软件包。固件内置的包会随新固件一起回来；
  你自己 `apk add` 装的需要重新安装。备份工具用 `-k` 导出软件包清单供比对。
- AdGuardHome 运行时数据（`/srv/adguardhome-*`）。它不在 keep.d 中：普通重启会保留，
  但 sysupgrade 重建磁盘时会随 overlay 一起丢失，必要时需自行纳入备份。
  真正的设置（上游、过滤器订阅地址、用户密码）在 YAML 里，会保留；规则可在启动后重新下载。
- `/tmp`、`/var` 下的其它一切。
- 手动或通过 LuCI 更新的 `/usr/share/v2ray/geoip.dat`、`/usr/share/v2ray/geosite.dat`。`-c` 不包含 `/usr/share`；若需保留自定义分流数据，升级前单独复制这两个文件到电脑，或确认原下载源仍可用。
- 未列入 keep.d、conffiles，也未被 `-c` 捕获的路径。

## 升级前必做

> 备份清单由当前正在运行的旧固件生成。刚在仓库或新固件里加的规则，救不了尚未完成的这次升级。
> 若当前路由器还没有 `my-sysupgrade-backup`，直接用下面的兼容命令；`-c` 会额外保存 `/etc`
> 下所有变更过的文件，可弥补旧固件保留规则的不足。

```sh
# 1. 确认当前不是临时 RAM overlay；若命中 /tmp/root，先备份且不要重启
mount | grep -E ' /overlay |overlayfs:/tmp/root'

# 2. 生成包含 /etc 本地变更和软件包清单的备份
sysupgrade -c -k -b /tmp/backup-before-upgrade.tar.gz

# 3. 验证压缩包可读，并抽查关键配置
tar -tzf /tmp/backup-before-upgrade.tar.gz >/dev/null
tar -tzf /tmp/backup-before-upgrade.tar.gz | grep -E '(^|/)etc/(config/(network|dhcp|firewall|honk|dae|daed|daede|lucky|lucky\.daji)|honk/|dae/|daed/|adguardhome-(direct|proxy)/|AdGuardHome-(direct|proxy)\.yaml|shadow|passwd)'
sha256sum /tmp/backup-before-upgrade.tar.gz
```

立刻通过 SCP / SFTP / LuCI 把备份下载到电脑或 NAS。`/tmp` 位于内存，重启或刷机后消失。

已在运行本项目固件时，用内置工具完成同样的事并自动核验关键路径（它直接读 keep.d，
不会和保留规则脱节）：

```sh
my-sysupgrade-backup
my-sysupgrade-backup /mnt/sda2/my-router-backup.tar.gz   # 直接写到持久磁盘
```

任何一个存在于磁盘、却没进入备份的项目路径都会让它以非零码退出。

## 升级步骤

1. 保持相同固件用途：`master → master` 或 `iptv → iptv`。旧 IPTV 设备首次迁移见 [IPTV 备份说明](iptv.md)。
   不要在一次保留配置升级中跨分支迁移。
2. EFI 用 `squashfs-combined-efi.img.gz`；Legacy BIOS 用 `squashfs-combined.img.gz`。
   不要用 `rootfs.tar.gz` 做 sysupgrade。
3. 先测试镜像再升级：

```sh
sysupgrade -T /tmp/immortalwrt-x86-64-generic-squashfs-combined-efi.img.gz
sysupgrade -c -k -v /tmp/immortalwrt-x86-64-generic-squashfs-combined-efi.img.gz
```

不要用 `-n`（不保留配置）或 `-F`（跳过兼容性检查）。LuCI 升级必须勾选「保留配置」；
对尚未包含本项目 `keep.d` 的旧固件，优先用上面的 CLI `-c -k` 流程。

## 升级后检查

```sh
mount | grep -E ' /overlay |overlayfs:/overlay on / '
sysupgrade -l | grep -E '(AdGuardHome|adguardhome)-(direct|proxy)|etc/(honk|dae|daed)|lucky\.daji'
uci show network >/dev/null && uci show dhcp >/dev/null
/etc/init.d/adh-direct status
/etc/init.d/adh-proxy status
```

`/overlay` 应挂载在持久存储上。若根 overlay 显示为 `overlayfs:/tmp/root`，说明配置正在写入
RAM——先把配置备份到外部设备，再排查，期间不要重启。

> 不要用 `dd`、PVE 重新导入整盘或写盘工具覆盖旧磁盘来做「保留配置升级」，这些方式会直接覆盖
> 原分区和 overlay。若必须重建虚拟磁盘，先导出备份，在新系统中上传后执行
> `sysupgrade -r /tmp/backup-before-upgrade.tar.gz`，检查无误再重启。

## 已知的取舍

固件更新不会刷新已有安装上的 `/etc/AdGuardHome-*.yaml` 默认模板——保留规则让用户的现有
配置胜出。想采用新版默认值时需要手动比对 `/rom/etc/AdGuardHome-direct.yaml`。
