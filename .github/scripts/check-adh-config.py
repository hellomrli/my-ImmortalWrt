#!/usr/bin/env python3
"""Check the repository's dual-AdGuardHome DNS defaults, not retained user configs."""

import argparse
from pathlib import Path
import sys

import yaml


COMMON_DNS = {
    "bind_hosts": ["127.0.0.1", "::1"],
    "upstream_dns_file": "",
    "upstream_mode": "parallel",
    "serve_plain_dns": True,
}
PROFILES = {
    "direct": {
        "port": 50530,
        "upstream_dns": [
            "221.7.128.68",
            "221.7.136.68",
            "2408:8001:4000:9000:221:7:128:68",
            "2408:8001:4010:9000:221:7:136:68",
        ],
        "fallback_dns": [],
        "upstream_timeout": "10s",
        "aaaa_disabled": False,
    },
    "proxy": {
        "port": 50531,
        "upstream_dns": [
            "https://1.1.1.1/dns-query",
            "https://1.0.0.1/dns-query",
            "https://8.8.8.8/dns-query",
            "https://8.8.4.4/dns-query",
        ],
        "fallback_dns": ["127.0.0.1:50530"],
        "upstream_timeout": "3s",
        "aaaa_disabled": True,
    },
}


def check_configs(etc_dir: Path) -> None:
    # Together these defaults prevent a template-level proxy -> direct -> proxy
    # loop. Actual daed process routing still needs a separate runtime test.
    for role, profile in PROFILES.items():
        path = etc_dir / f"AdGuardHome-{role}.yaml"
        try:
            config = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise RuntimeError(f"{path}: invalid YAML: {exc}") from exc
        if not isinstance(config, dict) or not isinstance(config.get("dns"), dict):
            raise RuntimeError(f"{path}: expected a dns mapping")
        dns = config["dns"]
        for field, expected in {**COMMON_DNS, **profile}.items():
            actual = dns.get(field)
            # bool is an int subclass; do not accept 0/1 for YAML booleans.
            if type(actual) is not type(expected) or actual != expected:
                raise RuntimeError(
                    f"{path}: dns.{field}: expected {expected!r}, got {actual!r}"
                )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("etc_dir", type=Path, help="Overlay etc directory")
    args = parser.parse_args()
    check_configs(args.etc_dir)
    print("Dual-AdGuardHome DNS defaults verified (static configuration only).")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        raise SystemExit(1)
