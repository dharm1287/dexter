"""The agent loop itself: sends messages to Groq, executes any requested
tool calls, and feeds results back until the model is done responding."""

import json

from groq import Groq

from . import config
from .schema import TOOLS, SYSTEM_PROMPT
from .tools import ProjectTools


def dispatch_tool_call(tools: ProjectTools, name: str, arguments: dict) -> str:
    """Run the requested tool and return its string result."""
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
    """Send one user message through the agent loop, mutating and
    returning the updated conversation history."""
    history.append({"role": "user", "content": user_message})

    for _ in range(config.MAX_TOOL_ITERATIONS):
        response = client.chat.completions.create(
            model=config.MODEL,
            max_tokens=config.MAX_TOKENS,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history,
            tools=TOOLS,
            tool_choice="auto",
        )

        message = response.choices[0].message

        history.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": (
                    [tc.model_dump() for tc in message.tool_calls]
                    if message.tool_calls
                    else None
                ),
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
