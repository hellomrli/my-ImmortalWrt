#!/usr/bin/env python3
"""Validate the resolved IPTV config and installed firmware, without master assumptions."""
import argparse
import json
from pathlib import Path
import subprocess

REQUIRED = (
    'kmod-fs-f2fs', 'mkf2fs', 'f2fsck', 'openssh-sftp-server', 'qemu-ga',
    'kmod-tcp-bbr', 'kmod-sched', 'ppp-mod-pppoe', 'lucky', 'luci-app-lucky',
    'gxmobile-scan', 'luci-app-gxmobile', 'rpcd-mod-ucode', 'ucode-mod-fs',
    'ucode-mod-uci', 'curl', 'flock', 'kmod-r8125',
)
FORBIDDEN = ('dae', 'daed', 'luci-app-daede', 'adguardhome', 'samba4-server', 'avahi-dbus-daemon')


def check(tree: Path, manifest: Path | None = None) -> None:
    config = set((tree / '.config').read_text().splitlines())
    for package in REQUIRED:
        assert f'CONFIG_PACKAGE_{package}=y' in config, f'Missing selected package: {package}'
    for package in FORBIDDEN:
        assert f'CONFIG_PACKAGE_{package}=y' not in config, f'Unexpected package: {package}'
    assert not any(line.startswith(('CONFIG_PACKAGE_ruby', 'CONFIG_PACKAGE_libruby')) and line.endswith(('=y', '=m')) for line in config), 'Unexpected Ruby runtime'
    for line in ('CONFIG_TARGET_x86_64=y', 'CONFIG_IMAGEOPT=y', 'CONFIG_PREINITOPT=y',
                 'CONFIG_TARGET_PREINIT_IP="192.168.50.250"',
                 'CONFIG_TARGET_PREINIT_NETMASK="255.255.255.0"',
                 'CONFIG_TARGET_PREINIT_BROADCAST="192.168.50.255"'):
        assert line in config, f'Missing IPTV option: {line}'
    files = tree / 'files'
    for path in files.rglob('*'):
        assert 'AdGuardHome' not in path.name and 'adh-' not in path.name, f'Master overlay leaked: {path}'
    perf = (files / 'etc/sysctl.d/99-iptv-performance.conf').read_text()
    for setting in ('net.ipv4.tcp_congestion_control=bbr', 'net.core.default_qdisc=fq', 'net.netfilter.nf_conntrack_max=65536'):
        assert setting in perf, f'Missing performance setting: {setting}'
    keep = (files / 'lib/upgrade/keep.d/my-immortalwrt').read_text().splitlines()
    for path in ('/etc/config/gxmobile', '/etc/gxmobile', '/etc/config/lucky.daji', '/etc/crontabs/root'):
        assert path in keep, f'Missing upgrade retention: {path}'
    fstab = (files / 'etc/config/fstab').read_text()
    assert "option auto_mount '0'" in fstab and "option anon_mount '0'" in fstab
    assert "option device '/dev/sda1'" not in fstab, 'QEMU boot disk must not be hard-coded as sda'
    ppp = (tree / 'package/network/services/ppp/files/ppp.sh').read_text()
    assert '[ "$(uci get syncdial.config.enabled)" -eq "1" ]' not in ppp
    assert 'CONFIG_GOLANG_EXTERNAL_BOOTSTRAP_ROOT=' in '\n'.join(config)
    for root in (files, tree / 'package/gxmobile-scan/root'):
        for path in root.rglob('*'):
            if path.is_file() and path.read_bytes().startswith(b'#!/bin/sh'):
                assert path.stat().st_mode & 0o111, f'Script is not executable: {path}'
                subprocess.run(['sh', '-n', str(path)], check=True)
    for path in (tree / 'package/luci-app-gxmobile/root').rglob('*.json'):
        json.loads(path.read_text())
    if manifest:
        packages = {line.split()[0] for line in manifest.read_text().splitlines() if line.strip()}
        assert set(REQUIRED) <= packages, f'Missing firmware packages: {set(REQUIRED) - packages}'
        assert not set(FORBIDDEN) & packages, f'Unexpected firmware packages: {set(FORBIDDEN) & packages}'
    print('IPTV profile validated: recovery address, packages, overlay, BBR/fq and backups.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tree', type=Path)
    parser.add_argument('--manifest', type=Path)
    args = parser.parse_args()
    check(args.tree, args.manifest)
