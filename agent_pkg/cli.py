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
    parser.add_argument("--auto-approve", action="store_true", help="Show each plan and approve it automatically.")
    parser.add_argument("--model", help="Override the Groq model for this launch.")
    parser.add_argument("--temperature", type=float, help="Sampling temperature from 0.0 to 2.0.")
    parser.add_argument("--max-iterations", type=int, help="Maximum tool-call loops per instruction.")
    parser.add_argument(
        "--read-only",
        action="store_true",
        help="Disable edits and commands; allow only project inspection and search.",
    )
    args = parser.parse_args()
    if args.temperature is not None and not 0.0 <= args.temperature <= 2.0:
        parser.error("--temperature must be between 0.0 and 2.0")
    if args.max_iterations is not None and args.max_iterations < 1:
        parser.error("--max-iterations must be at least 1")

    config.require_api_key()
    config.configure_runtime(
        model=args.model,
        temperature=args.temperature,
        max_tool_iterations=args.max_iterations,
    )

    client = Groq()
    tools = ProjectTools(args.project_dir, read_only=args.read_only)
    session = SessionStore(tools.root)
    history = [] if args.new_session else session.load()
    approval_mode = args.approval_mode or args.auto_approve

    print(f"Coding agent ready. Project directory: {tools.root}")
    if history:
        print(f"Restored {len(history)} messages from the previous session.")
    print(f"Model: {config.MODEL}; temperature: {config.DEFAULT_TEMPERATURE}; max iterations: {config.MAX_TOOL_ITERATIONS}")
    if tools.read_only:
        print("Read-only mode is enabled.")
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
            if args.auto_approve:
                approved = True
                print("Plan automatically approved.")
            else:
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
