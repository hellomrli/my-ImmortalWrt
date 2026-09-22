# 更新日志

所有重要的项目变更都会记录在此文件中。

## [Unreleased]

### 性能
- 🚀 预置 `/etc/sysctl.d/99-performance.conf`：启用 BBR + fq。`kmod-tcp-bbr` 此前已编入固件却从未激活（仓库里没有任何 sysctl 配置），系统一直在用 cubic。这一项对本固件特别相关——dae 在本机终结客户端 TCP 后会自行向代理服务器建立连接，这些出站连接使用路由器自身的拥塞控制，在有损长 RTT 的国际链路上 BBR 优势明显。
- 🚀 抬高套接字缓冲区上限（16 MiB）、`netdev_max_backlog` 与 `somaxconn`；只改上限、保留接近原厂的默认值，让 Linux 自动调节，避免单连接内存膨胀。
- 🚀 关闭 `tcp_slow_start_after_idle`、开启 `tcp_mtu_probing`：代理连接空闲后突发时不再每次重新慢启动；隧道/代理路径常见的 ICMP 黑洞导致的 PMTU 失败也能规避。
- 🚀 conntrack 上限提到 262144 并同步抬高哈希桶（约 max/4）——代理场景下每条客户端连接消耗两个条目。只提上限不提桶会拖慢每次查表。
- 🚀 扩大临时端口范围，并显式保留 `2023,12345,50080,50081,50530,50531`——扩大后的范围覆盖了本固件的服务端口，不保留的话服务重启时可能因端口被临时连接占用而启动失败。
- 🩹 新增 `/etc/init.d/perf-tune`（START=99）重新应用一次 sysctl 配置：`kmod-nf-conntrack` 没有 AutoLoad，要到防火墙 START=19 才加载，而 `/etc/init.d/sysctl` 在 START=11 用 `sysctl -e` 静默跳过不存在的键——否则 conntrack 两项会毫无提示地不生效。
- 🚀 AdGuardHome 工作目录从 `/var/lib/adguardhome-*` 移到 `/srv/adguardhome-*`。`/var` 是指向 tmpfs 的软链接，原先每次重启都要重新下载全部过滤规则，期间 DNS 拦截不生效。放 `/srv` 同时避免查询日志被 `sysupgrade -c` 卷进备份包。
- 设置 `net.ipv4.tcp_fin_timeout=30`，限制孤立连接的 FIN_WAIT_2 等待时间；`net.ipv4.tcp_notsent_lowat=16384` 对应用未发送数据施加写入背压。它们不缩短 TIME_WAIT，也不绕过 TCP 拥塞窗口。
- 🚀 新增 `vm.swappiness=10`：dae 与双 AdGuardHome 都是内存型服务，默认 60 会让匿名页过早换出，增加 DNS 查询和代理连接延迟；无 swap 分区时该项无副作用。
- 🚀 新增 `97-dnsmasq-cache`：dnsmasq 缓存从编译内建默认（1000 条）提到 10000，热门域名直接命中 `:53`，不再每次走 dnsmasq → dae → 双 ADH 整条链。仅在用户未显式设置 `cachesize` 时写入，升级不覆盖已有配置。
- 🚀 `AdGuardHome-direct` 缓存从 4 MiB 提到 64 MiB。它是处理国内流量（绝大多数查询）的主后端，小缓存频繁逐出；`cache_optimistic` 已开启，加大缓存减少上游查询次数。

