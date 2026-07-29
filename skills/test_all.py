from __future__ import annotations

import unittest
from pathlib import Path


SKILLS = Path(__file__).resolve().parent


def load_tests(
    loader: unittest.TestLoader,
    standard_tests: unittest.TestSuite,
    pattern: str | None,
) -> unittest.TestSuite:
    """Collect every flat skill's test suite for top-level discovery."""
    suite = loader.suiteClass()
    suite.addTests(standard_tests)
    for tests_root in sorted(SKILLS.glob("*/tests")):
        suite.addTests(
            loader.discover(
                start_dir=str(tests_root),
                pattern=pattern or "test_*.py",
                top_level_dir=str(tests_root),
            )
        )
    return suite
