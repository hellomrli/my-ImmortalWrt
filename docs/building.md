# 构建固件并固定来源

[返回文档入口](index.md)

## 触发构建

在本仓库 Actions 的 OpenWrt Builder 中选择 branches=master、iptv 或 all。已配置 GitHub CLI 的维护者也可在本仓库执行：

```sh
gh workflow run openwrt-builder.yml --ref main -f sources=immortalwrt -f branches=master
```

构建会发布固件及来源附件，不会刷写路由器。具体目标、配置文件和脚本由 [targets.json](../.github/targets.json) 声明。

## 第三方来源

编译用到的第三方包不直接克隆上游，而是走个人镜像仓库
[`hellomrli/my-openwrt-packages`](https://github.com/hellomrli/my-openwrt-packages)，
上游删库、改名或转为私有时构建仍可继续。

| 包 | 镜像路径 | 上游 |
| --- | --- | --- |
| `honk` / `luci-app-honk` | `openwrt-honk` | `kenzok8/openwrt-honk`（按 release 同步，含资源） |
| `lucky` / `luci-app-lucky` | `luci-app-lucky` | `gdy666/luci-app-lucky`（LuCI 界面）+ [官方文件服务](https://release.66666.host/)（核心包） |
| `watchdog` / `luci-app-watchdog` | `luci-app-watchdog` | `sirpdboy/luci-app-watchdog` |

master 使用 [`.github/packages-honk.json`](../.github/packages-honk.json)，IPTV 使用
[`.github/packages-iptv.json`](../.github/packages-iptv.json)，由
[`.github/scripts/fetch-packages.py`](../.github/scripts/fetch-packages.py) 在构建时落地：

- 只抽取清单列出的子目录，不整仓克隆进 `package/`。镜像同时保存了本固件不编译的包
  （`golang`、`adguardhome-dual`、`openclash`、`passwall` 等），整仓引入会与
  `feeds/packages/lang/golang` 及本固件基于 overlay 的双 ADH 方案冲突。
- 镜像优先、按包兜底：非 mirror-only 包在镜像不可达或未收录时尝试上游并告警；
  Honk 不回退上游，普通包的上游也不可用时同样会构建失败。
- 落地后校验每个包的必需 `Makefile`，并把实际来源和 commit 写入 `package-provenance.txt`，
  随 Release 发布为 `*_packages.txt`。

`honk` / `luci-app-honk` 是只能从镜像获取的包：镜像按上游最新 release 同步 wrapper、
`generated-stage.mk`、`generated-doona-stage.mk` 与来源清单，并把 Honk core / Doona 归档
重新上传到镜像自己的 release，再把 stage 文件里的下载地址改写成镜像地址。固件构建由
[`.github/scripts/fetch-honk-source.py`](../.github/scripts/fetch-honk-source.py) 读取随包下发的
`honk-source.json`，核对 wrapper 的 `CORE_COMMIT`、release 来源、两个 stage 文件的 URL 与
每一项 SHA256，然后才把资源放进 `dl/`；不再解析也不访问 `kenzok8/openwrt-honk`，也不接受
`SKIP` 或可漂移的 staging 资源。清单里该项标记为 `mirror_only`：镜像不可用时构建直接失败，
不会回退去克隆一个缺少生成文件的空 wrapper。实际使用的资源与哈希记入
`package-provenance.txt`。

Lucky 的核心包从 3.x 起闭源，走的是另一条路：`gdy666/lucky` 的 GitHub release 停在
v2.27.2，新版本只在官方文件服务 [`release.66666.host`](https://release.66666.host/) 发布
（路径为 `v<版本>/<版本>_lucky/lucky_<版本>_Linux_<架构>.tar.gz`，同目录 `checksums.txt`
给出各架构 sha256）。镜像用
[`overrides/luci-app-lucky/lucky`](https://github.com/hellomrli/my-openwrt-packages/tree/main/overrides/luci-app-lucky/lucky)
固定核心包 Makefile——否则每 6 小时的同步会把它退回 2.27.2。构建前由
[`.github/scripts/pin-lucky-source.py`](../.github/scripts/pin-lucky-source.py) 取官方最新发布，
回写 `PKG_VERSION` / `PKG_SOURCE_URL` 和逐架构哈希表。两个固件目标都要求 x86_64 的 SHA256；
官方清单缺少该摘要即停止，不会降级为 `skip`。服务不可达时只允许沿用带有 x86_64 摘要且符合
`LUCKY_VERSION`（如有指定）的镜像 pin。发布来源清单记录实际使用的版本和 x86_64 摘要。
LuCI 界面和 Lucky 核心使用独立版本号，不要求两者一致；具体版本、来源和哈希以每次
Release 的包清单与 `*_packages.txt` 为准。
需要钉住某个版本时设置 `LUCKY_VERSION=3.1.4`。同一数字版本优先正式版；若只有 beta/rc
仍可选择，更高数字版本的预发布也不会被自动排除，不等于“仅使用稳定版”。

上游改动打断构建时，在对应目标的包清单中把 `mirror.ref` 固定到已知可用的 commit SHA，
并设置 `PKG_SOURCE=mirror`，避免镜像失败时回退到未固定的上游。这会固定包定义及 Honk 的
配套资源清单；Lucky 核心仍会独立解析官方发布，需另设 `LUCKY_VERSION`。
也可在构建工作流的 `env` 或本地执行 DIY 脚本的环境中设置以下变量（不是 Run workflow 输入）：

```sh
PKG_MIRROR_REF=<commit>  # 覆盖所选清单的 mirror.ref
PKG_SOURCE=mirror       # 强制只用镜像，缺包即失败
LUCKY_VERSION=3.1.4     # 独立固定 Lucky 核心数字版本
```

`PKG_SOURCE=upstream` 仅适用于允许上游兜底的包清单（如 IPTV）；master 含 mirror-only 的
Honk，使用该模式会拒绝构建。

## 构建流水线

[`configs/honk.config`](../configs/honk.config) 保存 master 的精简构建选项，由上游
`scripts/diffconfig.sh` 提取，并补齐需要显式保留的设置。master 在
`make defconfig` 后校验恢复模式 IP、BTF、`kmod-sched` 和 QEMU Guest Agent；IPTV 使用
独立的 `configs/iptv.config` 和校验脚本，恢复地址为 `.250`，不要求透明代理的 BPF 组件。最终完整
`.config` 随 Release 发布。Ruby 及其标准库不再预装，`qemu-ga` 所需的 GLib 依赖保留。

内核配置附件只从 `build_dir/target-*/linux-x86_64/linux-*/.config` 导出。两个目标均校验
x86_64、FQ 和 BBR；master 额外校验 BPF/BTF、NETKIT、XDP 和 NFQUEUE，IPTV 不要求这些
透明代理组件。不会误发布 BPF headers 辅助构建的 MIPS 配置。

GitHub 托管 runner 有几条硬性限制，流水线是围绕它们设计的：

| 限制 | 应对 |
| --- | --- |
| 单 job 6 小时上限 | job 限时 350 分钟；编译前扣除前置步骤的实际耗时，动态设置步骤超时（最多 320 分钟），预留 30 分钟给诊断和收尾；前置步骤也分别限时 |
| 仓库 Actions 缓存共 10 GB | 只缓存 ccache（上限 2 GB、开压缩），不缓存 `dl/`；重新下载只花几分钟，冷 ccache 要花几小时 |
| `actions/cache` 命中主 key 就跳过保存 | ccache 用 run 唯一 key + 前缀恢复，并改用显式 `restore` / `save`，失败的构建也能留下部分预热缓存 |
| 磁盘容易 ENOSPC | 清理 dotnet / android / ghc / CodeQL / boost 等预装目录，编译前后都输出 `df` |
| 网络抖动 | `apt-get`、`make download`、`git push` 均带重试；下载后删除截断文件并重新下载 |

其它行为：

- 配置、下载或编译阶段失败时上传 `openwrt/logs`（已启用 `CONFIG_BUILD_LOG`）、`.config`、
  内核配置、feed 配置和包来源清单，保留 14 天；显式包含隐藏的 `.config` 文件。
  诊断报告记录构建配置 commit、上游及各 feed 的实际 commit 和已跟踪文件改动，不导出 Git 凭据。
  失败日志优先于缓存统计和保存上传；日志与缓存步骤各自限时，避免缓存耗尽诊断时间。
  不再靠整轮 `make -j1 V=s` 重跑来取日志。
- 重试阶梯全部增量执行：并行 → 并行重试 → 单线程 `V=s`。不再有 `make clean` 后的全量重建
  （那在 6 小时内不可能完成）。
- Update Checker 每 6 小时比对上游 commit；Honk 目标还比对镜像 `honk-source.json` 的 SHA256，
  单独更新 Honk 发布也会重建 master，不会因镜像内无关包变更重编 IPTV。「已构建」标记由实际构建输入计算，在发布成功后才写入，
  因此构建失败会在下次检查时重试，而不是等上游再次提交。
- 每个固件目标保留最近 5 个 Release；`OpenWrt Builder` 工作流共保留最近 20 条运行记录，
  不是每个目标各 20 条。

手动触发：Actions → `OpenWrt Builder` → Run workflow，`branches` 填 `master`、`iptv` 或 `all`。
两者的缓存、更新检查和 Release 标签独立；IPTV 从 `profiles/iptv/files` 加载自己的预置文件，
包含 Lucky、`luci-app-gxmobile`、BBR/fq 和扫描数据保留规则，不混入 master 的代理/DNS 服务。
构建表仅显示已经发布的固件，不代表当前任务状态；实时进度请查看
[Actions](https://github.com/hellomrli/my-ImmortalWrt/actions/workflows/openwrt-builder.yml)。

## 核对结果

以 Release 中最终 config、kernel config、manifest 和 packages.txt 为准。测试或编译失败先查看诊断 artifact；成功构建不能证明真实节点、运营商线路或硬件配置已通过测试。
