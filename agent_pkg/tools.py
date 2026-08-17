"""Project tools sandboxed to a single project directory."""

import json
import os
from pathlib import Path
import re
import subprocess

from . import config


# This is deliberately an allow-list.  Commands are passed as argument arrays
# (never through a shell), so metacharacters, pipes, and redirection cannot be
# interpreted.  The permitted commands cover common test, lint, build, and
# read-only Git workflows without granting a general-purpose terminal.
_DIRECT_COMMANDS = {"pytest", "ruff", "mypy", "flake8", "black", "git"}
_PYTHON_MODULES = {"pytest", "unittest", "compileall"}
_NODE_SCRIPT_ACTIONS = {"test", "run"}
_NODE_SCRIPT_NAMES = {"test", "lint", "build", "check", "typecheck", "format"}
_HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
_SEARCH_IGNORED_DIRECTORIES = {".git", "__pycache__", "node_modules", ".venv", "venv"}


class ProjectTools:
    """Read/write/list files within a fixed project directory only."""

    def __init__(self, project_dir: str):
        self.root = Path(project_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, rel_path: str) -> Path:
        """Resolve a relative path, blocking escapes via '..' or absolute paths."""
        candidate = (self.root / rel_path).resolve()
        if self.root not in candidate.parents and candidate != self.root:
            raise ValueError(f"Path '{rel_path}' escapes the project directory.")
        return candidate

    def list_files(self, path: str = ".") -> str:
        target = self._resolve(path)
        if not target.exists():
            return f"Error: '{path}' does not exist."
        entries = []
        for p in sorted(target.rglob("*")):
            if any(part.startswith(".git") for part in p.parts) or p.name == config.SESSION_FILENAME:
                continue
            entries.append(str(p.relative_to(self.root)))
        return "\n".join(entries) if entries else "(empty)"

    def _iter_searchable_files(self, directory: Path):
        """Yield project-contained files while pruning common generated folders."""
        for root, directories, files in os.walk(directory):
            root_path = Path(root)
            directories[:] = [
                name
                for name in directories
                if name not in _SEARCH_IGNORED_DIRECTORIES
                and not (root_path / name / "pyvenv.cfg").is_file()
            ]
            for name in files:
                candidate = Path(root, name)
                if candidate.name == config.SESSION_FILENAME:
                    continue
                resolved = candidate.resolve()
                if self.root in resolved.parents:
                    yield candidate

    @staticmethod
    def _validate_search_query(query: str) -> None:
        if not isinstance(query, str) or not query:
            raise ValueError("Search query must be a non-empty string.")
        if "\n" in query or "\r" in query:
            raise ValueError("Search query must be a single line.")

    def find_files(self, query: str, path: str = ".") -> str:
        """Find project files whose relative path contains a query string."""
        self._validate_search_query(query)
        directory = self._resolve(path)
        if not directory.is_dir():
            raise ValueError(f"Search path '{path}' is not a directory.")

        needle = query.casefold()
        matches = []
        for candidate in self._iter_searchable_files(directory):
            relative = candidate.relative_to(self.root).as_posix()
            if needle in relative.casefold():
                matches.append(relative)
                if len(matches) == config.SEARCH_RESULT_LIMIT:
                    return "\n".join(matches) + "\n[Results truncated.]"
        return "\n".join(matches) if matches else "No matching files."

    def search_code(self, query: str, path: str = ".", case_sensitive: bool = False) -> str:
        """Search text files and return matching path, line number, and line text."""
        self._validate_search_query(query)
        if not isinstance(case_sensitive, bool):
            raise ValueError("case_sensitive must be true or false.")
        directory = self._resolve(path)
        if not directory.is_dir():
            raise ValueError(f"Search path '{path}' is not a directory.")

        needle = query if case_sensitive else query.casefold()
        matches = []
        for candidate in self._iter_searchable_files(directory):
            try:
                if candidate.stat().st_size > config.SEARCH_FILE_SIZE_LIMIT:
                    continue
                content = candidate.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if "\0" in content:
                continue

            relative = candidate.relative_to(self.root).as_posix()
            for line_number, line in enumerate(content.splitlines(), start=1):
                haystack = line if case_sensitive else line.casefold()
                if needle in haystack:
                    matches.append(f"{relative}:{line_number}: {line}")
                    if len(matches) == config.SEARCH_RESULT_LIMIT:
                        return "\n".join(matches) + "\n[Results truncated.]"
        return "\n".join(matches) if matches else "No matches."

    def read_file(self, path: str) -> str:
        target = self._resolve(path)
        if not target.exists():
            return f"Error: file '{path}' does not exist."
        try:
            return target.read_text(encoding="utf-8")
        except Exception as e:
            return f"Error reading '{path}': {e}"

    def write_file(self, path: str, content: str) -> str:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} characters to '{path}'."

    def patch_file(self, path: str, patch: str) -> str:
        """Apply a unified diff to an existing project file.

        The path is supplied separately so diff headers cannot redirect the
        edit to another file. Every context/removal line must match exactly;
        this prevents a stale patch from silently changing the wrong code.
        """
        target = self._resolve(path)
        if not target.is_file():
            return f"Error: file '{path}' does not exist."
        if not isinstance(patch, str) or not patch.strip():
            raise ValueError("Patch must be a non-empty unified diff.")

        original = target.read_text(encoding="utf-8")
        newline = "\r\n" if "\r\n" in original else "\n"
        had_final_newline = original.endswith(("\n", "\r"))
        source_lines = original.splitlines()
        patch_lines = patch.replace("\r\n", "\n").replace("\r", "\n").split("\n")

        # File headers are optional because the explicit path is authoritative.
        while patch_lines and (patch_lines[0].startswith("--- ") or patch_lines[0].startswith("+++ ")):
            patch_lines.pop(0)

        result_lines = []
        source_cursor = 0
        additions = deletions = 0
        index = 0
        saw_hunk = False

        while index < len(patch_lines):
            header = _HUNK_HEADER.match(patch_lines[index])
            if not header:
                if patch_lines[index] == "":
                    index += 1
                    continue
                raise ValueError(f"Invalid unified-diff hunk header: {patch_lines[index]!r}")

            saw_hunk = True
            old_start = int(header.group(1))
            old_count = int(header.group(2) or "1")
            new_start = int(header.group(3))
            new_count = int(header.group(4) or "1")
            if (
                old_start < 0
                or new_start < 0
                or old_count < 0
                or new_count < 0
                or (old_start == 0 and old_count != 0)
                or (new_start == 0 and new_count != 0)
            ):
                raise ValueError("Invalid line range in unified-diff hunk.")
            expected_cursor = 0 if old_start == 0 else old_start - 1
            if expected_cursor < source_cursor or expected_cursor > len(source_lines):
                raise ValueError("Patch hunks are out of order or outside the file.")

            result_lines.extend(source_lines[source_cursor:expected_cursor])
            source_cursor = expected_cursor
            index += 1
            old_seen = 0
            new_seen = 0

            while index < len(patch_lines) and not _HUNK_HEADER.match(patch_lines[index]):
                line = patch_lines[index]
                index += 1
                if line == "\\ No newline at end of file":
                    continue
                if not line or line[0] not in " +-":
                    raise ValueError(f"Invalid unified-diff line: {line!r}")

                marker, content = line[0], line[1:]
                if marker in " -":
                    if source_cursor >= len(source_lines) or source_lines[source_cursor] != content:
                        raise ValueError(
                            f"Patch no longer matches '{path}' at line {source_cursor + 1}."
                        )
                    source_cursor += 1
                    old_seen += 1
                if marker in " +":
                    result_lines.append(content)
                    new_seen += 1
                if marker == "+":
                    additions += 1
                elif marker == "-":
                    deletions += 1

            if old_seen != old_count:
                raise ValueError(
                    f"Hunk expected {old_count} original lines but contains {old_seen}."
                )
            if new_seen != new_count:
                raise ValueError(
                    f"Hunk expected {new_count} updated lines but contains {new_seen}."
                )

        if not saw_hunk:
            raise ValueError("Patch does not contain a unified-diff hunk.")

        result_lines.extend(source_lines[source_cursor:])
        updated = newline.join(result_lines)
        if result_lines and had_final_newline:
            updated += newline
        target.write_text(updated, encoding="utf-8", newline="")
        return f"Applied patch to '{path}': +{additions} lines, -{deletions} lines."

    def _validate_command(self, command: list[str]) -> None:
        if not command or not all(isinstance(part, str) and part for part in command):
            raise ValueError("Command must be a non-empty array of strings.")

        executable = command[0].lower()
        if executable in _DIRECT_COMMANDS:
            if executable == "git" and (len(command) < 2 or command[1] not in {"status", "diff", "log"}):
                raise ValueError("Only 'git status', 'git diff', and 'git log' are allowed.")
            if executable == "black" and "--check" not in command:
                raise ValueError("Black is only allowed with --check.")
            if executable == "ruff" and any(option in {"--fix", "--unsafe-fixes"} for option in command[1:]):
                raise ValueError("Ruff fix options are not allowed.")
            return

        if executable in {"python", "python3", "py"}:
            if len(command) >= 3 and command[1] == "-m" and command[2] in _PYTHON_MODULES:
                return
            raise ValueError("Python commands must use -m pytest, unittest, or compileall.")

        if executable in {"npm", "pnpm", "yarn"}:
            if len(command) >= 2 and command[1] in _NODE_SCRIPT_ACTIONS:
                if command[1] == "run" and (len(command) < 3 or command[2] not in _NODE_SCRIPT_NAMES):
                    raise ValueError("Only standard npm run scripts are allowed.")
                return
            raise ValueError("Only test or run package-manager commands are allowed.")

        raise ValueError(f"Command '{command[0]}' is not permitted.")

    def run_command(self, command: list[str], path: str = ".") -> str:
        """Run an approved test, lint, build, or read-only Git command."""
        self._validate_command(command)
        cwd = self._resolve(path)
        if not cwd.is_dir():
            raise ValueError(f"Working directory '{path}' is not a directory.")

        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                shell=False,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=config.COMMAND_TIMEOUT_SECONDS,
            )
        except FileNotFoundError:
            return f"Error: command not found: {command[0]}"
        except subprocess.TimeoutExpired as error:
            output = (error.stdout or "")
            if isinstance(output, bytes):
                output = output.decode("utf-8", errors="replace")
            return f"Timed out after {config.COMMAND_TIMEOUT_SECONDS} seconds.\n{output[:config.COMMAND_OUTPUT_LIMIT]}"

        output = completed.stdout or "(no output)"
        if len(output) > config.COMMAND_OUTPUT_LIMIT:
            output = output[:config.COMMAND_OUTPUT_LIMIT] + "\n[Output truncated.]"
        return f"Exit code: {completed.returncode}\n{output}"

    def _detect_test_command(self, directory: Path) -> list[str] | None:
        """Return the safest conventional test command for a project directory."""
        package_file = directory / "package.json"
        if package_file.is_file():
            try:
                package = json.loads(package_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError as error:
                raise ValueError(f"Could not parse package.json: {error.msg}") from error
            if isinstance(package.get("scripts"), dict) and isinstance(
                package["scripts"].get("test"), str
            ):
                return ["npm", "test"]

        pytest_configs = ("pytest.ini", "tox.ini")
        if any((directory / name).is_file() for name in pytest_configs):
            return ["python", "-m", "pytest"]

        pyproject = directory / "pyproject.toml"
        if pyproject.is_file() and "pytest" in pyproject.read_text(encoding="utf-8").lower():
            return ["python", "-m", "pytest"]

        if (directory / "tests").is_dir():
            return ["python", "-m", "unittest", "discover", "-s", "tests"]

        if any(directory.glob("test_*.py")):
            return ["python", "-m", "unittest", "discover"]

        return None

    def run_tests(self, path: str = ".") -> str:
        """Detect and run a project's conventional test command."""
        directory = self._resolve(path)
        if not directory.is_dir():
            raise ValueError(f"Working directory '{path}' is not a directory.")

        command = self._detect_test_command(directory)
        if command is None:
            return (
                "No supported test setup was found. Add a tests/ directory, a pytest "
                "configuration, or a package.json test script, or use run_command."
            )

        rendered_command = " ".join(command)
        return f"Detected test command: {rendered_command}\n{self.run_command(command, path)}"
