"""Command-line entry point: sets up the agent and runs the interactive
read-eval-print loop."""

import argparse

from groq import Groq

from . import config
from .core import run_agent
from .session import SessionStore
from .tools import ProjectTools


def main() -> None:
    parser = argparse.ArgumentParser(description="A lightweight Groq-powered coding agent.")
    parser.add_argument("project_dir", help="Directory the agent may inspect and edit.")
    parser.add_argument(
        "--new-session",
        action="store_true",
        help="Start without restoring the saved conversation for this project.",
    )
    args = parser.parse_args()

    config.require_api_key()

    client = Groq()
    tools = ProjectTools(args.project_dir)
    session = SessionStore(tools.root)
    history = [] if args.new_session else session.load()

    print(f"Coding agent ready. Project directory: {tools.root}")
    if history:
        print(f"Restored {len(history)} messages from the previous session.")
    print("Type an instruction, '/reset' to forget this session, or 'exit' to quit.\n")

    while True:
        try:
            user_message = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye.")
            break

        if user_message.lower() in ("exit", "quit"):
            break
        if user_message == "/reset":
            history = []
            if session.clear():
                print("Session cleared.\n")
            else:
                print("No saved session to clear.\n")
            continue
        if not user_message:
            continue

        history = run_agent(client, tools, user_message, history)
        session.save(history)
