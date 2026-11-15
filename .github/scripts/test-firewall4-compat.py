#!/usr/bin/env python3
"""Reproduce the firewall4 patch failure and exercise both build profiles."""

import importlib.util
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / ".github/scripts/patch-firewall4-compat.py"
spec = importlib.util.spec_from_file_location("firewall4_compat", HELPER)
compat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compat)

# Configuration hunk from ImmortalWrt a4ba8240, with a second file to ensure
# the refresh preserves patch content unrelated to the obsolete comments.
PATCH = (
    "--- a/root/etc/config/firewall\n"
    "+++ b/root/etc/config/firewall\n"
    "@@ -5,6 +5,10 @@ config defaults\n"
    " \toption forward\t\tREJECT\n"
    " # Uncomment this line to disable ipv6 rules\n"
    " #\toption disable_ipv6\t1\n"
    "+\toption flow_offloading\t1\n"
    "+\toption flow_offloading_hw\t1\n"
    "+\toption fullcone\t\t1\n"
    "+\toption fullcone6\t0\n"
    " \n"
    " config zone\n"
    " \toption name\t\tlan\n"
    "--- a/root/usr/share/ucode/fw4.uc\n"
    "+++ b/root/usr/share/ucode/fw4.uc\n"
    "@@ -1,2 +1,3 @@\n"
    "+// FullCone fixture\n"
    ' const fs = require("fs");\n'
    ' const uci = require("uci");\n'
)
CONFIG = """config defaults
\toption syn_flood\t1
\toption input\t\tREJECT
\toption output\t\tACCEPT
\toption forward\t\tREJECT

config zone
\toption name\t\tlan
"""
FW4 = 'const fs = require("fs");\nconst uci = require("uci");\n'


class Firewall4CompatTests(unittest.TestCase):
    def stage(self, tree, *, version="3722eadc088c3ab81389596ca9796112b436583a", contents=PATCH):
        package = tree / "package/network/config/firewall4"
        patches = package / "patches"
        patches.mkdir(parents=True)
        (package / "Makefile").write_text(f"PKG_SOURCE_VERSION:={version}\n")
        path = patches / "001-firewall4-add-support-for-fullcone-nat.patch"
        path.write_text(contents)
        for name, text in (("root/etc/config/firewall", CONFIG), ("root/usr/share/ucode/fw4.uc", FW4)):
            source = tree / name
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(text)
        return path

    def apply(self, tree, path, *, dry_run=False):
        command = ["patch", "-p1", "--batch", "--fuzz=0", "-i", str(path)]
        if dry_run:
            command.append("--dry-run")
        return subprocess.run(command, cwd=tree, text=True, capture_output=True, timeout=10)

    def test_refresh_resolves_real_patch_failure_and_preserves_other_hunks(self):
        with tempfile.TemporaryDirectory() as directory:
            tree = Path(directory)
            path = self.stage(tree)
            failed = self.apply(tree, path, dry_run=True)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("Hunk #1 FAILED at 5", failed.stdout)
            self.assertTrue(compat.patch(tree))
            self.assertEqual(path.read_text().split("--- a/root/usr/share/ucode/fw4.uc", 1)[1],
                             PATCH.split("--- a/root/usr/share/ucode/fw4.uc", 1)[1])
            applied = self.apply(tree, path)
            self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
            config = (tree / "root/etc/config/firewall").read_text()
            for option in ("flow_offloading\t1", "flow_offloading_hw\t1", "fullcone\t\t1", "fullcone6\t0"):
                self.assertEqual(config.splitlines().count("\toption " + option), 1)
            self.assertEqual((tree / "root/usr/share/ucode/fw4.uc").read_text(), "// FullCone fixture\n" + FW4)
            self.assertFalse(list(tree.rglob("*.rej")))
            contents = path.read_bytes()
            modified = path.stat().st_mtime_ns
            self.assertFalse(compat.patch(tree))
            self.assertEqual(path.read_bytes(), contents)
            self.assertEqual(path.stat().st_mtime_ns, modified)

    def test_other_source_revisions_keep_the_upstream_patch(self):
        with tempfile.TemporaryDirectory() as directory:
            tree = Path(directory)
            path = self.stage(tree, version="different-source-revision")
            self.assertFalse(compat.patch(tree))
            self.assertEqual(path.read_text(), PATCH)

    def test_upstream_refresh_and_removal_need_no_workaround(self):
        refreshed = """--- a/root/etc/config/firewall
+++ b/root/etc/config/firewall
@@ -3,3 +3,5 @@ config defaults
 \toption input\t\tREJECT
 \toption output\t\tACCEPT
 \toption forward\t\tREJECT
+\toption fullcone\t\t1
+\toption fullcone6\t0
"""
        with tempfile.TemporaryDirectory() as directory:
            tree = Path(directory)
            path = self.stage(tree, contents=refreshed)
            self.assertFalse(compat.patch(tree))
            self.assertEqual(path.read_text(), refreshed)
            path.unlink()
            self.assertFalse(compat.patch(tree))
            self.assertFalse(path.exists())

    def test_unrecognized_stale_hunks_fail_without_modification(self):
        changed = PATCH.replace("fullcone\t\t1", "fullcone\t\t0")
        for contents in (changed, PATCH + PATCH, PATCH + changed):
            with self.subTest(contents=contents), tempfile.TemporaryDirectory() as directory:
                tree = Path(directory)
                path = self.stage(tree, contents=contents)
                result = subprocess.run([sys.executable, str(HELPER), str(tree)],
                                        text=True, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 1)
                self.assertIn("Unrecognized stale configuration hunk", result.stderr)
                self.assertEqual(path.read_text(), contents)

    def test_missing_source_version_fails_before_modifying_patches(self):
        with tempfile.TemporaryDirectory() as directory:
            tree = Path(directory)
            path = self.stage(tree)
            (path.parent.parent / "Makefile").write_text("PKG_NAME:=firewall4\n")
            with self.assertRaisesRegex(RuntimeError, "Cannot read the firewall4 source version"):
                compat.patch(tree)
            self.assertEqual(path.read_text(), PATCH)

    def test_both_diy_profiles_refresh_firewall4_before_fetching_packages(self):
        for script in ("diy-part2-honk.sh", "diy-part2-iptv.sh"):
            with self.subTest(script=script), tempfile.TemporaryDirectory() as directory:
                tree = Path(directory)
                path = self.stage(tree)
                fixtures = {
                    "package/base-files/files/bin/config_generate": "192.168.1.1\n",
                    "package/network/services/ppp/files/ppp.sh": "#!/bin/sh\n",
                    "feeds/packages/net/miniupnpd/Makefile": "PKG_VERSION:=2.3.12\n",
                }
                for name, text in fixtures.items():
                    target = tree / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(text)
                commands = tree / "commands"
                commands.mkdir()
                python = commands / "python3"
                python.write_text('#!/bin/sh\ncase "$1" in */fetch-packages.py) exit 73 ;; esac\n'
                                  f'exec {shlex.quote(sys.executable)} "$@"\n')
                python.chmod(0o755)
                env = dict(os.environ, PATH=str(commands) + os.pathsep + os.environ["PATH"])
                result = subprocess.run(["bash", str(ROOT / script)], cwd=tree, env=env,
                                        text=True, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 73, result.stdout + result.stderr)
                applied = self.apply(tree, path, dry_run=True)
                self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)


if __name__ == "__main__":
    unittest.main()
