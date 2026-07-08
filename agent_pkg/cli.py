"""Command-line entry point: sets up the agent and runs the interactive
read-eval-print loop."""

import sys

from groq import Groq

from . import config
from .core import run_agent
from .tools import ProjectTools


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python agent.py /path/to/project")
        sys.exit(1)

    config.require_api_key()

    project_dir = sys.argv[1]
    client = Groq()
    tools = ProjectTools(project_dir)
    history = []

    print(f"Coding agent ready. Project directory: {tools.root}")
    print("Type an instruction, or 'exit' to quit.\n")

    while True:
        try:
            user_message = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye.")
            break

        if user_message.lower() in ("exit", "quit"):
            break
        if not user_message:
            continue

        history = run_agent(client, tools, user_message, history)
