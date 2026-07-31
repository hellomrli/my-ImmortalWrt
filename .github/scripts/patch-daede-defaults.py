#!/usr/bin/env python3
"""Patch kenzok8/openwrt-daede defaults for this firmware profile.

The upstream package is cloned during every build.  Keep the local changes as
small, checked textual replacements so an upstream layout change fails loudly
instead of silently restoring incompatible DNS defaults.
"""

from pathlib import Path
import sys


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"expected exactly one patch target in {path}, found {count}"
        )
    path.write_text(text.replace(old, new), encoding="utf-8")


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} OPENWRT_DAEDE_DIR", file=sys.stderr)
        return 2

    root = Path(sys.argv[1])
    daede_config = root / "luci-app-daede/root/etc/config/daede"
    defaults = root / "luci-app-daede/root/etc/uci-defaults/90-luci-app-daede-init"
    generator = root / "luci-app-daede/root/usr/share/luci-app-daede/gen-dae-config.sh"
    view = root / "luci-app-daede/htdocs/luci-static/resources/view/daede/dae.js"

    for path in (daede_config, defaults, generator, view):
        if not path.is_file():
            raise RuntimeError(f"required upstream file is missing: {path}")

    replace_once(
        daede_config,
        "\toption active_backend 'daed'",
        "\toption active_backend 'dae'",
    )

    replace_once(
        defaults,
        """\tif [ -f /etc/init.d/daed ]; then
\t\tuci -q set daede.config.active_backend='daed'
\telse
\t\tuci -q set daede.config.active_backend='dae'
\tfi""",
        """\t# This firmware ships both backends, but its DNS profile and current
\t# production configuration are maintained by the standalone dae backend.
\tuci -q set daede.config.active_backend='dae'""",
    )
    replace_once(
        defaults,
        """\t\tuci -q set dae.dns.cn_upstream='udp://dns.alidns.com:53'
\t\tuci -q set dae.dns.fallback_upstream='tcp+udp://dns.google:53'""",
        """\t\tuci -q set dae.dns.cn_upstream='udp://127.0.0.1:50530'
\t\tuci -q set dae.dns.fallback_upstream='udp://127.0.0.1:50531'""",
    )

    replace_once(
        generator,
        """generate() {
\tconfig_load dae""",
        """generate() {
\t# The production router keeps routing/group policy that the simplified UCI
\t# form cannot represent.  Never destroy an unmanaged config on a form save.
\tif [ -s "$CONFIG_DAE" ] && \\
\t   ! grep -Fq '# 本配置由 luci-app-daede 表单自动生成，再次保存表单会覆盖你的手动修改。' "$CONFIG_DAE"; then
\t\techo "refusing to overwrite unmanaged $CONFIG_DAE; use the raw editor or migrate it explicitly" >&2
\t\treturn 1
\tfi

\tconfig_load dae""",
    )
    replace_once(
        generator,
        '''\tconfig_get cn_up dns cn_upstream "udp://dns.alidns.com:53"
\tconfig_get fb_up dns fallback_upstream "tcp+udp://dns.google:53"''',
        '''\tconfig_get cn_up dns cn_upstream "udp://127.0.0.1:50530"
\tconfig_get fb_up dns fallback_upstream "udp://127.0.0.1:50531"''',
    )
    replace_once(
        generator,
        '''\t\techo "dns {"
\t\techo "    ipversion_prefer: 4"
\t\t[ "$response_ttl" -gt 0 ] && echo "    response_ttl: ${response_ttl}"
\t\techo "    upstream {"
\t\techo "        cndns: '${cn_up}'"
\t\techo "        fallbackdns: '${fb_up}'"
\t\techo "    }"
\t\techo "    routing {"
\t\techo "        request {"
\t\t[ "$block_ads" = "1" ] && echo "            qname(geosite:category-ads-all) -> reject"
\t\techo "            qname(geosite:cn) -> cndns"
\t\techo "            fallback: fallbackdns"
\t\techo "        }"
\t\techo "    }"
\t\techo "}"''',
        '''\t\techo "dns {"
\t\t[ "$response_ttl" -gt 0 ] && echo "    response_ttl: ${response_ttl}"
\t\techo "    upstream {"
\t\techo "        adh_direct: '${cn_up}'"
\t\techo "        adh_proxy: '${fb_up}'"
\t\techo "    }"
\t\techo "    routing {"
\t\techo "        request {"
\t\t[ "$block_ads" = "1" ] && echo "            qname(geosite:category-ads-all) -> reject"
\t\techo "            qname(geosite:private) -> adh_direct"
\t\techo "            qname(geosite:cn) -> adh_direct"
\t\tfor suffix in cloudflare-dns.com dns.google dns.quad9.net dns.adguard-dns.com doh.opendns.com dns.sb doh.mullvad.net filters.adtidy.org big.oisd.nl urlhaus.abuse.ch; do
\t\t\techo "            qname(suffix:${suffix}) -> adh_direct"
\t\tdone
\t\techo "            fallback: adh_proxy"
\t\techo "        }"
\t\techo "        response {"
\t\techo "            fallback: accept"
\t\techo "        }"
\t\techo "    }"
\t\techo "}"''',
    )
    replace_once(
        generator,
        '''\t\techo "routing {"
\t\techo "    pname(NetworkManager) -> direct"''',
        '''\t\techo "routing {"
\t\t# dae matches a 16-byte argv name when supported and the 15-byte Linux
\t\t# comm fallback otherwise.  Keep both forms used by the running router.
\t\techo "    pname(odhcpd, odhcp6c, netifd, ntpd, uhttpd, dropbear) -> must_direct"
\t\techo "    pname(mosdns, smartdns) -> must_direct"
\t\techo "    pname(AdGuardHome-dir, AdGuardHome-dire) -> must_direct"
\t\techo "    pname(AdGuardHome-pro, AdGuardHome-prox) -> ${fallback}"
\t\techo "    pname(NetworkManager, systemd-resolved) -> must_direct"''',
    )

    replace_once(
        view,
        """\t'# luci-app-daede 默认配置：把 subscription 里的占位链接换成你的机场订阅，保存即可运行。\\n' +""",
        """\t'# 本配置由 luci-app-daede 表单自动生成，再次保存表单会覆盖你的手动修改。\\n' +
\t'# 把 subscription 里的占位链接换成你的机场订阅，保存即可运行。\\n' +""",
    )
    replace_once(
        view,
        """\t'dns {\\n' +
\t'    # 国内域名走 cndns 解析，其余走 fallbackdns，避免 DNS 污染。\\n' +
\t'    ipversion_prefer: 4\\n' +
\t'    response_ttl: 0\\n' +
\t'    upstream {\\n' +
\t\"        cndns: 'udp://dns.alidns.com:53'\\n\" +
\t\"        fallbackdns: 'tcp+udp://dns.google:53'\\n\" +
\t'    }\\n' +
\t'    routing {\\n' +
\t'        request {\\n' +
\t'            qname(geosite:cn) -> cndns\\n' +
\t'            fallback: fallbackdns\\n' +
\t'        }\\n' +
\t'    }\\n' +
\t'}\\n' +""",
        """\t'dns {\\n' +
\t'    response_ttl: 0\\n' +
\t'    upstream {\\n' +
\t\"        adh_direct: 'udp://127.0.0.1:50530'\\n\" +
\t\"        adh_proxy: 'udp://127.0.0.1:50531'\\n\" +
\t'    }\\n' +
\t'    routing {\\n' +
\t'        request {\\n' +
\t'            qname(geosite:private) -> adh_direct\\n' +
\t'            qname(geosite:cn) -> adh_direct\\n' +
\t'            qname(suffix:cloudflare-dns.com) -> adh_direct\\n' +
\t'            qname(suffix:dns.google) -> adh_direct\\n' +
\t'            qname(suffix:dns.quad9.net) -> adh_direct\\n' +
\t'            qname(suffix:dns.adguard-dns.com) -> adh_direct\\n' +
\t'            qname(suffix:doh.opendns.com) -> adh_direct\\n' +
\t'            qname(suffix:dns.sb) -> adh_direct\\n' +
\t'            qname(suffix:doh.mullvad.net) -> adh_direct\\n' +
\t'            qname(suffix:filters.adtidy.org) -> adh_direct\\n' +
\t'            qname(suffix:big.oisd.nl) -> adh_direct\\n' +
\t'            qname(suffix:urlhaus.abuse.ch) -> adh_direct\\n' +
\t'            fallback: adh_proxy\\n' +
\t'        }\\n' +
\t'        response {\\n' +
\t'            fallback: accept\\n' +
\t'        }\\n' +
\t'    }\\n' +
\t'}\\n' +""",
    )
    replace_once(
        view,
        """\t'routing {\\n' +
\t'    # 分流规则：从上往下匹配，命中即停，最后由 fallback 兜底。\\n' +
\t'    # 想让某个网站直连，在 fallback 之前加一行，例如：domain(example.com) -> direct\\n' +
\t'    pname(NetworkManager) -> direct\\n' +""",
        """\t'routing {\\n' +
\t'    pname(odhcpd, odhcp6c, netifd, ntpd, uhttpd, dropbear) -> must_direct\\n' +
\t'    pname(mosdns, smartdns) -> must_direct\\n' +
\t'    pname(AdGuardHome-dir, AdGuardHome-dire) -> must_direct\\n' +
\t'    pname(AdGuardHome-pro, AdGuardHome-prox) -> proxy\\n' +
\t'    pname(NetworkManager, systemd-resolved) -> must_direct\\n' +""",
    )
    replace_once(
        view,
        """\to.default = 'udp://dns.alidns.com:53';
\to.placeholder = 'udp://dns.alidns.com:53';""",
        """\to.default = 'udp://127.0.0.1:50530';
\to.placeholder = 'udp://127.0.0.1:50530';""",
    )
    replace_once(
        view,
        """\to.default = 'tcp+udp://dns.google:53';
\to.placeholder = 'tcp+udp://dns.google:53';""",
        """\to.default = 'udp://127.0.0.1:50531';
\to.placeholder = 'udp://127.0.0.1:50531';""",
    )

    print("Patched luci-app-daede defaults for dae + dual AdGuardHome.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
