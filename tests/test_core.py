"""Tests for planning and agent-loop message handling."""

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agent_pkg.core import propose_plan, run_agent


class PlanningTests(unittest.TestCase):
    def test_propose_plan_disables_tools_and_includes_request(self):
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="1. Inspect files", tool_calls=None))]
        )

        with patch("agent_pkg.core._create_completion_with_retry", return_value=response) as create:
            plan = propose_plan(object(), [{"role": "user", "content": "Earlier"}], "Add tests")

        self.assertEqual("1. Inspect files", plan)
        self.assertFalse(create.call_args.kwargs["enable_tools"])
        self.assertEqual("Add tests", create.call_args.args[1][-1]["content"])

    def test_run_agent_does_not_duplicate_pre_recorded_request(self):
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Done", tool_calls=None))]
        )
        history = [{"role": "user", "content": "Already approved"}]

        with patch("agent_pkg.core._create_completion_with_retry", return_value=response):
            updated = run_agent(object(), object(), None, history)

        self.assertEqual("Already approved", updated[0]["content"])
        self.assertEqual(2, len(updated))
        self.assertEqual("assistant", updated[-1]["role"])
