#!/usr/bin/env python3
"""IPTV-only release notes; keep the original master release text unchanged."""
from datetime import datetime
import os
from pathlib import Path

print(f"""ImmortalWrt x86_64 IPTV 专用固件

构建目标：`iptv`；上游：ImmortalWrt 最新 `master`。
上游 commit：`{os.environ.get('SOURCE_SHA', 'unknown')}`。
构建时间：{datetime.now().astimezone().isoformat(timespec='seconds')}。

- 管理 / 恢复地址：`192.168.50.250`；主机名：`ImmortalWrt-IPTV`。
- Lucky HTTP/HLS 转发、PPPoE、`luci-app-gxmobile` 手动 / 定时扫描。
- BBR + fq、按需 TCP 缓冲、64K conntrack、QEMU Guest Agent、SFTP。
- 保留配置升级时保存拨号配置、Lucky 规则、频道基线及扫描计划。
- 全新安装需设置 root 密码、填写 IPTV 拨号账号并启用 WAN 自动连接、配置或恢复 Lucky 规则；固件不含私有凭据。
- LAN 不提供 DHCP / RA；无 dae / daed / AdGuardHome / Samba 服务。

推荐 `squashfs-combined-efi.img.gz`（Legacy BIOS 使用 `squashfs-combined.img.gz`）。
升级前用 `my-sysupgrade-backup` 或文档里的旧固件兼容步骤备份，并将备份复制到电脑。
内核模块仅适用于此镜像配套内核，不要安装到旧内核上。

[IPTV 部署与升级说明](https://github.com/hellomrli/my-ImmortalWrt/blob/main/docs/iptv.md)
""")
provenance = Path('openwrt/package-provenance.txt')
if provenance.exists():
    print('第三方包来源：\n\n```\n' + provenance.read_text() + '\n```')
