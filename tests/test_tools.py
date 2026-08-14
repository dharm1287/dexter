"""Regression tests for the project-tool safety boundary."""

import tempfile
import sys
import types
import unittest
from pathlib import Path

# The tool tests do not use environment loading.  Provide this tiny stand-in so
# they remain runnable in a bare Python installation; normal application use
# still requires python-dotenv as documented.
if "dotenv" not in sys.modules:
    dotenv_stub = types.ModuleType("dotenv")
    dotenv_stub.load_dotenv = lambda: False
    sys.modules["dotenv"] = dotenv_stub

from agent_pkg.tools import ProjectTools


class RunCommandTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tools = ProjectTools(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_runs_approved_python_module(self):
        Path(self.temp_dir.name, "sample.py").write_text("value = 1\n", encoding="utf-8")

        result = self.tools.run_command(["python", "-m", "compileall", "sample.py"])

        self.assertIn("Exit code: 0", result)

    def test_rejects_shell_and_mutating_commands(self):
        rejected = [
            ["powershell", "Remove-Item", "x"],
            ["python", "-c", "print('unsafe')"],
            ["git", "commit", "-m", "message"],
            ["black", "."],
            ["ruff", "check", "--fix", "."],
            ["npm", "exec", "some-package"],
        ]

        for command in rejected:
            with self.subTest(command=command):
                with self.assertRaises(ValueError):
                    self.tools.run_command(command)

    def test_blocks_working_directory_escape(self):
        with self.assertRaises(ValueError):
            self.tools.run_command(["python", "-m", "compileall"], "..")
