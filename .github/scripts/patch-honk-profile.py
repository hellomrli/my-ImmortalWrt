#!/usr/bin/env python3
"""Adapt only the staged Honk package and new-install dnsmasq defaults."""

from pathlib import Path
import re
import shutil
import sys


def replace(path, old, new):
    text = path.read_text()
    if text.count(old) != 1:
        raise ValueError(f"Upstream changed {path}: expected one {old.splitlines()[0]!r}; review the Honk integration")
    path.write_text(text.replace(old, new))


def patch(tree):
    core = tree / 'package/honk/honk'
    template = core / 'files/config.dae'
    replace(template, "'https://223.5.5.5/dns-query?tls_server_name=dns.alidns.com' -> direct", "'udp://127.0.0.1:50530' -> direct")
    replace(template, "'https://8.8.8.8/dns-query?tls_server_name=dns.google' -> proxy", "'udp://127.0.0.1:50531' -> direct")
    replace(template, 'qname(geosite: private) -> local', 'qname(geosite: private, suffix: lan) -> local')
    replace(template, 'qname(geosite: private) -> accept', 'upstream(local) -> accept')
    replace(template, '    pname(AdGuardHome, mosdns,',
            "    pname(AdGuardHome-pro) && dip(127.0.0.0/8, '::1') -> direct(must)\n"
            '    pname(AdGuardHome-pro) && dport(443) -> proxy\n    pname(AdGuardHome, mosdns,')
    replace(template, 'geosite: apple-cn', 'geosite: apple@cn')

    makefile = core / 'Makefile'
    luci = tree / 'package/honk/luci-app-honk'
    for package in (makefile, luci / 'Makefile'):
        replace(package, '\nPKG_RELEASE:=1\n', '\nPKG_RELEASE:=2\n')
    replace(makefile, '+coreutils-stat +v2ray-geoip', '+coreutils-stat +lua +v2ray-geoip')
    install = '\t$(INSTALL_BIN) $(CURDIR)/files/control.sh $(1)/usr/share/honk/control.sh'
    replace(makefile, install, install + '\n\t$(INSTALL_DATA) $(CURDIR)/files/check-geodata.lua $(1)/usr/share/honk/check-geodata.lua')
    shutil.copyfile(Path(__file__).with_name('check-geodata.lua'), core / 'files/check-geodata.lua')
    replace(core / 'files/control.sh', '''		_geo_size=$(wc -c < "$_geo_path" 2>/dev/null || echo 0)
		case "$_geo_size" in ''|*[!0-9]*) _geo_size=0 ;; esac
		if [ "$_geo_size" -lt 4194304 ]; then''',
            '\t\tif ! lua /usr/share/honk/check-geodata.lua "$_geo_path"; then')
    for option, asset in [('geoip', 'geoip/releases/latest/download/geoip.dat'),
                          ('geosite', 'domain-list-community/releases/latest/download/dlc.dat')]:
        replace(core / 'files/honk.config', f"option {option}_url ''", f"option {option}_url 'https://github.com/v2fly/{asset}'")
    updater = luci / 'root/usr/share/luci-app-honk/update-geo.sh'
    replace(updater, '''		magic=$(hexdump -n 1 -e '1/1 "%02x"' "$TMP" 2>/dev/null)
		if [ "$size" -lt 4194304 ]; then
			echo "$(date '+%F %T') file too small ($size bytes)"
			rm -f "$TMP"
			rc=2
		elif [ "$magic" != "0a" ]; then''',
            '\t\tif ! lua /usr/share/honk/check-geodata.lua "$TMP"; then')
    translation = luci / 'po/zh-cn/honk.po'
    for path in (translation, luci / 'htdocs/luci-static/resources/view/honk/rpc.js'):
        replace(path, 'data file is incomplete (under 4 MiB)', 'data file has invalid or truncated records')
    replace(translation, '数据文件不完整（小于 4 MiB）', '数据文件格式不正确或内容不完整')

    dhcp = tree / 'package/network/services/dnsmasq/files/dhcp.conf'
    text, count = re.subn(r'(?m)^([ \t]*option[ \t]+cachesize[ \t]+)\d+[ \t]*$', r'\g<1>10000', dhcp.read_text())
    if count != 1:
        raise ValueError(f'Expected exactly one dnsmasq cache default in {dhcp}')
    dhcp.write_text(text)


if __name__ == '__main__':
    patch(Path(sys.argv[1]))
