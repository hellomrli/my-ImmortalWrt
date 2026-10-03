#!/usr/bin/env python3
"""Regression tests for the repository's dual-AdGuardHome template checks."""

import argparse
from copy import deepcopy
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml


SCRIPT = Path(__file__).with_name("check-adh-config.py")
spec = importlib.util.spec_from_file_location("check_adh_config", SCRIPT)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)
ETC_DIR = Path(__file__).resolve().parents[2] / "files/etc"


class AdhConfigTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.etc = Path(self.directory.name)
        self.configs = {
            role: yaml.safe_load((ETC_DIR / f"AdGuardHome-{role}.yaml").read_text())
            for role in ("direct", "proxy")
        }
        self.write_configs(self.configs)

    def write_configs(self, configs):
        for role, config in configs.items():
            (self.etc / f"AdGuardHome-{role}.yaml").write_text(yaml.safe_dump(config))

    def test_repository_templates(self):
        checker.check_configs(ETC_DIR)
        checker.check_configs(self.etc)

    def test_invalid_dns_fields(self):
        cases = [
            ("direct", "port", 50531),
            ("proxy", "port", "50531"),
            ("proxy", "bind_hosts", ["0.0.0.0", "::"]),
            ("direct", "upstream_dns", ["127.0.0.1:50531"]),
            ("direct", "fallback_dns", ["127.0.0.1:50531"]),
            ("direct", "fallback_dns", ["127.0.0.1:50530"]),
            ("proxy", "fallback_dns", ["127.0.0.1:50531"]),
            ("proxy", "fallback_dns", ["127.0.0.1:53"]),
            ("proxy", "fallback_dns", []),
            ("proxy", "fallback_dns", "127.0.0.1:50530"),
            ("proxy", "upstream_dns", ["8.8.8.8"]),
            ("proxy", "upstream_dns", []),
            ("proxy", "upstream_dns_file", "/etc/upstreams.txt"),
            ("proxy", "upstream_timeout", "10s"),
            ("direct", "upstream_timeout", 10),
            ("proxy", "upstream_mode", "load_balance"),
            ("direct", "aaaa_disabled", True),
            ("proxy", "aaaa_disabled", False),
            ("proxy", "aaaa_disabled", 1),
            ("proxy", "serve_plain_dns", False),
        ]
        for role, field, value in cases:
            with self.subTest(role=role, field=field, value=value):
                configs = deepcopy(self.configs)
                configs[role]["dns"][field] = value
                self.write_configs(configs)
                with self.assertRaisesRegex(RuntimeError, rf"dns\.{field}:"):
                    checker.check_configs(self.etc)

    def test_missing_field(self):
        del self.configs["proxy"]["dns"]["fallback_dns"]
        self.write_configs(self.configs)
        with self.assertRaisesRegex(RuntimeError, "dns.fallback_dns:"):
            checker.check_configs(self.etc)

    def test_wrong_document_shape(self):
        for value in (None, [], "dns", {}, {"dns": []}):
            with self.subTest(value=value):
                (self.etc / "AdGuardHome-proxy.yaml").write_text(yaml.safe_dump(value))
                with self.assertRaisesRegex(RuntimeError, "expected a dns mapping"):
                    checker.check_configs(self.etc)

    def test_unrelated_settings_are_not_rewritten(self):
        self.configs["proxy"]["user_rules"].append("@@||example.org^")
        self.write_configs(self.configs)
        path = self.etc / "AdGuardHome-proxy.yaml"
        before = path.read_bytes()
        checker.check_configs(self.etc)
        self.assertEqual(before, path.read_bytes())

    def test_cli_success(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("static configuration only", result.stdout)

    def test_cli_invalid_yaml(self):
        (self.etc / "AdGuardHome-proxy.yaml").write_text("dns: [\n")
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertIn("invalid YAML", result.stderr)
        self.assertIn("::error::", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_cli_missing_file(self):
        (self.etc / "AdGuardHome-proxy.yaml").unlink()
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertIn("AdGuardHome-proxy.yaml", result.stderr)
        self.assertIn("::error::", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def run_cli(self):
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(self.etc)],
            capture_output=True, text=True, check=False,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--etc-dir", type=Path, default=ETC_DIR)
    args, unittest_args = parser.parse_known_args()
    ETC_DIR = args.etc_dir
    unittest.main(argv=[sys.argv[0], *unittest_args])
