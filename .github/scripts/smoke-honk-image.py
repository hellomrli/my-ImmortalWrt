#!/usr/bin/env python3
"""Boot a disposable, offline x86 guest and verify both supervised DNS instances."""

import argparse
from pathlib import Path
import sys

import pexpect


CHECK = r'''set -eu
check_role() {
    role="$1"; port="$2"; comm="$3"; other="$4"
    for proc in /proc/[0-9]*; do
        [ "$(cat "$proc/comm" 2>/dev/null)" = "$comm" ] || continue
        [ "$(awk '/^Uid:/{print $2}' "$proc/status")" = "$(id -u adguardhome)" ] || continue
        grep -Eq '^NoNewPrivs:[[:space:]]+1$' "$proc/status" || continue
        [ "$(readlink "$proc/ns/mnt")" != "$(readlink /proc/1/ns/mnt)" ] || continue
        [ -f "$proc/root/etc/adguardhome-$role/AdGuardHome.yaml" ] || continue
        [ ! -e "$proc/root/etc/adguardhome-$other/AdGuardHome.yaml" ] || continue
        netstat -ln | grep -Fq "127.0.0.1:$port " || continue
        return 0
    done
    return 1
}
ready=0
for attempt in $(seq 1 90); do
    if check_role direct 50530 AdGuardHome-dir proxy && check_role proxy 50531 AdGuardHome-pro direct; then ready=1; break; fi
    sleep 1
done
[ "$ready" = 1 ] || { logread | grep -Ei 'adh-|adguardhome|ujail' | tail -45; exit 1; }
[ "$(uci -q get 'dhcp.@dnsmasq[0].cachesize')" = 10000 ]
[ "$(uci -q get honk.main.enabled)" = 0 ]
cmp /etc/honk/config.dae /usr/share/honk/default-config.dae
for port in 50530 50531; do grep -Fq "'udp://127.0.0.1:$port' -> direct" /etc/honk/config.dae; done
runtime=$(honk-core config validate --config /etc/honk/config.dae)
[ "$(printf '%s' "$runtime" | jsonfilter -e '@.runtime.nfqueue_enable')" = true ]
for data in geoip geosite; do lua /usr/share/honk/check-geodata.lua "/usr/share/v2ray/$data.dat"; done
printf '\012\010\012\002CN\022\002\010\001' >/tmp/small-geo.dat
lua /usr/share/honk/check-geodata.lua /tmp/small-geo.dat
for bad in '\012\006\012\002CN\022\004' '\012\012\012\002CN\022\002\010\001\022\005' '<html>'; do
    printf '%b' "$bad" >/tmp/bad-geo.dat
    if lua /usr/share/honk/check-geodata.lua /tmp/bad-geo.dat; then exit 1; fi
done
for port in 50530 50531; do nslookup localhost "127.0.0.1:$port" >/dev/null; done
'''


def smoke(kernel, disk):
    machine = pexpect.spawn('qemu-system-x86_64', [
        '-nodefaults', '-machine', 'pc,accel=tcg', '-cpu', 'max', '-m', '768', '-smp', '2',
        '-display', 'none', '-monitor', 'none', '-serial', 'stdio', '-no-reboot',
        '-kernel', str(kernel), '-append', 'root=/dev/vda2 rootwait console=ttyS0,115200',
        '-drive', f'file={disk},format=raw,if=virtio,snapshot=on',
        '-netdev', 'user,id=lan,restrict=on', '-device', 'virtio-net-pci,netdev=lan,romfile=',
    ], encoding='utf-8', codec_errors='replace', timeout=180)
    try:
        machine.expect_exact('Please press Enter to activate this console')
        machine.sendline('')
        machine.expect(r'root@[^\r\n]*# ')
        machine.sendline("cat >/tmp/check-honk <<'END_CHECK'")
        for line in CHECK.splitlines():
            machine.sendline(line)
        machine.sendline('END_CHECK')
        machine.sendline('if sh /tmp/check-honk; then echo HONK_GUEST_PASS; else echo HONK_GUEST_FAIL; fi')
        if machine.expect([r'\nHONK_GUEST_PASS\r*\n', r'\nHONK_GUEST_FAIL\r*\n']) != 0:
            raise RuntimeError('Guest checks failed')
        print('Fresh Honk image: jailed, non-root ADH workers answered DNS; Honk defaults and geo assets passed.')
    except Exception:
        print((machine.before or '')[-8000:], file=sys.stderr)
        raise
    finally:
        machine.close(force=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kernel', type=Path)
    parser.add_argument('disk', type=Path)
    args = parser.parse_args()
    smoke(args.kernel, args.disk)