### 构建产物
- 📦 去除重复的 rootfs 压缩包：`CONFIG_TARGET_ROOTFS_TARGZ` 会用两个名字产出同一份归档（上次发布的两份 sha256 完全相同），每次构建白传约 81 MiB。删除前用 `cmp` 验证内容确实相同，并同步剔除 `sha256sums` 中的对应行。
- 📦 关闭无消费者的 DRM/fb/backlight 共 15 个 kmod：`kmod-drm-i915` 早已关闭且未选任何其它 GPU 驱动。本地控制台不受影响——x86 内核内建 `CONFIG_VGA_CONSOLE=y`，而 `FB_EFI` / `SYSFB_SIMPLEFB` / `DRM_SIMPLEDRM` 均未内建，控制台从未依赖这些模块。
- ⚠️ `CONFIG_KERNEL_DEBUG_INFO` 刻意保留：它看似是配置里最昂贵的一项，但 `DEBUG_INFO_BTF` 依赖它，而 dae/daed 需要内核 BTF；且 BTF 与 `DEBUG_INFO_REDUCED` 互斥，没有折中方案。
- 📦 fstab 与 apk repositories 从 `diy-part2-daed.sh` 的构建期 heredoc 改为仓库 `files/` 内提交的静态文件（`files/etc/config/fstab`、`files/etc/apk/repositories`），可 diff、可审查，与其余 overlay 覆盖一致；CI 断言同步指向新路径。

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
- 🧱 构建目标收敛为单一事实源 `.github/targets.json`：builder 矩阵、update-checker 矩阵、README 构建表脚本三处统一读取，加/删分支只需改一个文件。
- 🔐 修复「已构建」标记在 release 上传失败时仍被写入的问题：`Upload to release` 现在有 `id`，标记、README 刷新、旧 release 清理三个步骤都要求 release 上传成功才执行——上传失败会保持「未构建」状态，下次更新检查会重试而不是被标记污染。
- ⚡ `make download` 的截断文件清理并入重试循环（失败重试 + 截断重取，最多 4 趟），省掉原先成功后再跑一轮全量下载扫描的浪费。
- 🤖 新增 dependabot：GitHub Actions 每周自动检查更新，统一分组 PR，`ci` 前缀提交信息。
- 🧱 `dae` / `daed` 源码 pin 改为自适应上游滚动 release：上游把组装好的源码树发在 `dae-src` / `daed-src` 上且只保留最新 3 个 tar 包，镜像里固定的 `PKG_SOURCE` 因此会在上游每次重组源码后被轮换删除——2026-09-17 起连续三天的失败全部是这一个原因（pin 指向已被删除的 `dae-src-2026.09.12-187058462a1f.tar.gz`）。构建前由 `.github/scripts/pin-daede-source.py` 沿用仍存在的 pin、pin 消失时改用最新资产并回写 `PKG_VERSION` / `PKG_RELEASE` / `PKG_SOURCE` / `PKG_HASH`，再取回 `dl/` 校验 sha256、文件名内嵌内容 id 与目录结构，实际 tar 包记入 provenance。
- ⏱️ 修复 `make download` 的「假成功」：`include/toplevel.mk` 把 `tools/toolchain/package/target` 四个下载目录放在同一个 shell 循环里执行，整体退出码取自最后一个 `target/download`，于是 `package/` 里的 404 被吞掉、下载步骤判绿，失败一直拖到两小时后的编译阶段才暴露（本次故障就是这样浪费了 1.5-2 小时）。现在逐个目录重跑并检查退出码，上游源失效会在下载步骤内失败并在 4 次重试后终止。
- 🧱 `response_ttl` 补丁随上游源码重组一起重建：镜像里带的是上游照 2026.09.12 源码写的 `010-dns-response-ttl.patch`，而 `dae-src` 是滚动 release——pin 一旦采用新资产（2026.09.19 起），上游补丁的 hunk 就全部失配（上游把 `NormalizeAndCacheDnsResp_` 拆进了 `control/dns_controller_cache.go`、运行时可调项移到 `control/dns_controller_runtime.go`，并且不再把 A/AAAA 应答 TTL 归零），编译在 dae 的 `Build/Prepare` 阶段报 `Patch failed!`。构建改用仓库内维护的 [.github/patches/010-dns-response-ttl.patch](.github/patches/010-dns-response-ttl.patch) 覆盖镜像那份，并把语义对齐到新代码：`response_ttl > 0` 时固定下行 TTL，`0` 保持上游默认（转发真实 TTL）。覆盖发生在缓存期限由真实 TTL 推导之后，缓存命中回放的是覆盖值的剩余部分，因此客户端看到的 TTL 不再取决于是否命中缓存。该选项必须存在于二进制里——dae 的配置解析器拒绝未知键（`config/parser.go` 的 `unexpected key`），丢掉补丁会让任何带 `response_ttl` 的配置直接无法启动。
- 🧱 交给上游修，自己不再补：daed 的版本错配（`daed-src` 内嵌的 `wing/dae-core` 取自 dae 默认分支，而 dae-wing 锁的是 4 月提交）此前由我们自维护三份补丁（`response_ttl`、配置键兼容 `disable_thp`/`auto_sniff_punt`/`bpf_conn_state_map_size`/`optimistic_stale_reply_ttl`、面板流量统计镜像）。上游现已自己解决：[kenzok8/openwrt-daede](https://github.com/kenzok8/openwrt-daede) 发布 `0012-adapt-wing-to-new-core.patch` 把 `wing/` 适配到新内核，dae 也自行长出了那几个配置键，并让 TCP 中继直接记进包级口径——新版 `daed-src` 因此自带新内核。我们的 pin 机制此前仍按「旧 API 符号是否存在」判断，会把合规的新内核误判为不合规、硬钉回 4 月内核，再把面向新内核的 `0012` 打到旧内核上：该 hunk 靠 fuzz 应用，导致 `dae-core/config/marshal.go` 里 `Marshaller.Bytes` 被声明两次（2026-09-21 实机 CI 失败即为此，`Hunk #1 succeeded at 46 with fuzz 1`）。现在 `pin-daed-core.py` 的判据是「上游是否已适配」：内核仍提供 wing 未打补丁代码所需的全部旧 API 符号 → 不动它；内核更新但随包补丁系列里存在触及 `dae-core/` 的适配补丁（即 `0012`）→ 同样不动它。仅当两者都不成立（2026-09-19 那种新内核却无适配补丁的情形）才回落到 pin。同时删除了上述三份自维护补丁，只保留上游确实没有、而属于我们自有功能的 `response_ttl`（LuCI 表单会写入该键，而 daed 的解析器拒绝未知键）；它为两代内核各备一份候选（4 月核用 `dae-core-response-ttl.patch`、dae main 及其后继用 `010-dns-response-ttl.patch`），由脚本按「能否干净应用」自动选择，都不可用则在十分钟的配置阶段失败。
- ⏱️ dae 与 daed 两套补丁都在「加载自定义配置」阶段预检：用 `pin-daede-source.py` 刚取进 `dl/` 的源码按 OpenWrt 的方式逐个应用一遍（`scripts/patch-kernel.sh` 的 `for i in ${patchdir}/*` 是 shell 通配符展开，即字典序，失败即停），上游再次重组源码时十分钟内失败并打印失配的 hunk，不再拖到两小时后的编译阶段（2026.09.19 那次失败正是这样浪费了一整轮）。daed 的 11 个补丁是顺序依赖的，必须整条链一起试，单独 dry-run 会误报。
- 🧱 修复 daed 内嵌 `dae-core` 与 `wing` 的版本错配：`daed-src` tarball 里的 `wing/dae-core` 取的是 dae 的**默认分支**，而不是 dae-wing 给这个子模块锁定的提交（`daeuniverse/daed` → `wing@dc503088` → `dae-core@85a1fc3c`）。dae main 删掉 `netutils.FallbackDns` 与 `dialer.NewFromLink` 之后，`wing/` 直接编译不过，daed 包报出 6 个 `undefined`——它被前面的 dae 补丁失败挡在后面，直到这次修好 dae 才暴露出来。新增 [.github/scripts/pin-daed-core.py](.github/scripts/pin-daed-core.py)：先用六项符号探针检查 tarball 自带的 dae-core，**自带即合规就完全不改动 Makefile**（上游修好组装后自动跟随）；不合规才解析 dae-wing 真正锁定的提交、把归档取进 `dl/`，并让 daed 的 `Build/Prepare` 用 `$(DaeCore/Install)` 换掉该目录。GitHub API 不可达时沿用上次写入的 pin，候选都不满足探针则立即失败并提示更新探针。修复已用 `go generate ./...` + `go build`（`dae_stub_ebpf` 标签）在本地验证通过。
- 🧱 上述替换必须保留 submodule：GitHub 的 `/archive/<sha>.tar.gz` **不含 submodule 内容**，锁定版的 `control/kern/headers` 与 `trace/kern/headers` 是空目录，直接整体替换会让 bpf2go 编译 `tproxy.c` / `trace.c` 时报 `fatal error: 'headers/errno-base.h' file not found`（2026-09-20 那次失败即为此，前两次并行尝试也是同一原因）。`$(DaeCore/Install)` 现在先把 tarball 已materialize 的两个 header 目录暂存、换完源码再放回，并在放回后断言目录非空（空则立即失败）；`pin-daed-core.py` 也在打包前就检查随包 header 是否存在，把这一失败提前到十分钟内。
- 🧱 `$(DaeCore/Install)` 的 recipe 改为**不含任何 shell 变量**：OpenWrt 用 `$(eval $(call BuildPackage,...))` 把包的规则内联进来，而 **`$(eval)` 会把参数展开两次**——`$$path` 第一次变 `$path`、第二次被 make 当成 `$p` + `ath`，空目录检查因此查了根本不存在的路径，每次构建都在 `Build/Prepare` 报 `dae-core submodule ath is missing`（2026-09-20 第二次失败即为此）。这也说明：本地用单层展开的 `make -n` 去验证 `$` 转义会得出**相反**的结论——本轮就是这么被误导的。现在暂存/回填/校验三类命令全部由 make 层的 `$(foreach)` 生成，空目录检查改用 `ls -A | grep -q .` 取代命令替换，`make -n` 的展开结果里不含任何 `$`，因此对展开层数免疫。`pin-daed-core.py` 另加断言：生成的 recipe 里不得出现 `$$`，防止该问题回归。
- 🧱 pin 同时把 daed 的 Go 构建切到 `-mod=mod`：锁定版 dae-core（4 月）导入了 tarball 那份从未用过的模块（`bits-and-blooms/bloom/v3`、`bitset`），而 `wing/go.sum` 是照着 tarball 的 dae-core 生成的——Go 1.16 起，缺少 go.sum 条目时直接拒绝构建，OpenWrt 的 `go list`/`go install` 正跑在这个只读模式下，于是 daed 在 `wing/.built` 报 `missing go.sum entry ... to add: go get github.com/daeuniverse/dae/control@v0.2.0`（2026-09-20 第三次失败即为此）。`pin-daed-core.py` 现在会一并改写 `GO_PKG_BUILD_VARS+= GOFLAGS=...` 加上 `-mod=mod`，让 Go 自行补齐缺失的间接依赖与校验和；上游修好组装、pin 被移除时该行会自动还原。已在**全新解包**的树上按 CI 模式复现该失败并验证修复：`go list`、`go generate`、`go build` 全部通过。
- 🧱 daed 内嵌的 dae 内核也补上 `response_ttl`：daed 在进程内构建控制面（`wing/dae/run.go` 调用 `control.NewControlPlane`）并解析同一份 dae 配置，而它的 `config/parser.go` 同样拒绝未知键——`active_backend` 切到 `daed` 时，LuCI 生成的含 `response_ttl` 的配置会让 daed 直接起不来（该选项此前只打在独立的 `dae` 包上）。新增 [.github/patches/dae-core-response-ttl.patch](.github/patches/dae-core-response-ttl.patch)：上游原版补丁正好就是照 dae-wing 锁定的那个内核写的，可零冲突应用；其自带测试的夹具用了没有 logger 的裸 controller、运行即 panic，已改用 `newScopedDnsController`，并另加一条解析器验收测试（含 `response_ttl` 的配置必须解析成功且取到值）。`pin-daed-core.py` 把「替换内核」与「打该补丁」合并成一个调整块：先探测内核是否已认识 `response_ttl`（认识则不打补丁，上游跟上后自动免维护），再 dry-run 验证补丁可应用（不可应用则十分钟内失败并提示重建），构建期由 `$(DaeCore/ApplyPatch)` 在换树之后执行。验证：打补丁后 `config`/`control` 两套测试全绿（含两条新测试），并用真实 clang 18.1.8 跑通 bpf2go 与真实标签构建。
- 🧱 新增构建期断言 [.github/scripts/check-dae-config-compat.py](.github/scripts/check-dae-config-compat.py)：dae 包 `example.dae` 里出现的**每个键**都必须被 daed 实际构建的那个 dae-core 接受（pin 过就读 `dl/` 里 pin 的归档，未 pin 就读 daed-src 自带的 `wing/dae-core`）。读取的是构建真正会用的两个 tar 包，并把构建期那套补丁序列**按序重放**到按 `$(DaeCore/Install)` 方式解包的内核上——只比对归档会拿未打补丁的 4 月内核去对模板，从而把兼容补丁新增的键全部误报为不兼容；上游下次给 dae 加键时十分钟内失败并列出「模板文件:行号 段.键」，而不是等运行时把整份配置丢掉。已用真实资产验证：对 pin 的 4 月内核报出 `global.bpf_conn_state_map_size` / `global.disable_thp` / `global.auto_sniff_punt`，加上兼容补丁后 36 个模板键全部通过，未 pin（自带内核已是 dae main）时同样通过，模板里塞入虚构新键则按预期失败。
- 🧱 上述断言的补丁重放是对**它在 CI 中真实行为**的修正：脚本原先只扫未打补丁的归档，于是必然报出 `global.bpf_conn_state_map_size` / `global.disable_thp` / `global.auto_sniff_punt` 并返回 1，而它在 `diy-part2-daed.sh` 里由 `set -euo pipefail` 调用——构建会在第 10 分钟中断（等于把「配置面漂移」这个被修的故障换成了「构建必失败」）。现在脚本按 Makefile 的 `DAE_CORE_PATCHES` 顺序、从 `package/dae/daed/dae-core-patches/` 取补丁并在临时解包目录上真实应用后再扫键；`--core-archive` 显式覆盖时按调用方保证的内容处理、不重放。验证：补丁序列齐全时 `series applied: … , 56 config keys` / `all 36 template keys are accepted`（exit 0）；序列里去掉兼容补丁时仍按预期列出那 3 个键并 exit 1；补丁文件缺失时给出可操作报错；两份补丁叠加后的内核 `go build` 与 `config`/`control` 测试全绿，且含 `disable_thp`/`auto_sniff_punt`/`bpf_conn_state_map_size`/`optimistic_stale_reply_ttl` 的配置能被解析（即实机那条报错已被消除）。
- 🧱 兼容补丁的验收方式与 `response_ttl` 那份一致：`go build -tags dae_stub_ebpf ./config/... ./control/... ./cmd/...` 干净，`go test -tags dae_stub_ebpf -count=1 ./config/ ./control/ ./cmd/` 全绿；两条新解析器测试（含四个新键的配置必须解析成功、缺省时默认值不变）在**未打补丁的固定核**上复现出实机同一条错误 `failed to parse "global": unexpected key: disable_thp`，证明它们钉住的正是这次的回归。

### Changed
- 🔄 构建矩阵收敛为两个正式 ImmortalWrt 固件：`immortalwrt/master` 与 `immortalwrt/openwrt-25.12`；产物名称不再使用 `immortalwrt-daed` 后缀。
- 🔄 固件内容统一按当前 `192.168.50.1` 路由器软件结构构建：Daed + 双 AdGuardHome + Lucky + Watchdog + SQM + UPnP + SFTP。
- 🔄 第三方插件不再从个人聚合仓库拉取：Lucky、Watchdog 直接从各自上游仓库克隆；Golang、AdGuardHome 使用 ImmortalWrt 官方 packages feed。
- 🔄 `dae`、`daed` 与统一管理界面 `luci-app-daede` 全部改用 `kenzok8/openwrt-daede`，并在构建前移除 ImmortalWrt feeds 中的官方同名/旧版入口。
- 🔄 Golang 改为直接使用 ImmortalWrt 官方 `packages/lang/golang`（官方 master/openwrt-25.12 已为 Go 1.26.x），不再用第三方 Golang 覆盖官方 feed。
- 🔄 关闭 ext4 rootfs 与 ext4 文件系统包，Release 仅构建并发布 squashfs 相关镜像和 rootfs.tar.gz。

### Fixed
- 补齐 `kmod-sched` 提供的 FQ 模块；性能脚本显式加载 `sch_fq`，sysctl 失败时记录原因并返回失败。
- 开启 IMAGEOPT/PREINITOPT，使恢复模式的 `192.168.50.1` 与广播地址在 `make defconfig` 后仍然生效。
- 内核配置附件限定从 x86 目标构建目录导出，校验架构及 BPF/BTF、XDP、FQ、BBR，拒绝误用辅助构建的 MIPS 配置。
- 构建配置改为经过两个分支解析验证的精简选项，移除过期符号、无效禁用写法和无使用方的 Ruby 包，保留 QEMU Guest Agent 的 GLib 依赖。
- 双 AdGuardHome 新装默认查询日志保留期由 90 天改为 7 天；保留配置升级继续沿用已有 YAML。
- 修复 `luci-app-daede` 将 DNS 初始化迁入 `config-defaults.sh` 后两个云编译分支在加载自定义配置时失败的问题；补丁兼容新旧布局，首次初始化和插件重置均使用双 AdGuardHome 上游。
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
