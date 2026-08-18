"""Tests for the approval-mode CLI gate."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from agent_pkg import cli


class ApprovalModeTests(unittest.TestCase):
    def test_declined_plan_never_reaches_agent_loop(self):
        with tempfile.TemporaryDirectory() as directory:
            tools = MagicMock()
            tools.root = Path(directory)
            session = MagicMock()
            session.load.return_value = []

            with (
                patch.object(cli, "config") as config,
                patch.object(cli, "Groq"),
                patch.object(cli, "ProjectTools", return_value=tools),
                patch.object(cli, "SessionStore", return_value=session),
                patch.object(cli, "propose_plan", return_value="1. Inspect files"),
                patch.object(cli, "run_agent") as run_agent,
                patch("sys.argv", ["agent.py", "--approval-mode", directory]),
                patch("builtins.input", side_effect=["Make a change", "n", "exit"]),
            ):
                cli.main()

        config.require_api_key.assert_called_once()
        run_agent.assert_not_called()
        session.save.assert_not_called()
