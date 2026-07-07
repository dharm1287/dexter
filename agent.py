#!/usr/bin/env python3
"""
A simple coding agent powered by the Groq API.

The agent can read and write files within a chosen project directory,
using tool-calling in a loop until the task is done.

Setup:
    pip install groq python-dotenv --break-system-packages
    Create a .env file next to this script containing:
        GROQ_API_KEY=gsk_your_key_here
    (or export GROQ_API_KEY as a regular environment variable instead)

Usage:
    python agent.py /path/to/project
    (then type instructions at the prompt; Ctrl+C or "exit" to quit)
"""

import os
import sys
import json
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

# Load variables from a .env file in the current directory (if present).
load_dotenv()

MODEL = "llama-3.3-70b-versatile"
MAX_TOKENS = 4096
MAX_TOOL_ITERATIONS = 15  # safety cap so a stuck loop can't run forever


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

class ProjectTools:
    """File tools sandboxed to a single project directory."""

    def __init__(self, project_dir: str):
        self.root = Path(project_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, rel_path: str) -> Path:
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


# ---------------------------------------------------------------------------
# Tool schema (OpenAI-style "function" format, used by Groq's API)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List all files in the project directory (or a subdirectory).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to list, defaults to project root.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the full contents of a file in the project directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path to read."}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a file in the project directory with the given content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path to write."},
                    "content": {"type": "string", "description": "Full content to write to the file."},
                },
                "required": ["path", "content"],
            },
        },
    },
]

SYSTEM_PROMPT = (
    "You are a careful, concise coding agent. You have tools to list, read, "
    "and write files inside a project directory. Use them as needed to "
    "understand existing code before changing it. Explain briefly what you "
    "did after finishing. Always write complete, working file contents when "
    "using write_file (no partial diffs)."
)


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

def dispatch_tool_call(tools: ProjectTools, name: str, arguments: dict) -> str:
    try:
        if name == "list_files":
            return tools.list_files(arguments.get("path", "."))
        elif name == "read_file":
            return tools.read_file(arguments["path"])
        elif name == "write_file":
            return tools.write_file(arguments["path"], arguments["content"])
        else:
            return f"Error: unknown tool '{name}'"
    except Exception as e:
        return f"Error running tool '{name}': {e}"


def run_agent(client: Groq, tools: ProjectTools, user_message: str, history: list) -> list:
    history.append({"role": "user", "content": user_message})

    for _ in range(MAX_TOOL_ITERATIONS):
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history,
            tools=TOOLS,
            tool_choice="auto",
        )

        message = response.choices[0].message

        history.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [tc.model_dump() for tc in message.tool_calls] if message.tool_calls else None,
            }
        )

        if message.content:
            print(f"\nAgent: {message.content}")

        if not message.tool_calls:
            break  # Model is done for this turn.

        for tool_call in message.tool_calls:
            name = tool_call.function.name
            try:
                arguments = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                arguments = {}

            print(f"  [tool call] {name}({arguments})")
            result = dispatch_tool_call(tools, name, arguments)

            history.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )
    else:
        print("\n[Stopped: reached max tool-call iterations for this turn.]")

    return history


def main():
    if len(sys.argv) < 2:
        print("Usage: python agent.py /path/to/project")
        sys.exit(1)

    if not os.environ.get("GROQ_API_KEY"):
        print(
            "Error: GROQ_API_KEY is not set.\n"
            "Either export it as an environment variable, or create a .env "
            "file next to this script containing:\n"
            "    GROQ_API_KEY=gsk_your_key_here"
        )
        sys.exit(1)

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


if __name__ == "__main__":
    main()