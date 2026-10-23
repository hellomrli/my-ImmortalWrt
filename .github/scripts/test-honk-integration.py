#!/usr/bin/env python3
"""Regression tests for the isolated Honk test firmware and its release gates."""

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT / ".github/scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


profile = load("check-honk-profile")
source = load("fetch-honk-source")
kernel = load("export-kernel-config")
compat = load("patch-test-feed-compat")


class HonkTests(unittest.TestCase):
    def stage(self, tree):
        shutil.copytree(ROOT / "files", tree / "files", symlinks=True)
        with (tree / "files/lib/upgrade/keep.d/my-immortalwrt").open("a") as handle:
            handle.write("/etc/config/honk\n/etc/honk\n")
        for name in ("honk", "luci-app-honk"):
            path = tree / "package/honk" / name / "Makefile"
            path.parent.mkdir(parents=True)
            path.write_text(f"PKG_NAME:={name}\nPKG_VERSION:=2026.10.16\nPKG_RELEASE:=1\n")
        config = (ROOT / "configs/honk.config").read_text()
        config += "\n" + "".join(f"CONFIG_PACKAGE_{name}=y\n" for name in profile.REQUIRED
                                  if f"CONFIG_PACKAGE_{name}=y" not in config.splitlines())
        config += "\nCONFIG_PACKAGE_dnsmasq-full=y\n"
        (tree / ".config").write_text(config)
        packages = list(profile.REQUIRED) + ["dnsmasq-full"]
        manifest = tree / "firmware.manifest"
        manifest.write_text("".join(f"{name} - 2026.10.16-r1\n" for name in packages))
        return manifest

    def organize(self, directory, *, missing=None, per_feed=True):
        tree = directory / "openwrt"
        tree.mkdir()
        manifest = self.stage(tree)
        target = tree / "bin/targets/x86/64"
        target.mkdir(parents=True)
        manifest.rename(target / "immortalwrt-x86-64-generic.manifest")
        image = target / "immortalwrt-x86-64-generic-squashfs-combined.img.gz"
        image.write_bytes(b"test firmware image")
        (target / "sha256sums").write_text(f"{hashlib.sha256(image.read_bytes()).hexdigest()} *{image.name}\n")
        packages = {}
        for name in ("honk", "luci-app-honk", "kmod-nft-queue", "kmod-nfnetlink-queue"):
            repository = target / "packages"
            if per_feed and not name.startswith("kmod-"):
                repository = tree / "bin/packages/x86_64/honk"
            repository.mkdir(parents=True, exist_ok=True)
            filename = f"{name}-2026.10.16-r1.apk"
            contents = f"fixture for {name}\n".encode()
            packages[filename] = contents
            if name != missing:
                (repository / filename).write_bytes(contents)
        config = tree / "build_dir/target-x86_64/linux-x86_64/linux-6.18/.config"
        config.parent.mkdir(parents=True)
        config.write_text("".join(f"CONFIG_{name}=y\n" for name in (
            "X86_64", "BPF_SYSCALL", "CGROUP_BPF", "DEBUG_INFO_BTF", "NETKIT",
            "XDP_SOCKETS", "NET_SCH_FQ", "TCP_CONG_BBR", "NFT_QUEUE", "NETFILTER_NETLINK_QUEUE")))
        workflow = yaml.safe_load((ROOT / ".github/workflows/openwrt-builder.yml").read_text())
        script = next(step["run"] for step in workflow["jobs"]["build"]["steps"]
                      if step["name"] == "Organize files")
        script = script.replace("${{ matrix.profile }}", "honk").replace("${{ matrix.branch }}", "master").replace("${{ matrix.source }}", "immortalwrt")
        env = dict(os.environ, GITHUB_WORKSPACE=str(ROOT), GITHUB_ENV=str(directory / "github-env"),
                   GITHUB_OUTPUT=str(directory / "github-output"))
        result = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", script], cwd=directory,
                                env=env, text=True, capture_output=True, timeout=30)
        return result, target, packages

    def test_organize_collects_target_and_feed_apks(self):
        for per_feed in (True, False):
            with self.subTest(per_feed=per_feed), tempfile.TemporaryDirectory() as directory:
                result, target, packages = self.organize(Path(directory), per_feed=per_feed)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                for filename, contents in packages.items():
                    self.assertEqual((target / filename).read_bytes(), contents)
                checksums = subprocess.run(["sha256sum", "-c", "sha256sums"], cwd=target,
                                           text=True, capture_output=True, timeout=10)
                self.assertEqual(checksums.returncode, 0, checksums.stdout + checksums.stderr)
                self.assertEqual(len((target / "sha256sums").read_text().splitlines()), 5)
                self.assertFalse((target / "packages").exists())
                self.assertIn("CONFIG_NFT_QUEUE=y", (target / "immortalwrt-master_kernel.config").read_text())
                self.assertIn("status=success", (Path(directory) / "github-output").read_text())

    def test_organize_rejects_missing_nfqueue_apks(self):
        for missing in ("kmod-nft-queue", "kmod-nfnetlink-queue"):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as directory:
                result, target, _ = self.organize(Path(directory), missing=missing)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f"::error::No installable APK for {missing}", result.stdout)
                self.assertFalse((Path(directory) / "github-output").exists())
                self.assertTrue((target / "packages").is_dir())

    def test_profile_and_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            tree = Path(directory)
            manifest = self.stage(tree)
            profile.check(tree, manifest)
            config = tree / ".config"
            original = config.read_text()
            for package in ("kmod-nft-queue", "kmod-nfnetlink-queue", "honk", "adguardhome"):
                with self.subTest(missing=package):
                    config.write_text(original.replace(f"CONFIG_PACKAGE_{package}=y", f"# CONFIG_PACKAGE_{package} is not set"))
                    with self.assertRaises(RuntimeError):
                        profile.check(tree)
            config.write_text(original)
            for name in ("dae", "daed", "luci-app-daede", "daed-geosite", "luci-app-daede_dae"):
                config.write_text(original + f"CONFIG_PACKAGE_{name}=m\n")
                with self.assertRaises(RuntimeError):
                    profile.check(tree)
            config.write_text(original)
            original_manifest = manifest.read_text()
            for contents in (original_manifest + "daed - 1-r1\n",
                             original_manifest.replace("kmod-nft-queue - 2026.10.16-r1\n", ""),
                             original_manifest.replace("honk - 2026.10.16-r1", "honk - 2026.10.16-r2")):
                manifest.write_text(contents)
                with self.assertRaises(RuntimeError):
                    profile.check(tree, manifest)

    def test_kernel_export_requires_real_nfqueue_and_ebpf(self):
        with tempfile.TemporaryDirectory() as directory:
            tree = Path(directory)
            config = tree / "build_dir/target-x86_64/linux-x86_64/linux-6.18/.config"
            config.parent.mkdir(parents=True)
            base = "".join(f"CONFIG_{name}=y\n" for name in (
                "X86_64", "BPF_SYSCALL", "CGROUP_BPF", "DEBUG_INFO_BTF", "NETKIT",
                "XDP_SOCKETS", "NET_SCH_FQ", "TCP_CONG_BBR"))
            config.write_text(base)
            with self.assertRaises(RuntimeError):
                kernel.export_kernel_config(tree, tree / "export.config", "test")
            complete = base + "CONFIG_NFT_QUEUE=m\nCONFIG_NETFILTER_NETLINK_QUEUE=m\n"
            config.write_text(complete)
            kernel.export_kernel_config(tree, tree / "export.config", "test")
            for line in ("CONFIG_NFT_QUEUE=m\n", "CONFIG_NETFILTER_NETLINK_QUEUE=m\n", "CONFIG_DEBUG_INFO_BTF=y\n"):
                config.write_text(complete.replace(line, ""))
                with self.assertRaises(RuntimeError):
                    kernel.export_kernel_config(tree, tree / "export.config", "test")

    CORE_COMMIT = "aebc0d78d567cac1cd74ee9c56674857c5441451"
    CORE_ASSET = f"honk-core-{CORE_COMMIT}-x86_64.tar.gz"
    DOONA_ASSET = "doona-369aee8f-f6612106faf8.tar.gz"

    def tarball(self, path, files):
        with tarfile.open(path, "w:gz") as archive:
            for name, contents in files.items():
                info = tarfile.TarInfo(name)
                info.size = len(contents)
                archive.addfile(info, io.BytesIO(contents))

    def honk_pin(self, core_tar, doona_tar):
        core_hash = hashlib.sha256(core_tar.read_bytes()).hexdigest()
        doona_hash = hashlib.sha256(doona_tar.read_bytes()).hexdigest()
        release = "honk-source-39547891412"
        return {
            "format": 1,
            "upstream": "https://github.com/kenzok8/openwrt-honk.git",
            "upstream_release": "v2026.10.21-r39547891412",
            "source_tag": "source-39547891412",
            "wrapper_commit": "29857755c037f36d7a49fc888eef6efa90bf33fb",
            "mirror_repository": "https://github.com/hellomrli/my-openwrt-packages.git",
            "mirror_release": release,
            "release_url": f"https://github.com/hellomrli/my-openwrt-packages/releases/download/{release}",
            "core": {
                "repository": "https://github.com/Glassyiris/honk.git",
                "commit": self.CORE_COMMIT,
                "version": "0.0.1-alpha",
                "features": "clash-api,ebpf,rprx,native-api",
                "architectures": ["x86_64", "aarch64", "armv7"],
            },
            "assets": {
                "honk_x86_64": {"name": self.CORE_ASSET, "sha256": core_hash, "size": core_tar.stat().st_size},
                "doona": {"name": self.DOONA_ASSET, "sha256": doona_hash, "size": doona_tar.stat().st_size},
            },
        }

    def stage_honk_tree(self, tree, pin):
        core_dir = tree / "package/honk/honk"
        core_dir.mkdir(parents=True)
        (core_dir / "Makefile").write_text(
            f"PKG_NAME:=honk\nCORE_COMMIT:={pin['core']['commit']}\n")
        (core_dir / "generated-stage.mk").write_text(
            f"PKG_SOURCE_URL:={pin['release_url']}/\n"
            f"HONK_ASSET_X86_64:={pin['assets']['honk_x86_64']['name']}\n"
            f"HONK_HASH_X86_64:={pin['assets']['honk_x86_64']['sha256']}\n")
        (core_dir / "generated-provenance.json").write_text(json.dumps({"core": pin["core"]}))
        luci_dir = tree / "package/honk/luci-app-honk"
        luci_dir.mkdir()
        (luci_dir / "Makefile").write_text("PKG_NAME:=luci-app-honk\n")
        (luci_dir / "generated-doona-stage.mk").write_text(
            f"PKG_SOURCE:={pin['assets']['doona']['name']}\n"
            f"PKG_SOURCE_URL:={pin['release_url']}\n"
            f"PKG_HASH:={pin['assets']['doona']['sha256']}\n")
        (tree / "package/honk/honk-source.json").write_text(json.dumps(pin))
        (tree / "scripts").mkdir()
        (tree / "scripts/feeds").write_text("")

    def honk_fixture(self, directory):
        tree = directory / "tree"
        cache = directory / "cache"
        cache.mkdir()
        core_tar = cache / self.CORE_ASSET
        self.tarball(core_tar, {
            f"{self.CORE_ASSET[:-7]}/honk-core": b"core binary\n",
            f"{self.CORE_ASSET[:-7]}/LICENSE": b"license\n",
        })
        doona_tar = cache / self.DOONA_ASSET
        self.tarball(doona_tar, {
            "doona/index.html": b"<html></html>\n",
            "doona/LICENSE": b"license\n",
            "doona/NOTICE": b"notice\n",
            "doona/SOURCE": b"source\n",
            "doona/THIRD-PARTY-NOTICES.txt": b"third party\n",
        })
        pin = self.honk_pin(core_tar, doona_tar)
        self.stage_honk_tree(tree, pin)
        return tree, cache, pin

    def test_honk_pin_must_describe_the_mirror(self):
        with tempfile.TemporaryDirectory() as directory:
            tree, _, pin = self.honk_fixture(Path(directory))
            source.validate_sources(tree, pin)
            pin["release_url"] = pin["release_url"].replace(
                "github.com/hellomrli/my-openwrt-packages", "github.com/kenzok8/openwrt-honk")
            with self.assertRaises(RuntimeError):
                source.validate_sources(tree, pin)

    def test_honk_stage_files_must_match_the_pin(self):
        with tempfile.TemporaryDirectory() as directory:
            tree, _, pin = self.honk_fixture(Path(directory))
            stage = tree / "package/honk/honk/generated-stage.mk"
            original = stage.read_text()
            stage.write_text(original.replace(pin["core"]["commit"], "0" * 40))
            with self.assertRaises(RuntimeError):
                source.validate_sources(tree, pin)
            stage.write_text(original)
            stage.write_text(original.replace(pin["assets"]["honk_x86_64"]["sha256"], "0" * 64))
            with self.assertRaises(RuntimeError):
                source.validate_sources(tree, pin)

    def test_honk_assets_are_hash_checked_before_use(self):
        with tempfile.TemporaryDirectory() as directory:
            tree, cache, pin = self.honk_fixture(Path(directory))
            self.assertEqual(source.install(tree, pin, cache), [self.CORE_ASSET, self.DOONA_ASSET])
            for name in (self.CORE_ASSET, self.DOONA_ASSET):
                self.assertTrue((tree / "dl" / name).is_file())
            (tree / "dl" / self.CORE_ASSET).unlink()
            (cache / self.CORE_ASSET).write_bytes(b"corrupt data")
            with self.assertRaises(RuntimeError):
                source.install(tree, pin, cache)
            for expected in ("SKIP", "0" * 64):
                with self.assertRaises(RuntimeError):
                    source.verify_hash(tree / "dl" / self.DOONA_ASSET, expected)

    def test_honk_provenance_features_are_required(self):
        with tempfile.TemporaryDirectory() as directory:
            tree, _, pin = self.honk_fixture(Path(directory))
            provenance = tree / "package/honk/honk/generated-provenance.json"
            data = json.loads(provenance.read_text())
            data["core"]["features"] = "ebpf"
            provenance.write_text(json.dumps(data))
            with self.assertRaises(RuntimeError):
                source.validate_sources(tree, pin)

    def test_feed_workaround_is_narrow_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            tree = Path(directory)
            package = tree / "feeds/packages/net/miniupnpd"
            patches = package / "patches"
            patches.mkdir(parents=True)
            makefile = package / "Makefile"
            makefile.write_text("PKG_VERSION:=2.3.11\nPKG_HASH:=91994b127da735b2c97f19992e34420648c0e8c4ace8a4bcb0596e7685c48678\n")
            stale = patches / "020-descr-filter-fix.patch"
            stale.write_bytes(b"unknown upstream change")
            with self.assertRaises(RuntimeError):
                compat.patch(tree)
            self.assertTrue(stale.exists())
            with mock.patch.dict(compat.STALE_PATCHES, {stale.name: hashlib.sha256(stale.read_bytes()).hexdigest()}):
                self.assertEqual(compat.patch(tree), [stale.name])
                self.assertEqual(compat.patch(tree), [])
            stale.write_bytes(b"new upstream fix")
            makefile.write_text("PKG_VERSION:=2.3.12\n")
            self.assertEqual(compat.patch(tree), [])
            self.assertTrue(stale.exists())

    def test_feed_workaround_preserves_refreshed_upstream_patches(self):
        with tempfile.TemporaryDirectory() as directory:
            tree = Path(directory)
            package = tree / "feeds/packages/net/miniupnpd"
            patches = package / "patches"
            patches.mkdir(parents=True)
            (package / "Makefile").write_text(
                "PKG_VERSION:=2.3.11\n"
                "PKG_HASH:=91994b127da735b2c97f19992e34420648c0e8c4ace8a4bcb0596e7685c48678\n")
            retained = {
                "010-upnp-igdv2-compat.patch": b"upstream IGD compatibility\n",
                "040-improve-logging.patch": b"upstream logging rebased onto 2.3.11\n",
                "900-miniupnpd-format-xml-to-make-some-app-happy.patch": b"upstream XML compatibility\n",
            }
            for name, contents in retained.items():
                (patches / name).write_bytes(contents)
            for logging in (retained["040-improve-logging.patch"], b"another upstream logging refresh\n"):
                with self.subTest(logging=logging):
                    retained["040-improve-logging.patch"] = logging
                    (patches / "040-improve-logging.patch").write_bytes(logging)
                    for _ in range(2):
                        self.assertEqual(compat.patch(tree), [])
                        for name, contents in retained.items():
                            self.assertEqual((patches / name).read_bytes(), contents)

    def test_feed_workaround_checks_all_stale_hashes_before_removal(self):
        with tempfile.TemporaryDirectory() as directory:
            tree = Path(directory)
            package = tree / "feeds/packages/net/miniupnpd"
            patches = package / "patches"
            patches.mkdir(parents=True)
            (package / "Makefile").write_text(
                "PKG_VERSION:=2.3.11\n"
                "PKG_HASH:=91994b127da735b2c97f19992e34420648c0e8c4ace8a4bcb0596e7685c48678\n")
            stale = {
                "020-descr-filter-fix.patch": b"known parser fix\n",
                "030-allow-private-fix.patch": b"known private-IP fix\n",
            }
            for name, contents in stale.items():
                (patches / name).write_bytes(contents)
            logging = patches / "040-improve-logging.patch"
            logging.write_bytes(b"refreshed upstream logging\n")
            hashes = {name: hashlib.sha256(contents).hexdigest() for name, contents in stale.items()}
            with mock.patch.dict(compat.STALE_PATCHES, hashes):
                changed = patches / "030-allow-private-fix.patch"
                changed.write_bytes(b"unknown upstream private-IP change\n")
                with self.assertRaisesRegex(RuntimeError, "Upstream changed 030-allow-private-fix.patch"):
                    compat.patch(tree)
                self.assertEqual((patches / "020-descr-filter-fix.patch").read_bytes(), stale["020-descr-filter-fix.patch"])
                self.assertEqual(changed.read_bytes(), b"unknown upstream private-IP change\n")
                changed.write_bytes(stale[changed.name])
                self.assertEqual(set(compat.patch(tree)), set(stale))
                self.assertEqual(compat.patch(tree), [])
            self.assertEqual(logging.read_bytes(), b"refreshed upstream logging\n")
            for name in stale:
                self.assertFalse((patches / name).exists())

    def test_target_and_release_isolation(self):
        targets = json.loads((ROOT / ".github/targets.json").read_text())["targets"]
        test = next(item for item in targets if item["branch"] == "test")
        self.assertEqual(test["upstream_branch"], "master")
        self.assertFalse(test["automatic"])
        master = next(item for item in targets if item["branch"] == "master")
        self.assertEqual(master["profile"], "honk")
        self.assertEqual(master["config_file"], "configs/honk.config")
        self.assertEqual(master["diy_p2_sh"], "diy-part2-honk.sh")
        self.assertNotIn("/etc/honk", (ROOT / "files/lib/upgrade/keep.d/my-immortalwrt").read_text().splitlines())
        workflow = yaml.safe_load((ROOT / ".github/workflows/openwrt-builder.yml").read_text())
        steps = {step["name"]: step for step in workflow["jobs"]["build"]["steps"]}
        release = steps["Upload to release"]["with"]
        self.assertIn("matrix.branch == 'test'", release["prerelease"])
        self.assertIn("'false'", release["make_latest"])
        self.assertIn("github.ref_name != 'test'", steps["Refresh README build table"]["if"])
        recovery = steps["Preserve unpublished firmware on organize failure"]
        self.assertIn("matrix.profile == 'honk'", recovery["if"])
        self.assertIn("steps.compile.outputs.status == 'success'", recovery["if"])
        self.assertIn("steps.organize.outcome == 'failure'", recovery["if"])
        self.assertEqual(recovery["with"]["name"], "unpublished-firmware_${{ github.run_id }}")
        self.assertTrue(recovery["with"]["include-hidden-files"])
        self.assertIn("openwrt/bin/targets", recovery["with"]["path"].splitlines())
        packages = json.loads((ROOT / ".github/packages-honk.json").read_text())["packages"]
        self.assertEqual({package["name"] for package in packages},
                         {"honk", "luci-app-lucky", "luci-app-watchdog"})
        honk = next(package for package in packages if package["name"] == "honk")
        self.assertTrue(honk["mirror_only"])
        self.assertIn("honk-source.json", honk["require"])


if __name__ == "__main__":
    unittest.main()
