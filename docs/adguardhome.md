# 当前 master 的双 AdGuardHome

[返回文档入口](index.md)

本文适用于 [Honk master 固件](honk.md)，不适用于不含 ADH 的 [IPTV 固件](iptv.md)。
历史 daed 部署记录保留在 [旧方案文档](dnsmasq-daed-dual-adh.md)，仅供回滚和核对旧配置。

## 服务与 DNS 路径

两个实例共用官方包提供的 `/usr/bin/AdGuardHome`，通过 `AdGuardHome-direct` 和
`AdGuardHome-proxy` 两个 symlink 启动。各自使用独立 procd 服务、YAML 和工作目录：

| 实例 | 服务 | 配置 | 工作目录 | DNS / Web 端口 |
| --- | --- | --- | --- | --- |
| direct | `adh-direct` | `/etc/adguardhome-direct/AdGuardHome.yaml` | `/srv/adguardhome-direct` | `50530` / `50080` |
| proxy | `adh-proxy` | `/etc/adguardhome-proxy/AdGuardHome.yaml` | `/srv/adguardhome-proxy` | `50531` / `50081` |

两个服务使用 `adguardhome` 用户、上游 capabilities、`no_new_privs` 与独立的 procd jail。
每个实例只能写自己的配置和工作目录，运行日志用 `logread` 查看。自定义本地证书、密钥或上游列表
应放入对应实例的私有配置目录并更新 YAML 路径；不要给 jail 放行整个 `/etc`。
首启迁移旧 YAML 后，原有 `/etc/AdGuardHome-*.yaml` 路径是兼容链接；编辑请使用表内正式路径，
避免某些编辑器原子保存时替换链接。若发现新旧两份不同的用户配置，迁移拒绝覆盖，请先备份并人工合并。

DNS 监听 `127.0.0.1` / `::1`；新装 Web 仅监听 IPv4 loopback。官方单实例
`adguardhome` 服务会被禁用，避免与双实例冲突。

```text
LAN 普通 DNS -> Honk 透明接管 / DNS routing
                   |-> ADH-direct :50530 -> ISP DNS
                   `-> ADH-proxy  :50531 -> 经代理的 DoH
                                              `-> 失败时 ADH-direct

.lan / 本地反查 -> dnsmasq
DHCP           -> dnsmasq
```

新装的 Honk 模板已接入双 ADH，但不会开启 Honk 或创建节点。保留配置升级不改变 DNS 或节点。
如需让已有配置采用同一路径，可比较 `/usr/share/honk/default-config.dae`：两个回环 DNS 后端都用
`-> direct`，不把本机 DNS 端口发给代理节点。流量规则依次让 `AdGuardHome-pro` 的回环访问直连、
该进程的 443 出站走 `proxy`、其余 ADH 流量直连。自定义 DoH 端口或代理组时需同步调整；
实例名取 15 字节前缀，与内核进程名一致。不要整份替换正在使用的配置。
dnsmasq 可以继续监听 53，但不代表所有被透明接管的查询都先经过它。

## 首次管理与启动等待

模板为 `users: []`，不内置登录密码哈希，因此先通过 SSH 隧道访问：

```sh
ssh -L 50080:127.0.0.1:50080 -L 50081:127.0.0.1:50081 root@192.168.50.1
```

浏览器打开 `http://127.0.0.1:50080` 或 `http://127.0.0.1:50081`。配置认证后，才根据需要将
相应 YAML 的 `http.address` 改为 LAN 地址并重启服务；不要直接把无认证界面开放到 LAN/WAN。
需要生成 bcrypt 哈希时可在电脑运行 `htpasswd -nBC 10 root`，取冒号后的哈希写入 `users`。

服务启动由 `adh-wait-start` 等待配置中的 Web 绑定地址就绪；IPv6 压缩/展开写法等价，
处于 `tentative` / `dadfailed` 状态的地址不会被视为可用。等待发生在 procd 管理的进程中，
不阻塞整个开机序列，但该实例的 DNS 和 Web 都要等地址就绪才启动。
若长时间未就绪，检查 YAML 中的地址是否确实属于本机：

```sh
ip -o address show
logread -e adh-start
/etc/init.d/adh-direct status
/etc/init.d/adh-proxy status
```

## 新装默认模板

实际配置以 [`AdGuardHome-direct.yaml`](../files/etc/AdGuardHome-direct.yaml) 和
[`AdGuardHome-proxy.yaml`](../files/etc/AdGuardHome-proxy.yaml) 为准：

