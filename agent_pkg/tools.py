"""File tools sandboxed to a single project directory."""

from pathlib import Path


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
