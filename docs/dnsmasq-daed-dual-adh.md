# dnsmasq + daed + 双 AdGuardHome 实际方案

实际链路：

```text
LAN clients
  ↓ DNS :53
dnsmasq
  ↓ daed 透明 DNS 接管/分流
daed DNS routing
  ├─ geosite:private / geosite:cn → ADH-direct :50530 → ISP IPv4/IPv6 DNS
  └─ fallback / 国外域名            → ADH-proxy  :50531 → DoH-only DNS
```

> 当前 daed/daed UI 使用透明 DNS 接管，不暴露固定 `50500` listener；不要把 dnsmasq 直接改到 `127.0.0.1#50500`。

## 端口

| 组件 | 地址 | 端口 | 用途 |
| --- | --- | ---: | --- |
| dnsmasq | LAN / loopback | 53 | LAN DNS 入口 |
| ADH-direct DNS | 127.0.0.1 / ::1 | 50530 | 国内 DNS 后端 |
| ADH-proxy DNS | 127.0.0.1 / ::1 | 50531 | 国外 DNS 后端 |
| ADH-direct Web | 192.168.50.1 | 50080 | 国内实例管理 |
| ADH-proxy Web | 192.168.50.1 | 50081 | 国外实例管理 |
| daed Web | 0.0.0.0 / :: | 2023 | daed 管理 |

## 关键兼容性处理

1. 去掉 daed DNS 的 `ipversion_prefer: 4`，避免近似“只用 IPv4”。
2. 去掉全局 `l4proto(udp) && dport(443) -> block`，避免影响手机 App / 游戏 / QUIC / HTTP3。
3. 两个 ADH 实例共用官方 `adguardhome` 包提供的 `/usr/bin/AdGuardHome` 二进制；固件只额外提供 `/usr/bin/AdGuardHome-direct` 和 `/usr/bin/AdGuardHome-proxy` 两个 symlink，用于保留 daed `pname(...)` 分流能力。
4. daed routing 只让 `pname(AdGuardHome-direct)` 全直连，避免 ISP DNS 查询被 daed 再次送回 ADH 形成环路。
5. `adh-proxy` 对应的 DoH HTTPS 连接不直连；按 daed 规则走代理。
6. `adh-proxy` 的 DoH 上游使用 IP-literal DoH，减少 bootstrap 自引用问题。

## ADH-direct

- DNS：`127.0.0.1:50530` / `[::1]:50530`
- Web：`http://192.168.50.1:50080`
- 上游：ISP DNS
  - `221.7.128.68`
  - `221.7.136.68`
  - `2408:8001:4000:9000:221:7:128:68`
  - `2408:8001:4010:9000:221:7:136:68`
- 策略：国内广告过滤，稳定优先。

## ADH-proxy

- DNS：`127.0.0.1:50531` / `[::1]:50531`
- Web：`http://192.168.50.1:50081`
- 上游：DoH only
  - `https://1.1.1.1/dns-query`
  - `https://1.0.0.1/dns-query`
  - `https://8.8.8.8/dns-query`
  - `https://8.8.4.4/dns-query`
  - `https://[2606:4700:4700::1111]/dns-query`
  - `https://[2606:4700:4700::1001]/dns-query`
  - `https://[2001:4860:4860::8888]/dns-query`
  - `https://[2001:4860:4860::8844]/dns-query`
- 策略：国外广告/隐私过滤，中高强度。

## daed DNS 配置核心

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

## daed routing 核心变更

```text
pname(AdGuardHome-direct) -> must_direct
# 不要添加 pname(AdGuardHome-proxy) -> direct
pname(AdGuardHome-proxy) -> default_vmiss
# 不要添加 l4proto(udp) && dport(443) -> block
```

## 验证

```sh
nslookup baidu.com 127.0.0.1:50530
nslookup google.com 127.0.0.1:50531
nslookup baidu.com 127.0.0.1
nslookup google.com 127.0.0.1
nslookup -query=AAAA google.com 127.0.0.1

tail -n 200 /var/log/daed/daed.log | grep -E '127.0.0.1:5053|AdGuardHome-prox|AdGuardHome-dire'
```

## sysupgrade 保留

当前应保留：

```text
/etc/AdGuardHome-direct.yaml
/etc/AdGuardHome-proxy.yaml
/etc/daed
/etc/config/daed
/etc/config/dhcp
```


## 临时关闭国外 AAAA 解析（保留国内双栈）

当国外 IPv6 出口（例如 CC 节点 IPv6）故障时，只关闭国外 AAAA，不要全局过滤 AAAA：

1. `ADH-direct` 保持 `aaaa_disabled: false`，国内 IPv4/IPv6 双栈正常。
2. `ADH-proxy` 临时设置 `aaaa_disabled: true`，国外只返回 IPv4。
3. daed DNS response 只拒绝非中国域名 AAAA：

```text
response {
  qtype(aaaa) && qname(geosite:geolocation-!cn) -> reject
  fallback: accept
}
```

故障期间如 ADH-proxy 上游列表里有 IPv6 DNS/DoH，可临时移除，避免上游探测超时：

```sh
cp /etc/AdGuardHome-proxy.yaml /etc/AdGuardHome-proxy.yaml.bak-before-disable-foreign-aaaa-$(date +%Y%m%d-%H%M%S)
sed -i 's/^  aaaa_disabled: false/  aaaa_disabled: true/' /etc/AdGuardHome-proxy.yaml
sed -i '/2606:4700:4700::/d; /2001:4860:4860::/d' /etc/AdGuardHome-proxy.yaml
/etc/init.d/adh-proxy restart
```

不要使用这些全局止血规则，除非明确接受副作用：

```text
# 会破坏国内 IPv6 双栈，不推荐：
dhcp.@dnsmasq[0].filter_aaaa='1'

# 会影响部分手机 App / 游戏 / QUIC，不推荐：
l4proto(udp) && dport(443) -> block
```

恢复国外 IPv6：

```sh
# 如需恢复被临时移除的 IPv6 上游，优先从上面的 bak 文件恢复；或手工加回原 IPv6 DNS/DoH。
sed -i 's/^  aaaa_disabled: true/  aaaa_disabled: false/' /etc/AdGuardHome-proxy.yaml
/etc/init.d/adh-proxy restart
```

## 国外 ADH-proxy 上游要求

`ADH-proxy` 的国外上游必须使用 DoH/DoT，并且它自身的出站连接必须经 daed 代理，避免明文国外 DNS 被污染或超时。当前临时方案使用 IPv4 DoH（CC IPv6 恢复前不放 IPv6 DoH）：

```yaml
dns:
  upstream_dns:
    - https://1.1.1.1/dns-query
    - https://1.0.0.1/dns-query
    - https://8.8.8.8/dns-query
    - https://8.8.4.4/dns-query
  upstream_mode: parallel
  aaaa_disabled: true
```

对应 daed routing 需要有：

```text
pname(AdGuardHome-direct) -> must_direct
pname(AdGuardHome-proxy) -> default_vmiss
```

这样国外 DNS 路径为：

```text
client/dnsmasq -> daed DNS -> ADH-proxy :50531 -> DoH(1.1.1.1/8.8.8.8) -> default_vmiss
```

国内 `ADH-direct` 也使用并行请求：

```yaml
dns:
  upstream_mode: parallel
  aaaa_disabled: false
```
