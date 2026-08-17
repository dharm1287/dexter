"""Durable, project-local conversation history for the command-line agent."""

import json
import os
from pathlib import Path
import tempfile

from . import config


class SessionStore:
    """Persist one conversation history beside the project being edited."""

    def __init__(self, project_root: Path):
        self.path = project_root / config.SESSION_FILENAME

    def load(self) -> list:
        """Load valid history, treating a missing or corrupted session as empty."""
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            history = payload.get("history")
            if not isinstance(history, list) or not all(isinstance(item, dict) for item in history):
                raise ValueError("history is not a list of messages")
            return history
        except (OSError, json.JSONDecodeError, ValueError) as error:
            print(f"[warning] Ignoring unreadable session file: {error}")
            return []

    def save(self, history: list) -> None:
        """Atomically save history so interrupted writes do not corrupt a session."""
        payload = {"version": 1, "history": history}
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=self.path.parent, delete=False
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                json.dump(payload, temporary_file, ensure_ascii=False, indent=2)
                temporary_file.write("\n")
            os.replace(temporary_path, self.path)
        except (OSError, TypeError) as error:
            print(f"[warning] Could not save session: {error}")
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def clear(self) -> bool:
        """Delete the stored session, returning whether one was removed."""
        if not self.path.exists():
            return False
        self.path.unlink()
        return True
