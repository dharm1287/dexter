"""Tests for launch-time configuration overrides."""

import unittest

from agent_pkg import config


class RuntimeConfigTests(unittest.TestCase):
    def setUp(self):
        self.original = (config.MODEL, config.DEFAULT_TEMPERATURE, config.MAX_TOOL_ITERATIONS)

    def tearDown(self):
        config.configure_runtime(
            model=self.original[0],
            temperature=self.original[1],
            max_tool_iterations=self.original[2],
        )

    def test_configure_runtime_applies_overrides(self):
        config.configure_runtime(model="test-model", temperature=0.7, max_tool_iterations=9)

        self.assertEqual("test-model", config.MODEL)
        self.assertEqual(0.7, config.DEFAULT_TEMPERATURE)
        self.assertEqual(9, config.MAX_TOOL_ITERATIONS)
