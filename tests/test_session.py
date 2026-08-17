"""Tests for durable project-local agent sessions."""

import tempfile
import unittest
from pathlib import Path

from agent_pkg.session import SessionStore


class SessionStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = SessionStore(Path(self.temp_dir.name))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_saves_and_loads_history(self):
        history = [{"role": "user", "content": "Remember this task."}]

        self.store.save(history)

        self.assertEqual(history, self.store.load())

    def test_missing_or_malformed_session_loads_as_empty(self):
        self.assertEqual([], self.store.load())
        self.store.path.write_text("not JSON", encoding="utf-8")

        self.assertEqual([], self.store.load())

    def test_clears_saved_session(self):
        self.store.save([{"role": "user", "content": "temporary"}])

        self.assertTrue(self.store.clear())
        self.assertFalse(self.store.path.exists())
        self.assertFalse(self.store.clear())
