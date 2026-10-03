# dnsmasq + daed + 双 AdGuardHome 实际方案

本文描述实机的 **daed** 方案。固件同时包含 dae/daed，当前构建选择
`luci-app-daede` 的 dae 变体；这不代表实机正在使用 dae，也不意味着新装固件已配置好
本文的节点和 DNS 分流。上游默认值不做本地修改。

```text
LAN clients
  ↓ DNS :53
dnsmasq
  ↓ daed 透明 DNS 接管 / 分流
daed DNS routing
  ├─ geosite:private / geosite:cn → ADH-direct :50530 → ISP IPv4/IPv6 DNS
  └─ fallback / 国外域名          → ADH-proxy  :50531 → 经代理的 IPv4 DoH
                                                     └─ 上游失败 → ADH-direct
```

> 本方案使用透明 DNS 接管，不暴露固定 `50500` listener；不要把 dnsmasq 直接改到
> `127.0.0.1#50500`。实机配置由 daed 面板维护，保存在 `/etc/daed/wing.db`。

## 端口

| 组件 | 地址 | 端口 | 用途 |
| --- | --- | ---: | --- |
| dnsmasq | LAN / loopback | 53 | LAN DNS 入口 |
| ADH-direct DNS | 127.0.0.1 / ::1 | 50530 | 国内 DNS 后端 |
| ADH-proxy DNS | 127.0.0.1 / ::1 | 50531 | 国外 DNS 后端 |
| ADH-direct Web | 127.0.0.1（新装） | 50080 | 设置认证前仅本机/SSH 隧道管理 |
| ADH-proxy Web | 127.0.0.1（新装） | 50081 | 设置认证前仅本机/SSH 隧道管理 |
| daed Web | 0.0.0.0 / :: | 2023 | daed 管理 |

## 关键兼容性处理

1. DNS 配置由 daed 面板维护，不使用全局 `ipversion_prefer: 4`。`luci-app-daede` 按上游原样编译，其 dae 表单只在切换到 dae 后端时生效，写出的是上游默认的 `cndns` / `fallbackdns`，不是本方案。
2. 不使用全局 `l4proto(udp) && dport(443) -> block`，避免影响手机 App / 游戏 / QUIC / HTTP3。
3. 两个 ADH 实例共用官方 `adguardhome` 包提供的 `/usr/bin/AdGuardHome` 二进制；固件只额外提供 `/usr/bin/AdGuardHome-direct` 和 `/usr/bin/AdGuardHome-proxy` 两个 symlink，用于保留代理内核的 `pname(...)` 分流能力。
4. ADH-direct 的实际 Linux 进程名必须全直连，避免 ISP DNS 查询被再次送回 ADH 形成环路。
5. ADH-proxy 的国外 DoH HTTPS 连接走代理；其到 `127.0.0.1:50530` 的本机兜底请求应到达 ADH-direct，不能被重新送进代理。此行为需要结合实际 daed routing 验证，不能仅由 YAML 推断。
6. ADH-proxy 的主上游使用 IP-literal DoH，减少 bootstrap 自引用问题。
7. 不要在 LuCI 里切到 dae 后端后保存 dae 表单：上游生成器会直接覆盖 `/etc/dae/config.dae`，丢掉表单无法表达的节点组和 routing。

## 当前 ADH 默认模板

以下是仓库的新装默认，不会强制覆盖保留配置升级后的 YAML。

### ADH-direct

- DNS：`127.0.0.1:50530` / `[::1]:50530`
- Web：新装为 `http://127.0.0.1:50080`；设置认证后可改回 LAN 地址
- 上游：ISP DNS
  - `221.7.128.68`
  - `221.7.136.68`
  - `2408:8001:4000:9000:221:7:128:68`
  - `2408:8001:4010:9000:221:7:136:68`
- `upstream_mode: parallel`、`upstream_timeout: 10s`、`fallback_dns: []`
- `aaaa_disabled: false`：保留国内双栈。
- 策略：国内广告过滤，稳定优先。

### ADH-proxy

- DNS：`127.0.0.1:50531` / `[::1]:50531`
- Web：新装为 `http://127.0.0.1:50081`；设置认证后可改回 LAN 地址
- 主上游：四个 IPv4 DoH，经代理访问
  - `https://1.1.1.1/dns-query`
  - `https://1.0.0.1/dns-query`
  - `https://8.8.8.8/dns-query`
  - `https://8.8.4.4/dns-query`
