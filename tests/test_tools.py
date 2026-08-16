"""Regression tests for the project-tool safety boundary."""

import tempfile
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

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


class SearchToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tools = ProjectTools(self.temp_dir.name)
        Path(self.temp_dir.name, "src").mkdir()
        Path(self.temp_dir.name, "src", "Agent.py").write_text(
            "def launch_agent():\n    return 'ready'\n", encoding="utf-8"
        )
        Path(self.temp_dir.name, "node_modules").mkdir()
        Path(self.temp_dir.name, "node_modules", "hidden.py").write_text(
            "launch_agent()\n", encoding="utf-8"
        )
        Path(self.temp_dir.name, "custom-python").mkdir()
        Path(self.temp_dir.name, "custom-python", "pyvenv.cfg").write_text("", encoding="utf-8")
        Path(self.temp_dir.name, "custom-python", "hidden.py").write_text(
            "launch_agent()\n", encoding="utf-8"
        )
        Path(self.temp_dir.name, "binary.dat").write_bytes(b"launch_agent\0")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_finds_files_case_insensitively_and_skips_dependencies(self):
        self.assertEqual("src/Agent.py", self.tools.find_files("agent"))
        self.assertEqual("No matching files.", self.tools.find_files("hidden"))

    def test_searches_text_with_line_numbers_and_case_option(self):
        self.assertEqual(
            "src/Agent.py:1: def launch_agent():",
            self.tools.search_code("LAUNCH_AGENT"),
        )
        self.assertEqual("No matches.", self.tools.search_code("LAUNCH_AGENT", case_sensitive=True))
        self.assertEqual("No matches.", self.tools.search_code("launch_agent\0"))

    def test_rejects_empty_or_multiline_queries(self):
        with self.assertRaises(ValueError):
            self.tools.find_files("")
        with self.assertRaises(ValueError):
            self.tools.search_code("line one\nline two")


class PatchFileTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tools = ProjectTools(self.temp_dir.name)
        Path(self.temp_dir.name, "example.txt").write_text(
            "one\ntwo\nthree\n", encoding="utf-8"
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_applies_unified_diff_and_reports_summary(self):
        result = self.tools.patch_file(
            "example.txt",
            "@@ -1,3 +1,4 @@\n one\n-two\n+two updated\n+two and a half\n three",
        )

        self.assertEqual("Applied patch to 'example.txt': +2 lines, -1 lines.", result)
        self.assertEqual(
            "one\ntwo updated\ntwo and a half\nthree\n",
            Path(self.temp_dir.name, "example.txt").read_text(encoding="utf-8"),
        )

    def test_rejects_stale_patch_without_changing_file(self):
        with self.assertRaisesRegex(ValueError, "no longer matches"):
            self.tools.patch_file("example.txt", "@@ -1 +1 @@\n-not one\n+replacement")

        self.assertEqual(
            "one\ntwo\nthree\n",
            Path(self.temp_dir.name, "example.txt").read_text(encoding="utf-8"),
        )

    def test_applies_standard_empty_file_addition(self):
        Path(self.temp_dir.name, "empty.txt").write_text("", encoding="utf-8")

        self.tools.patch_file("empty.txt", "@@ -0,0 +1 @@\n+first line")

        self.assertEqual(
            "first line",
            Path(self.temp_dir.name, "empty.txt").read_text(encoding="utf-8"),
        )


class RunTestsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tools = ProjectTools(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_detects_unittest_tests_directory(self):
        Path(self.temp_dir.name, "tests").mkdir()

        with patch.object(self.tools, "run_command", return_value="Exit code: 0\nOK") as run:
            result = self.tools.run_tests()

        run.assert_called_once_with(["python", "-m", "unittest", "discover", "-s", "tests"], ".")
        self.assertIn("Detected test command: python -m unittest discover -s tests", result)

    def test_prefers_npm_test_script(self):
        Path(self.temp_dir.name, "package.json").write_text(
            '{"scripts": {"test": "vitest run"}}', encoding="utf-8"
        )

        with patch.object(self.tools, "run_command", return_value="Exit code: 0\nOK") as run:
            self.tools.run_tests()

        run.assert_called_once_with(["npm", "test"], ".")

    def test_reports_when_no_supported_tests_exist(self):
        self.assertIn("No supported test setup", self.tools.run_tests())
