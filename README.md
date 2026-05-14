# ImmortalWrt x86_64 云编译

基于 [ImmortalWrt](https://github.com/immortalwrt/immortalwrt) 项目构建的 x86_64 通用固件，支持 Hyper-V / VMware / 物理机启动。

## 默认参数

| 项目 | 默认值 |
|------|--------|
| **内核版本** | Linux 6.18 |
| **架构** | x86_64 (generic) |
| **默认 IP** | 192.168.1.1 |
| **默认账号** | root |
| **默认密码** | 无密码（首次登录需设置） |
| **文件格式** | ext4 + squashfs |
| **软件源** | 使用 ImmortalWrt 构建生成的 APK 源（不再额外覆盖为清华目录源） |
| **包管理** | APK |
| **链接器** | MOLD |

## 编译分支

| 分支 | 说明 |
|------|------|
| `master` | 最新开发版 |
| `openwrt-25.12` | 稳定版分支 |

## 已集成的 LUCI 插件

- `luci-app-lucky` — 断代转发 / Lucky 一键部署
- `luci-app-openclash` — Clash 客户端
- `luci-app-firewall` — 防火墙管理
- `luci-app-sqm` — 流量 QoS
- `luci-app-upnp` — UPnP 端口映射
- `luci-app-package-manager` — 在线包管理

## 主题

默认使用 `luci-theme-bootstrap`。

## 主要特性

- ✅ 使用构建生成的 APK 源，并移除 video 源以避免 `apk update` 因镜像同步不完整失败
- ✅ 预置 `/etc/config/fstab` 挂载配置，告别 block-mount 报错
- ✅ 关闭自动挂载扫描，避免 Hyper-V 虚拟磁盘识别错误
- ✅ 关闭独立 var 分区模式，单盘即可使用
- ✅ 签名包验证，安全加固
- ✅ MOLD 链接器，加速编译

## 使用方法

### 触发编译

GitHub → **Actions** → **OpenWrt Builder** → **Run workflow** → 选择分支（留空则同时编译 master 和 openwrt-25.12）

### 下载固件

编译完成后在对应 Release 中下载 `*-generic-squashfs-combined-efi.img.gz`，写入虚拟机或物理机即可。

### 写入参考命令

```bash
# 解压并写入虚拟机磁盘（请勿在生产环境执行！）
gunzip -c openwrt-*-generic-squashfs-combined-efi.img.gz | dd of=/dev/sda bs=4M status=progress
```

## 自定义配置

修改项目根目录下的 `.config` 文件，然后重新触发编译。

原始配置文件已备份在 `backup/.config`，修复版本为当前默认配置。

## 致谢

- [ImmortalWrt](https://github.com/immortalwrt/immortalwrt)
- [P3TERX/Actions-OpenWrt](https://github.com/P3TERX/Actions-OpenWrt)
