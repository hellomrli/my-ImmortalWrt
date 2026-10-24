#!/usr/bin/env python3
"""Test wall-clock budgeting and diagnostic priority in the build workflow."""

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import yaml


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("build_budget", Path(__file__).with_name("build-time-budget.py"))
BUDGET = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUDGET)


class BudgetTests(unittest.TestCase):
    def test_elapsed_prerequisites_reduce_compile_time(self):
        for elapsed, expected in ((0, 320), (10, 310), (45, 275), (300, 20), (319, 1)):
            with self.subTest(elapsed=elapsed):
                self.assertEqual(BUDGET.compile_minutes(1000, 1000 + elapsed * 60, 350), expected)

    def test_partial_minutes_round_down(self):
        self.assertEqual(BUDGET.compile_minutes(1000, 1601, 350), 309)

    def test_exhausted_budget_fails_before_make(self):
        for elapsed in (320, 350, 400):
            with self.subTest(elapsed=elapsed), self.assertRaises(ValueError):
                BUDGET.compile_minutes(1000, 1000 + elapsed * 60, 350)

    def test_compile_cap_and_invalid_clock(self):
        self.assertEqual(BUDGET.compile_minutes(1000, 1000, 600), 320)
        with self.assertRaises(ValueError):
            BUDGET.compile_minutes(1000, 999, 350)

    def test_step_output_uses_recorded_start_and_current_time(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            with patch.dict(os.environ, BUILD_STARTED_AT="1000", BUILD_JOB_TIMEOUT_MINUTES="350", GITHUB_OUTPUT=str(output)), \
                    patch.object(BUDGET.time, "time", return_value=3700):
                self.assertEqual(BUDGET.main(), 0)
            self.assertEqual(output.read_text(), "minutes=275\n")

    def test_workflow_bounds_prerequisites_and_prioritizes_logs(self):
        job = yaml.safe_load((ROOT / ".github/workflows/openwrt-builder.yml").read_text())["jobs"]["build"]
        steps = job["steps"]
        names = [step["name"] for step in steps]
        by_name = {step["name"]: step for step in steps}
        self.assertEqual(job["timeout-minutes"], job["env"]["BUILD_JOB_TIMEOUT_MINUTES"])
        self.assertEqual(names[0], "Record build start")
        self.assertIn("BUILD_STARTED_AT=$(date +%s)", steps[0]["run"])
        budget = by_name["Calculate compile budget"]
        self.assertIn("build-time-budget.py", budget["run"])
        compile_step = by_name["Compile firmware"]
        self.assertEqual(compile_step["timeout-minutes"], "${{ fromJSON(steps.budget.outputs.minutes || '1') }}")
        self.assertEqual(budget["id"], "budget")
        self.assertEqual(names.index("Calculate compile budget") + 1, names.index("Compile firmware"))
        prerequisites = steps[:names.index("Compile firmware")]
        for step in prerequisites:
            self.assertIsInstance(step["timeout-minutes"], int, step["name"])
            self.assertGreater(step["timeout-minutes"], 0)
        # Even if every prerequisite takes its full limit, diagnostics retain
        # a generous margin; conditional steps only reduce the actual total.
        self.assertLess(sum(step["timeout-minutes"] for step in prerequisites), job["timeout-minutes"] - 35)
        self.assertLess(names.index("Collect build diagnostics"), names.index("Upload build logs"))
        self.assertLess(names.index("Upload build logs"), names.index("Measure build caches"))
        self.assertLess(names.index("Upload build logs"), names.index("Save ccache"))
        finalization = [by_name[name] for name in (
            "Collect build diagnostics", "Upload build logs", "Measure build caches", "Save ccache")]
        self.assertLess(sum(step["timeout-minutes"] for step in finalization), 30)


if __name__ == "__main__":
    unittest.main()
