"""Project tools sandboxed to a single project directory."""

from pathlib import Path
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
            if any(part.startswith(".git") for part in p.parts):
                continue
            entries.append(str(p.relative_to(self.root)))
        return "\n".join(entries) if entries else "(empty)"

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