- `upstream_mode: parallel`、`upstream_timeout: 3s`
- `aaaa_disabled: true`：当前默认暂时禁用国外 AAAA；不是所有 daed 部署的必需设置。
- 故障兜底：`fallback_dns: [127.0.0.1:50530]`。主上游请求失败时尝试国内直连解析器，以减少代理节点不可用造成的 DNS 级联超时。
- 策略：国外广告/隐私过滤，中高强度。

**兜底的取舍：**这是可用性优先的降级，不是严格的 DoH-only。降级后的查询会进入
ADH-direct 的 ISP 明文 DNS 路径，可能得到不同或受污染的结果。兜底不保证国外域名
解析成功，更不能修复代理业务连接。`3s` 是主上游超时设置，不是端到端时延上限：
直连后端自身还有 `10s` 上游超时，缓存和实际故障形式也会影响观察结果。

## daed 中的 DNS 配置核心

以下是代理内核配置的示意，需在 daed 面板维护对应规则，不是写入 `/etc/dae/config.dae`
即可生效的实机配置。

```text
dns {
  upstream {
    adh_direct: 'udp://127.0.0.1:50530'
    adh_proxy: 'udp://127.0.0.1:50531'
  }

  routing {
    request {
      qname(geosite:private) -> adh_direct
      qname(geosite:cn) -> adh_direct
      qname(suffix:cloudflare-dns.com) -> adh_direct
      qname(suffix:dns.google) -> adh_direct
      qname(suffix:dns.quad9.net) -> adh_direct
      qname(suffix:dns.adguard-dns.com) -> adh_direct
      qname(suffix:doh.opendns.com) -> adh_direct
      qname(suffix:dns.sb) -> adh_direct
      qname(suffix:doh.mullvad.net) -> adh_direct
      qname(suffix:filters.adtidy.org) -> adh_direct
      qname(suffix:big.oisd.nl) -> adh_direct
      qname(suffix:urlhaus.abuse.ch) -> adh_direct
      fallback: adh_proxy
    }
  }
}
```