| 设置 | direct | proxy |
| --- | --- | --- |
| 主上游 | `221.7.128.68`、`221.7.136.68` 及对应 ISP IPv6 DNS | `https://1.1.1.1/dns-query`、`https://1.0.0.1/dns-query`、`https://8.8.8.8/dns-query`、`https://8.8.4.4/dns-query` |
| 上游模式 | `parallel` | `parallel` |
| 上游超时 | `10s` | `3s` |
| 兜底 | 无 | `127.0.0.1:50530` |
| AAAA | 保留 | 暂时禁用（`aaaa_disabled: true`） |
| 缓存上限 | 64 MiB | 8 MiB |
| 查询日志保留 | 7 天 | 7 天 |

**兜底是可用性优先的降级，不是严格的 DoH-only。** 降级查询会进入 direct 的 ISP 明文 DNS，
可能得到不同或受污染的结果；它不保证国外域名解析成功，也不能修复代理业务连接。
`3s` 只是 proxy 主上游的超时，不是端到端时延上限，direct 自身还有 `10s` 上游超时。

IPv4 DoH 同样可以查询 AAAA。确认国外 IPv6 代理链路可用后，可自行恢复 proxy 的 AAAA，
同时检查 Honk 是否另有拒绝 AAAA 的响应规则。获得 AAAA 记录不等于 IPv6 出口已可用。
不要为了国外故障而全局禁用 dnsmasq AAAA，或全局阻断 UDP/443。

## 保留配置与显式更新

sysupgrade 保留两个 YAML。`99-adh-dual` 会恢复新版服务 wrapper，并收紧无认证 Web 的
监听地址，但不会用模板覆盖用户的 DNS 上游、过滤器、认证和节点相关设置。
已有用户配置的监听地址会保留；合法的无缩进 `users` 列表同样可被识别。

工作目录 `/srv/adguardhome-*` 在普通重启时保留，但不在项目的 sysupgrade keep.d 中。
需要保留查询日志、统计或过滤规则缓存时，应自行纳入备份；不能将普通重启持久化等同于升级保留。

采用新版默认前，先比较设备现有 YAML 与 `/rom/etc/AdGuardHome-*.yaml`，不要整份覆盖。
以下以调整 proxy 的 fallback/timeout 为例；先确认接受前述明文降级取舍：

1. 备份成功后再停止服务，避免运行中的 ADH 重写 YAML：

   ```sh
   backup="/root/AdGuardHome-proxy.yaml.before-edit.$(date +%Y%m%d-%H%M%S)"
   conf=/etc/adguardhome-proxy/AdGuardHome.yaml
   cp -p "$conf" "$backup" && ls -l "$backup"
   # 仅在备份成功后继续；另将备份下载到电脑或 NAS。
   /etc/init.d/adh-proxy stop
   vi "$conf"
   ```

2. 只修改现有 `dns:` 映射中的字段，不新增第二个 `dns:` 或重复键：

   ```yaml
   dns:
     fallback_dns:
       - 127.0.0.1:50530
     upstream_timeout: 3s
   ```

3. 启动并核查解析；这两个字段的修改不要求同时改变 AAAA 或 Honk 节点配置：

   ```sh
   /etc/init.d/adh-proxy start
   /etc/init.d/adh-proxy status
   nslookup google.com 127.0.0.1:50531
   ```

4. 如需回退，在同一 shell 使用记录的 `$backup`；新会话需填入实际备份文件名：

   ```sh
   /etc/init.d/adh-proxy stop
   cp -p "$backup" "$conf"
   /etc/init.d/adh-proxy start
   ```

## 验证边界

开发机上可运行模板和脚本回归测试（Python 3 + PyYAML，不连接路由器）：

```sh
python3 .github/scripts/check-adh-config.py files/etc
python3 .github/scripts/test-check-adh-config.py
python3 .github/scripts/test-adh-wait-start.py
python3 .github/scripts/test-adh-migration.py
```

实机需结合 Honk 和两个 ADH 的日志确认实际路径，尤其是 proxy 的 DoH 出站和本机兜底。
完整故障测试应在维护窗口或隔离环境进行：正常请求走代理 DoH，主上游失败时到 direct 且
没有回环，恢复后新查询重新走 DoH。ADH 启用了缓存和乐观缓存，反复查询已缓存域名不能
证明兜底或恢复生效。仓库的静态检查不能替代这些实机验证。
