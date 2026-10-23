#!/usr/bin/env python3
"""Test the supervised ADH startup gate without changing network interfaces."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "files/usr/libexec/adh-wait-start"


class AdhStartTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.bin = self.directory / "bin"
        self.bin.mkdir()
        self.env = {**os.environ, "TEST_DIR": str(self.directory)}
        self.env["PATH"] = f"{self.bin}:{os.environ['PATH']}"
        self.script("ip", 'cat "$TEST_DIR/addresses"')
        self.script("logger", 'echo "$*" >> "$TEST_DIR/messages"')
        self.script("sleep", '''
echo wait >> "$TEST_DIR/waits"
if [ -e "$TEST_DIR/fail-if-started" ]; then
  test ! -e "$TEST_DIR/started" || exit 99
fi
cp "$TEST_DIR/ready-addresses" "$TEST_DIR/addresses"
''')
        self.script("daemon", 'printf "%s\\n" "$@" > "$TEST_DIR/started"')

    def script(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/sh\nset -eu\n" + body + "\n")
        path.chmod(0o755)

    def run_gate(self, address, addresses="", ready_addresses=None):
        conf = self.directory / "config.yaml"
        conf.write_text(f"http:\n  address: {address}\ndns:\n  port: 50530\n")
        (self.directory / "addresses").write_text(addresses)
        if ready_addresses is not None:
            (self.directory / "ready-addresses").write_text(ready_addresses)
        result = subprocess.run(
            ["sh", str(HELPER), str(conf), str(self.bin / "daemon"),
             "-c", str(conf), "argument with spaces"],
            env=self.env, capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            (self.directory / "started").read_text().splitlines(),
            ["-c", str(conf), "argument with spaces"],
        )

    def test_assigned_ipv4_starts_immediately(self):
        self.run_gate("192.168.50.1:50080", "8: br-lan inet 192.168.50.1/24 scope global\n")
        self.assertFalse((self.directory / "waits").exists())

    def test_unassigned_ipv4_waits_before_exec(self):
        (self.directory / "fail-if-started").touch()
        self.run_gate(
            "192.168.50.1:50080", "1: lo inet 127.0.0.1/8 scope host\n",
            "8: br-lan inet 192.168.50.1/24 scope global\n",
        )
        self.assertEqual((self.directory / "waits").read_text(), "wait\n")
        self.assertIn("waiting for web bind address 192.168.50.1",
                      (self.directory / "messages").read_text())

    def test_ipv6_dad_must_complete(self):
        self.run_gate(
            '"[fd00:50::1]:50080"',
            "8: br-lan inet6 fd00:50::1/64 scope global tentative\n",
            "8: br-lan inet6 fd00:50::1/64 scope global\n",
        )
        self.assertTrue((self.directory / "waits").exists())

    def test_quoted_ipv4_with_comment(self):
        self.run_gate("'192.168.50.1:50081' # admin", "8: br-lan inet 192.168.50.1/24 scope global\n")
        self.assertFalse((self.directory / "waits").exists())

    def test_wildcard_ipv4_does_not_wait(self):
        self.run_gate("0.0.0.0:50080")
        self.assertFalse((self.directory / "waits").exists())

    def test_wildcard_ipv6_does_not_wait(self):
        self.run_gate("'[::]:50080'")
        self.assertFalse((self.directory / "waits").exists())

    def test_loopback_binding_does_not_require_lan(self):
        self.run_gate("127.0.0.1:50080", "1: lo inet 127.0.0.1/8 scope host\n")
        self.assertFalse((self.directory / "waits").exists())


if __name__ == "__main__":
    unittest.main()
