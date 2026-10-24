#!/usr/bin/env python3
"""Keep active targets, build references and documentation links consistent."""

import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from urllib.parse import unquote, urlsplit

import yaml


ROOT = Path(__file__).resolve().parents[2]
RETIRED = (
    ".github/packages.json", ".github/scripts/pin-daede-source.py",
    "configs/immortalwrt.config", "diy-part2-daed.sh",
    ".github/scripts/patch-test-feed-compat.py",
    "packages/gxmobile-scan/src/console_windows.go",
    "packages/gxmobile-scan/src/console_other.go",
)


class RepositoryLayoutTests(unittest.TestCase):
    def test_target_files_and_package_manifests_exist(self):
        targets = json.loads((ROOT / ".github/targets.json").read_text())["targets"]
        self.assertEqual({target["branch"] for target in targets}, {"master", "iptv"})
        for target in targets:
            with self.subTest(target=target["branch"]):
                for key in ("config_file", "diy_p1_sh", "diy_p2_sh"):
                    self.assertTrue((ROOT / target[key]).is_file(), target[key])
                self.assertTrue((ROOT / target.get("files_dir", "files")).is_dir())
                script = (ROOT / target["diy_p2_sh"]).read_text()
                manifests = re.findall(r'--config "\$repo_root/([A-Za-z0-9_./-]+)"', script)
                self.assertEqual(len(manifests), 1)
                manifest = json.loads((ROOT / manifests[0]).read_text())
                self.assertTrue(manifest["mirror"]["repo"])
                self.assertTrue(manifest["packages"])

    def test_diy_and_workflow_script_references_resolve(self):
        scripts = list(ROOT.glob("diy-*.sh"))
        workflows = list((ROOT / ".github/workflows").glob("*.yml"))
        for path in scripts + workflows:
            text = path.read_text()
            references = re.findall(r'"\$repo_root/([A-Za-z0-9_./-]+)"', text)
            references += re.findall(r'\.github/scripts/[A-Za-z0-9_.-]+\.(?:py|js)', text)
            for reference in references:
                with self.subTest(file=str(path.relative_to(ROOT)), reference=reference):
                    self.assertTrue((ROOT / reference).is_file())

    def test_retired_files_are_absent_and_not_used_by_build_code(self):
        active = [ROOT / "README.md", *ROOT.glob("diy-*.sh"),
                  *(ROOT / ".github").glob("*.json"),
                  *(ROOT / ".github/workflows").glob("*.yml"),
                  *(ROOT / ".github/scripts").glob("*.py")]
        for retired in RETIRED:
            self.assertFalse((ROOT / retired).exists(), retired)
            for path in active:
                if path.resolve() == Path(__file__).resolve():
                    continue
                with self.subTest(retired=retired, file=str(path.relative_to(ROOT))):
                    self.assertNotIn(retired, path.read_text())

    def test_local_documentation_links_resolve(self):
        documents = [ROOT / "README.md", ROOT / "CHANGELOG.md",
                     *(ROOT / "docs").rglob("*.md"),
                     *(ROOT / "packages").rglob("README.md")]
        for document in documents:
            for href in re.findall(r'\]\(([^\s)]+)\)', document.read_text()):
                link = urlsplit(href)
                if link.scheme or link.netloc or not link.path:
                    continue
                target = (document.parent / unquote(link.path)).resolve()
                with self.subTest(document=str(document.relative_to(ROOT)), href=href):
                    self.assertTrue(target.is_relative_to(ROOT))
                    self.assertTrue(target.exists(), target)

    def test_honk_release_links_keep_the_old_entry_point(self):
        legacy = (ROOT / "docs/honk-test.md").read_text()
        self.assertIn("](honk.md)", legacy)
        workflow = yaml.safe_load((ROOT / ".github/workflows/openwrt-builder.yml").read_text())
        steps = {step["name"]: step for step in workflow["jobs"]["build"]["steps"]}
        self.assertIn("docs/honk.md", steps["Generate release tag"]["run"])
        self.assertIn("test-repository-layout.py", steps["Test build helpers"]["run"])
        for name in ("Download package", "Organize files", "Generate release tag"):
            self.assertNotIn("kenzok8/openwrt-daede", steps[name]["run"])

    def test_retired_proxy_data_still_has_upgrade_retention(self):
        keep = (ROOT / "files/lib/upgrade/keep.d/my-immortalwrt").read_text().splitlines()
        for path in ("/etc/config/dae", "/etc/config/daed", "/etc/config/daede", "/etc/dae", "/etc/daed"):
            self.assertIn(path, keep)

    def test_release_notes_cover_both_targets_and_reject_unknown_profiles(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/openwrt-builder.yml").read_text())
        script = next(step["run"] for step in workflow["jobs"]["build"]["steps"]
                      if step["name"] == "Generate release tag")
        for branch, profile, document in (("master", "honk", "honk.md"),
                                          ("iptv", "", "iptv.md"),
                                          ("unsupported", "", None)):
            with self.subTest(branch=branch), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "output"
                command = script.replace("${{ matrix.source }}", "immortalwrt")
                command = command.replace("${{ matrix.branch }}", branch).replace("${{ matrix.profile }}", profile)
                env = dict(os.environ, GITHUB_WORKSPACE=str(ROOT), GITHUB_OUTPUT=str(output))
                result = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", command],
                                        cwd=directory, env=env, text=True, capture_output=True, timeout=10)
                if document is None:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn("status=success", output.read_text())
                else:
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn(f"release_tag=immortalwrt-{branch}-", output.read_text())
                    self.assertIn("status=success", output.read_text())
                    self.assertIn(f"/docs/{document}", (Path(directory) / "release.txt").read_text())


if __name__ == "__main__":
    unittest.main()