此前的实机配置另手工吸收了
[`cs3306/adguard-dns-divert`](https://github.com/cs3306/adguard-dns-divert) 的显式自定义域名例外：
国内例外走 `adh_direct`，明确的国外域名走 `adh_proxy`。项目生成结果中的裸 TLD
（包括 `cn`）不导入，避免覆盖现有 `geosite:cn` 分流。更新时需在 daed 面板/配置接口
预检规则并确认优先级后再应用。**仓库不包含这些实机规则的快照、导入器或自动预检流程，
新装固件不会自动获得这些例外。**

## daed 中的 routing 要点

```text
# 代理内核在当前内核优先读取 16 字节 argv 名，降级时读取 15 字节 comm；两种都匹配。
pname(AdGuardHome-dir, AdGuardHome-dire) -> must_direct
# ADH-proxy 的国外 DoH 应走当前配置的代理组；default_vmiss 是实机组名，不是上游默认。
pname(AdGuardHome-pro, AdGuardHome-prox) -> default_vmiss
# 不要添加 l4proto(udp) && dport(443) -> block
```

应用前同时确认 loopback 兜底请求不会被上述进程规则送往远端代理。不要照抄组名，
也不要把 ADH-proxy 的所有国外 DoH 流量设为 direct。

## sysupgrade 保留与显式更新

keep.d 保留以下配置：

```text
/etc/AdGuardHome-direct.yaml
/etc/AdGuardHome-proxy.yaml
/etc/config/dae
/etc/config/daed
/etc/config/daede
/etc/dae
/etc/daed
/etc/config/dhcp
```

`99-adh-dual` 会更新服务 wrapper，并收紧无认证 Web UI 的监听地址，但**不会迁移
旧 YAML 的 DNS 上游、fallback 或 timeout**。保留配置升级后，这次模板改动不会自动生效。

已有设备只有在接受上述降级取舍后才需要更新。可以通过 ADH-proxy 管理界面修改，
或手工编辑；不要用仓库模板覆盖整份配置，以免丢失用户认证、过滤规则和其他自定义值。
手工更新示例（以下命令只作操作说明，本次仓库检查不会执行）：

1. 备份并确认成功，再停止 ADH-proxy，避免运行中的服务重写 YAML：

   ```sh
   backup="/root/AdGuardHome-proxy.yaml.before-fallback.$(date +%Y%m%d-%H%M%S)"
   cp -p /etc/AdGuardHome-proxy.yaml "$backup" && ls -l "$backup"
   # 仅在备份成功后继续；记下输出的备份文件名。
   /etc/init.d/adh-proxy stop
   vi /etc/AdGuardHome-proxy.yaml
   ```

2. 只在现有 `dns:` 映射中调整这两个字段，不要重复添加第二个 `dns:` 或同名键：

   ```yaml
   dns:
     fallback_dns:
       - 127.0.0.1:50530
     upstream_timeout: 3s
   ```

3. 启动并检查服务及解析：

   ```sh
   /etc/init.d/adh-proxy start
   /etc/init.d/adh-proxy status
   nslookup google.com 127.0.0.1:50531
   ```

4. 如需回退，在同一 shell 使用前面记录的 `$backup`（新会话请填实际文件名）：

   ```sh
   /etc/init.d/adh-proxy stop
   cp -p "$backup" /etc/AdGuardHome-proxy.yaml
   /etc/init.d/adh-proxy start
   ```

更新这两个字段不要求同时改变现有 AAAA 策略或节点配置。

## 验证

仓库静态检查（开发机需 Python 3 和 PyYAML；不连接路由器）：

```sh
python3 .github/scripts/check-adh-config.py files/etc
python3 .github/scripts/test-check-adh-config.py
```

该检查只约束仓库模板，不能验证 daed 的实机 routing、代理节点和 ISP 可达性。
实机检查示例：

```sh
/etc/init.d/adh-direct status
/etc/init.d/adh-proxy status
nslookup baidu.com 127.0.0.1:50530
nslookup google.com 127.0.0.1:50531
nslookup baidu.com 127.0.0.1
nslookup google.com 127.0.0.1
nslookup -query=AAAA baidu.com 127.0.0.1:50530
nslookup -query=AAAA google.com 127.0.0.1:50531
```

当前模板下 direct 保留 AAAA 能力，proxy 应返回空 AAAA 结果。结合两个 ADH 的查询日志
以及 daed 面板的日志确认实际命中的上游；不要以 `/var/log/dae/dae.log` 代替 daed 的日志。

完整故障验证需要另选维护窗口或隔离测试环境：确认正常主路径经代理 DoH；模拟主上游
失败后确认请求到达 ADH-direct、无反复回环；恢复后确认新的未缓存请求回到 DoH 主路径。
ADH 启用了缓存和乐观缓存，仅重复查询已缓存域名不能证明兜底或恢复生效。
本次静态检查和 defconfig 验证不包含这些实机故障测试。

## 国外 IPv6 的可选恢复

当前模板保留国内双栈，但 ADH-proxy 使用 IPv4 DoH 且 `aaaa_disabled: true`，以避开此前的
国外 IPv6 出口故障。确认国外 IPv6 代理链路恢复后，可以选择：

1. 备份 ADH-proxy 和 daed 的配置，通过管理界面把 proxy 的 `aaaa_disabled` 改为 `false`；
   若手工编辑 YAML，先停止服务，修改后再启动。
2. 如 daed 面板中曾加过下面的临时 response 规则，同时移除它；否则 ADH 恢复 AAAA 后，
   daed 仍可能拒绝结果：

   ```text
   qtype(aaaa) && qname(geosite:geolocation-!cn) -> reject
   ```

3. 按上一节验证国外 AAAA 和实际 IPv6 连接。获得 AAAA 记录不代表 IPv6 出口已经可用。
4. IPv4 DoH 同样可以查询 AAAA，无需为恢复 AAAA 强行添加 IPv6 DoH。仅在验证可达后，
   才考虑额外加入以下上游：

   ```text
   https://[2606:4700:4700::1111]/dns-query
   https://[2606:4700:4700::1001]/dns-query
   https://[2001:4860:4860::8888]/dns-query
   https://[2001:4860:4860::8844]/dns-query
   ```

不要使用以下全局止血规则，除非明确接受副作用：

```text
# 会破坏国内 IPv6 双栈，不推荐：
dhcp.@dnsmasq[0].filter_aaaa='1'

# 会影响部分手机 App / 游戏 / QUIC，不推荐：
l4proto(udp) && dport(443) -> block
```
