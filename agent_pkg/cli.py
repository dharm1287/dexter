"""Command-line entry point: sets up the agent and runs the interactive
read-eval-print loop."""

import argparse

from groq import Groq

from . import config
from .core import propose_plan, run_agent
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
    parser.add_argument(
        "--approval-mode",
        action="store_true",
        help="Require approval of a plan before the agent can act on each instruction.",
    )
    args = parser.parse_args()

    config.require_api_key()

    client = Groq()
    tools = ProjectTools(args.project_dir)
    session = SessionStore(tools.root)
    history = [] if args.new_session else session.load()
    approval_mode = args.approval_mode

    print(f"Coding agent ready. Project directory: {tools.root}")
    if history:
        print(f"Restored {len(history)} messages from the previous session.")
    print(
        "Type an instruction, '/reset' to forget this session, '/approval' to toggle "
        "plan approval, or 'exit' to quit.\n"
    )

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
        if user_message == "/approval":
            approval_mode = not approval_mode
            print(f"Plan approval mode is now {'on' if approval_mode else 'off'}.\n")
            continue
        if not user_message:
            continue

        if approval_mode:
            try:
                plan = propose_plan(client, history, user_message)
            except Exception as error:
                print(f"\n[Error] Could not create a plan: {error}\n")
                continue

            print(f"\nPlan:\n{plan}\n")
            try:
                approved = input("Apply this plan? [y/N]: ").strip().lower() in {"y", "yes"}
            except (KeyboardInterrupt, EOFError):
                print("\nPlan not approved.\n")
                continue
            if not approved:
                print("Plan not approved; no project actions were taken.\n")
                continue

            history.extend(
                [
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": f"Plan:\n{plan}"},
                    {
                        "role": "user",
                        "content": "The plan above is approved. Execute it now.",
                    },
                ]
            )
            history = run_agent(client, tools, None, history)
        else:
            history = run_agent(client, tools, user_message, history)
        session.save(history)
