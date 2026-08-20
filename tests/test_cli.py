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
            tools.read_only = False
            session = MagicMock()
            session.load.return_value = []

            with (
                patch.object(cli.config, "require_api_key") as require_api_key,
                patch.object(cli, "Groq"),
                patch.object(cli, "ProjectTools", return_value=tools),
                patch.object(cli, "SessionStore", return_value=session),
                patch.object(cli, "propose_plan", return_value="1. Inspect files"),
                patch.object(cli, "run_agent") as run_agent,
                patch("sys.argv", ["agent.py", "--approval-mode", directory]),
                patch("builtins.input", side_effect=["Make a change", "n", "exit"]),
            ):
                cli.main()

        require_api_key.assert_called_once()
        run_agent.assert_not_called()
        session.save.assert_not_called()

    def test_auto_approve_executes_without_a_confirmation_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            tools = MagicMock()
            tools.root = Path(directory)
            tools.read_only = False
            session = MagicMock()
            session.load.return_value = []

            with (
                patch.object(cli.config, "require_api_key"),
                patch.object(cli, "Groq"),
                patch.object(cli, "ProjectTools", return_value=tools),
                patch.object(cli, "SessionStore", return_value=session),
                patch.object(cli, "propose_plan", return_value="1. Inspect files"),
                patch.object(cli, "run_agent", return_value=[]) as run_agent,
                patch("sys.argv", ["agent.py", "--auto-approve", directory]),
                patch("builtins.input", side_effect=["Make a change", "exit"]) as user_input,
            ):
                cli.main()

        run_agent.assert_called_once()
        self.assertEqual(["You: ", "You: "], [call.args[0] for call in user_input.call_args_list])
