#!/usr/bin/env python3
"""Regression checks for branch selection, scheduling and master isolation."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]


def matrix_script(workflow, step_name):
    workflow = yaml.safe_load((ROOT / '.github/workflows' / workflow).read_text())
    step = next(s for s in workflow['jobs']['prepare']['steps'] if s['name'] == step_name)
    lines = step['run'].splitlines()
    return '\n'.join(lines[1:-1])


class IntegrationTests(unittest.TestCase):
    def test_target_selection_and_upstream(self):
        targets = json.loads((ROOT / '.github/targets.json').read_text())['targets']
        self.assertEqual([t['branch'] for t in targets], ['master', 'iptv'])
        self.assertEqual(targets[0]['config_file'], 'configs/immortalwrt.config')
        self.assertEqual(targets[0]['diy_p2_sh'], 'diy-part2-daed.sh')
        self.assertEqual(targets[1]['upstream_branch'], 'master')
        script = matrix_script('openwrt-builder.yml', 'Generate build matrix')
        for selection, want in [('all', ['master', 'iptv']), ('iptv', ['iptv']), ('["master"]', ['master'])]:
            with tempfile.NamedTemporaryFile() as output:
                env = dict(os.environ, GITHUB_OUTPUT=output.name, REQUESTED_SOURCES='all', REQUESTED_BRANCHES=selection)
                subprocess.run([sys.executable, '-c', script], cwd=ROOT, env=env, check=True, capture_output=True)
                line = Path(output.name).read_text().splitlines()[0]
                actual = json.loads(line.removeprefix('matrix='))['include']
                self.assertEqual([t['branch'] for t in actual], want)
        with tempfile.NamedTemporaryFile() as output:
            env = dict(os.environ, GITHUB_OUTPUT=output.name, REQUESTED_BRANCHES='openwrt-25.12')
            result = subprocess.run([sys.executable, '-c', script], cwd=ROOT, env=env, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
        with tempfile.NamedTemporaryFile() as output:
            script = matrix_script('update-checker.yml', 'Generate check matrix')
            subprocess.run([sys.executable, '-c', script], cwd=ROOT, env=dict(os.environ, GITHUB_OUTPUT=output.name), check=True)
            actual = json.loads(Path(output.name).read_text().strip().removeprefix('matrix='))['include']
            self.assertEqual([t['upstream_branch'] for t in actual], ['master', 'master'])

    def test_kernel_export_keeps_master_checks(self):
        path = ROOT / '.github/scripts/export-kernel-config.py'
        spec = importlib.util.spec_from_file_location('kernel_export', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            tree = Path(directory)
            config = tree / 'build_dir/target-x86_64/linux-x86_64/linux-6.12/.config'
            config.parent.mkdir(parents=True)
            config.write_text('CONFIG_X86_64=y\nCONFIG_NET_SCH_FQ=m\nCONFIG_TCP_CONG_BBR=m\n')
            module.export_kernel_config(tree, tree / 'exported.config', 'iptv')
            with self.assertRaises(RuntimeError):
                module.export_kernel_config(tree, tree / 'master.config')

    def test_cron_migration_is_idempotent_and_preserves_other_jobs(self):
        with tempfile.TemporaryDirectory() as directory:
            tree = Path(directory)
            (tree / 'etc/crontabs').mkdir(parents=True)
            (tree / 'etc/init.d').mkdir()
            functions = tree / 'functions.sh'
            functions.write_text('''optional=$IPKG_INSTROOT
config_load() { :; }
config_get() { eval "$1=\\${MOCK_$3:-$4}"; }
config_get_bool() { config_get "$@"; }
''')
            cron = tree / 'etc/init.d/cron'
            cron.write_text('#!/bin/sh\nexit 0\n')
            cron.chmod(0o755)
            script = (ROOT / 'packages/gxmobile-scan/root/usr/libexec/gxmobile-schedule').read_text()
            script = script.replace('/lib/functions.sh', str(functions)).replace('/etc/crontabs', str(tree / 'etc/crontabs'))
            script = script.replace('/etc/init.d/cron', str(cron)).replace('/var/lock', str(tree / 'lock'))
            helper = tree / 'schedule'
            helper.write_text(script)
            crontab = tree / 'etc/crontabs/root'
            other = '# keep my jobs\n5 1 * * * /usr/bin/backup\n'
            crontab.write_text(other + '20 4 * * 1 /usr/bin/gxmobile-scan >> /tmp/old.log 2>&1\n')
            env = dict(os.environ, MOCK_schedule_enabled='1')
            for _ in range(2):
                subprocess.run(['sh', str(helper), 'sync'], env=env, check=True)
            self.assertEqual(crontab.read_text(), other + '20 4 * * 1 /usr/libexec/gxmobile-schedule run # gxmobile-managed\n')
            subprocess.run(['sh', str(helper), 'sync'], env=dict(env, MOCK_frequency='daily', MOCK_hour='3'), check=True)
            self.assertIn('20 3 * * * /usr/libexec/gxmobile-schedule run', crontab.read_text())
            subprocess.run(['sh', str(helper), 'sync'], env=dict(env, MOCK_schedule_enabled='0'), check=True)
            self.assertEqual(crontab.read_text(), other)
            result = subprocess.run(['sh', str(helper), 'sync'], env=dict(env, MOCK_hour='25'))
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(crontab.read_text(), other)


if __name__ == '__main__':
    unittest.main()
