#!/usr/bin/env python3
"""Test release ordering without contacting the vendor service."""

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("pin_lucky", Path(__file__).with_name("pin-lucky-source.py"))
LUCKY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LUCKY)


class LuckyReleaseTests(unittest.TestCase):
    def pick(self, releases, requested=None):
        checksums = {"lucky_test_Linux_x86_64.tar.gz": "a" * 64}
        with patch.object(LUCKY, "list_dir", return_value=releases) as listing, \
                patch.object(LUCKY, "fetch_checksums", return_value=checksums) as fetch:
            release, product, actual = LUCKY.pick_release(requested)
        listing.assert_called_once_with(LUCKY.BASE_URL)
        fetch.assert_called_once_with(release, product)
        self.assertEqual(actual, checksums)
        return release, product

    def test_stable_beats_same_version_beta_and_rc(self):
        for releases in (["v3.1.4beta", "v3.1.4", "v3.1.4rc1"],
                         ["v3.1.4rc1", "v3.1.4", "v3.1.4beta"]):
            with self.subTest(releases=releases):
                self.assertEqual(self.pick(releases), ("v3.1.4", "3.1.4_lucky"))

    def test_numeric_pin_prefers_stable(self):
        self.assertEqual(self.pick(["v3.2.0", "v3.1.4beta", "v3.1.4", "v3.1.4rc1"], "3.1.4"),
                         ("v3.1.4", "3.1.4_lucky"))

    def test_numeric_order_not_lexicographic(self):
        self.assertEqual(self.pick(["v3.1.9", "v3.1.10"]), ("v3.1.10", "3.1.10_lucky"))

    def test_beta_only_vendor_layout_remains_supported(self):
        for requested in (None, "3.1.4"):
            with self.subTest(requested=requested):
                self.assertEqual(self.pick(["v3.1.4beta", "v3.1.3"], requested),
                                 ("v3.1.4beta", "3.1.4_lucky"))

    def test_higher_numeric_beta_still_precedes_older_stable(self):
        self.assertEqual(self.pick(["v3.1.4", "v3.1.5beta"]), ("v3.1.5beta", "3.1.5_lucky"))


if __name__ == "__main__":
    unittest.main()
