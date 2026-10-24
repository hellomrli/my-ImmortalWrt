#!/usr/bin/env python3
"""Exercise only the YAML migration functions, never the host init services."""

from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (ROOT / "files/etc/uci-defaults/99-adh-dual").read_text()
FUNCTIONS = SCRIPT[SCRIPT.index("adh_has_user() {"):SCRIPT.index("# Older images shipped")]


class AdhMigrationTests(unittest.TestCase):
    def migrate(self, users, authenticated):
        original = "http:\n  address: 192.168.50.1:50080\n" + users
        original += "dns:\n  port: 50530\nfilters:\n  - name: unrelated\n"
        with tempfile.TemporaryDirectory() as directory:
            conf = Path(directory) / "adh.yaml"
            conf.write_text(original)
            command = FUNCTIONS + '\nsecure_unauthenticated_web "$1" 127.0.0.1:50080\n'
            for _ in range(2):
                subprocess.run(["sh", "-eu", "-c", command, "migration-test", str(conf)],
                               check=True, capture_output=True, text=True, timeout=5)
            expected = original if authenticated else original.replace("192.168.50.1:50080", "127.0.0.1:50080")
            self.assertEqual(conf.read_text(), expected)

    def test_indented_users_keep_lan_binding(self):
        self.migrate("users:\n  - name: admin\n    password: bcrypt-hash\n", True)

    def test_indentless_users_keep_lan_binding(self):
        self.migrate("users:\n- name: admin\n  password: bcrypt-hash\n", True)

    def test_name_need_not_be_first_key(self):
        for indent in ("", "  "):
            with self.subTest(indent=indent):
                self.migrate(f"users:\n{indent}- password: bcrypt-hash\n{indent}  name: admin\n", True)

    def test_comments_do_not_end_users_section(self):
        self.migrate("users: # administrators\n# kept across upgrades\n\n- name: admin\n  password: bcrypt-hash\n", True)

    def test_empty_users_are_loopback_only(self):
        for users in ("users: []\n", "users:\n", "users: null\n", "", "users:\n  # - name: example\n"):
            with self.subTest(users=users):
                self.migrate(users, False)

    def test_unrelated_named_list_is_not_an_adh_user(self):
        self.migrate("users: []\nother:\n- name: not-an-admin\n", False)


if __name__ == "__main__":
    unittest.main()
