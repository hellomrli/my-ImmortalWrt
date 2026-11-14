# 检查并理解性能参数

[返回文档入口](index.md)

固件预置 [`/etc/sysctl.d/99-performance.conf`](../files/etc/sysctl.d/99-performance.conf)，
针对「x86 + 透明代理」这个具体场景，而不是通用模板。

BBR 拥塞控制。 普通路由器开 BBR 没有意义——转发流量由两端主机的拥塞控制决定。
但透明代理核心会在本机终结客户端 TCP、再向代理服务器发起新连接，这些出站连接用的是路由器自己的
拥塞控制。国际链路通常有丢包，cubic 每次丢包都会大幅收缩窗口，BBR 按实测带宽和 RTT 建模，
可能改善有损长 RTT 路径上的吞吐，效果需实测。配套的 `fq` 只作用于没有显式 qdisc 的接口，
WAN 上的 SQM/cake 不受影响。`sch_fq` 由 `kmod-sched` 提供，启动脚本会加载该模块；
sysctl 应用失败时记录错误，不再无条件报告成功。

套接字缓冲区。 按本线路的带宽延迟积（1000 Mbit/s 下行 / 100 Mbit/s 上行）计算，
而不是取一个「够大」的数。单条连接要跑满管道需要 BDP 字节的缓冲：

| | 50 ms | 100 ms | 250 ms |
| --- | ---: | ---: | ---: |
| 下行 1000 Mbit/s | 6 MiB | 12 MiB | 30 MiB |
| 上行 100 Mbit/s | 0.6 MiB | 1.2 MiB | 3.0 MiB |

所以接收上限取 32 MiB（覆盖最差的代理 RTT），发送上限 16 MiB（已是 100 Mbit/s 上行需求的
5 倍余量）。只抬高上限，中间那个值是每条连接的起始大小、保持内核默认——Linux 会按需
向上自动调节，上限高不占用内存，而调高默认值会乘以连接数。

连接跟踪。 代理场景下每条客户端连接消耗两个 conntrack 条目（客户端→路由器、
路由器→代理服务器），所以上限提到 262144，同时把哈希桶提到约 max/4——只提上限不提桶
会让每次查表变慢。代价：条目按需分配、每条约 300 B，表真填满才用到 75 MiB；桶数组预分配
512 KiB。

并非所有参数都是越大越好。 `netdev_max_backlog` 保持在 16384 而没有拉满：它是缓冲区，
调大不会增加吞吐，只会让报文在 CPU 处理前排更久的队——这就是 bufferbloat。16384 足以吸收
1 Gbit/s 下的突发。

临时端口范围。 代理路由器的出站连接远多于普通路由器，所以扩大了 ephemeral 端口范围。
扩大后的范围覆盖了本固件的服务端口，因此显式保留 `2023,12345,50080,50081,50530,50531`；
否则服务重启时可能出现端口已被临时连接占用而起不来。

`tcp_fin_timeout=30` 限制孤立连接在 `FIN_WAIT_2` 中等待对端关闭的时间，不改变
`TIME_WAIT` 超时。`tcp_notsent_lowat=16384` 限制应用排队的未发送数据，通过写入背压
约束缓冲积压，不会绕过 TCP 拥塞窗口。

> `nf-conntrack` 没有 AutoLoad，要等防火墙（START=19）装规则时才加载，而
> `/etc/init.d/sysctl` 在 START=11 就跑完并且用的是 `sysctl -e`（静默忽略不存在的键）。
> 所以 conntrack 那两项由 [`/etc/init.d/perf-tune`](../files/etc/init.d/perf-tune)
> 在 START=99 重新应用一次，否则它们会毫无提示地不生效。

验证：

```sh
sysctl net.ipv4.tcp_congestion_control   # 应为 bbr
sysctl net.core.default_qdisc           # 应为 fq
sysctl net.netfilter.nf_conntrack_max    # 应为 262144
tc qdisc show                          # 查看接口实际队列；SQM 接口可为 cake
logread | grep perf-tune
```

AdGuardHome 工作目录改到了 `/srv/adguardhome-{direct,proxy}`。原先在
`/var/lib/...`，而 OpenWrt 的 `/var` 是指向 tmpfs 的软链接——意味着每次重启两个实例的
过滤规则全部重新下载，这段时间内 DNS 拦截不生效。放在 `/srv` 既持久化，又不会被
`sysupgrade -c` 把查询日志卷进备份包。

两个实例的新装默认查询日志保留期为 7 天，避免 90 天的日志长期占用 2 GiB 根分区。
保留配置升级会沿用已有 YAML；现有设备可在各自的 AdGuardHome 界面调整查询日志保留期。

## 检查流量卸载

流量卸载能显著提升纯转发吞吐，但会让已建立的连接走内核快速路径、绕过常规 netfilter 处理，
这与透明代理存在张力。若遇到「个别连接莫名走直连」，这是首要嫌疑：

```sh
uci get firewall.@defaults[0].flow_offloading
```
