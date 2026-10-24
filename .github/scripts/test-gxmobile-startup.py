#!/usr/bin/env python3
"""Exercise the real daemon entry point using a locally built scanner binary."""

import argparse
from contextlib import contextmanager
import fcntl
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.request


PARSER = argparse.ArgumentParser()
PARSER.add_argument("--binary", required=True, type=Path)
ARGS, TEST_ARGS = PARSER.parse_known_args()
BINARY = ARGS.binary.resolve()
PLAYLIST = "\u5e7f\u897f\u79fb\u52a8IPTV_\u53bb\u91cd\u7248.m3u"
REPORT = "\u626b\u63cf\u62a5\u544a.txt"


class StartupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.data = self.root / "data"
        self.data.mkdir()
        self.published = self.root / "www"
        self.baseline = self.data / "iptv_baseline.json"
        self.baseline.write_text(json.dumps({
            "updated": "2026-01-02T03:04:05Z", "gateway": "http://old.invalid:8080",
            "channels": [{"name": "Test", "group": "Group", "lastWinner": 1,
                          "sources": [{"cid": 1, "h": 1080, "kbps": 3}]}],
        }))
        (self.data / REPORT).write_text("previous report")
        self.command = [str(BINARY), "-web", "-out", str(self.data), "-publish", str(self.published)]
        self.http = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    @contextmanager
    def server(self, gateway):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            address = f"127.0.0.1:{sock.getsockname()[1]}"
        with tempfile.TemporaryFile() as log:
            process = subprocess.Popen(self.command + ["-addr", address, "-gateway", gateway],
                                       stdout=log, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        break
                    try:
                        with self.http.open(f"http://{address}/api/status", timeout=0.2):
                            break
                    except OSError:
                        time.sleep(0.02)
                else:
                    self.fail("daemon did not start within five seconds")
                if process.poll() is not None:
                    log.seek(0)
                    self.fail(f"daemon exited early: {log.read().decode()}")
                yield address
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)

    def test_restart_republishes_new_gateway_without_scanning(self):
        before = self.baseline.read_bytes()
        for gateway in ("http://old.invalid:8080", "http://new.invalid:8080"):
            with self.server(gateway) as address:
                for directory in (self.data, self.published):
                    text = (directory / PLAYLIST).read_text()
                    self.assertIn(f"\n{gateway}/1/index.m3u8?servicetype=1\n", text)
                    if "new.invalid" in gateway:
                        self.assertNotIn("old.invalid", text)
                    self.assertEqual((directory / REPORT).read_text(), "previous report")
                with self.http.open(f"http://{address}/api/channels", timeout=1) as response:
                    channels = json.load(response)
                self.assertTrue(channels[0]["url"].startswith(gateway + "/"))
                with self.http.open(f"http://{address}/api/status", timeout=1) as response:
                    status = json.load(response)
                self.assertFalse(status["running"])
                self.assertTrue(status["lastRun"].startswith("0001-"))
                self.assertEqual(self.baseline.read_bytes(), before)

    def test_startup_respects_existing_scan_lock(self):
        (self.data / PLAYLIST).write_text("keep existing playlist")
        with (self.data / ".scan.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = subprocess.run(self.command + ["-addr", "127.0.0.1:0"],
                                    capture_output=True, text=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.data / PLAYLIST).read_text(), "keep existing playlist")
        self.assertFalse(self.published.exists())


if __name__ == "__main__":
    unittest.main(argv=[__file__, *TEST_ARGS])
