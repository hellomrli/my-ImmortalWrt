start_service() {
  [ -x "$BIN" ] && [ -f "$CONF" ] && [ -d "$WORK" ] || return 1
  procd_open_instance
  procd_set_param command /usr/libexec/adh-wait-start "$CONF" "$BIN" -c "$CONF" -w "$WORK" --no-check-update --logfile syslog
  procd_set_param user adguardhome
  procd_set_param group adguardhome
  procd_set_param capabilities /etc/capabilities/adguardhome.json
  procd_set_param no_new_privs 1
  procd_set_param respawn 3600 5 5
  procd_set_param limits nofile="65535 65535"
  procd_set_param stdout 1
  procd_set_param stderr 1
  procd_set_param file "$CONF" /usr/libexec/adh-wait-start
  procd_add_jail "${BIN##*/}" log procfs requirejail
  procd_add_jail_mount "$BIN" /usr/bin/AdGuardHome /bin/sh /bin/busybox /bin/sleep /usr/bin/awk /usr/bin/basename /usr/bin/logger /sbin/ip
  procd_add_jail_mount /etc/hosts /etc/ssl/certs /etc/ssl/cert.pem /etc/TZ /etc/localtime
  procd_add_jail_mount_rw "${CONF%/*}" "$WORK"
  procd_close_instance
}

reload_service() { stop; start; }
