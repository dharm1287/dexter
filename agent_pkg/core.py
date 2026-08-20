"""The agent loop itself: sends messages to Groq, executes any requested
tool calls, and feeds results back until the model is done responding."""

import json
from typing import Optional

import groq
from groq import Groq

from . import config
from .schema import TOOLS, SYSTEM_PROMPT
from .tools import ProjectTools


PLANNING_PROMPT = """You are preparing a coding plan for approval. Do not use tools or
claim that you inspected files. Respond with a concise plan of 3-6 numbered steps,
including expected files to inspect or change, validation, and any assumptions or
risks. Do not begin implementation; wait for explicit approval."""


def _text_only_history(history: list) -> list:
    """Convert native tool messages into plain chat context for recovery."""
    text_history = []
    for message in history:
        role = message["role"]
        content = message.get("content") or ""

        if role == "tool":
            text_history.append(
                {"role": "user", "content": f"Tool result from earlier work:\n{content}"}
            )
        elif role in ("user", "assistant") and content:
            text_history.append({"role": role, "content": content})
    return text_history


def dispatch_tool_call(tools: ProjectTools, name: str, arguments: dict) -> str:
    """Run the requested tool and return its string result."""
    try:
        if name == "list_files":
            return tools.list_files(arguments.get("path", "."))
        elif name == "find_files":
            return tools.find_files(arguments["query"], arguments.get("path", "."))
        elif name == "search_code":
            return tools.search_code(
                arguments["query"],
                arguments.get("path", "."),
                arguments.get("case_sensitive", False),
            )
        elif name == "read_file":
            return tools.read_file(arguments["path"])
        elif name == "write_file":
            return tools.write_file(arguments["path"], arguments["content"])
        elif name == "patch_file":
            return tools.patch_file(arguments["path"], arguments["patch"])
        elif name == "run_command":
            return tools.run_command(arguments["command"], arguments.get("path", "."))
        elif name == "run_tests":
            return tools.run_tests(arguments.get("path", "."))
        else:
            return f"Error: unknown tool '{name}'"
    except Exception as e:
        return f"Error running tool '{name}': {e}"


def _create_completion_with_retry(client: Groq, messages: list, *, enable_tools: bool = True):
    """Call the Groq chat completion API, retrying at a lower temperature
    if the model emits a malformed tool call (a known occasional issue
    with some models, surfaced by Groq as a 400 tool_use_failed error)."""
    temperature = config.DEFAULT_TEMPERATURE
    last_error = None

    for attempt in range(1 + config.MAX_TOOL_CALL_RETRIES):
        try:
            request = {
                "model": config.MODEL,
                "max_tokens": config.MAX_TOKENS,
                "temperature": temperature,
                "messages": messages,
            }
            if enable_tools:
                request.update(
                    tools=TOOLS,
                    tool_choice="auto",
                    # Keep tool requests serial: the default model does not support
                    # parallel tool calls, and this also keeps file operations ordered.
                    parallel_tool_calls=False,
                )
            return client.chat.completions.create(**request)
        except groq.BadRequestError as e:
            if not enable_tools:
                raise
            body = getattr(e, "body", None) or {}
            code = (body.get("error") or {}).get("code") if isinstance(body, dict) else None
            if code != "tool_use_failed":
                raise  # a different kind of error; don't swallow it

            last_error = e
            temperature = config.TOOL_CALL_RETRY_TEMPERATURE
            print(
                f"  [warning] model produced a malformed tool call, "
                f"retrying (attempt {attempt + 2}/{1 + config.MAX_TOOL_CALL_RETRIES})..."
            )

    raise last_error


def propose_plan(client: Groq, history: list, user_message: str) -> str:
    """Generate a tool-free implementation plan for the user's approval."""
    response = _create_completion_with_retry(
        client,
        [{"role": "system", "content": PLANNING_PROMPT}]
        + _text_only_history(history)
        + [{"role": "user", "content": user_message}],
        enable_tools=False,
    )
    return response.choices[0].message.content or "No plan was returned."


def run_agent(
    client: Groq, tools: ProjectTools, user_message: Optional[str], history: list
) -> list:
    """Send one user message through the agent loop, mutating and
    returning the updated conversation history. Pass None when the user's
    request has already been recorded, such as after approval mode planning."""
    if user_message is not None:
        history.append({"role": "user", "content": user_message})

    system_prompt = SYSTEM_PROMPT
    if getattr(tools, "read_only", False):
        system_prompt += " This is a read-only session: do not attempt edits or commands."

    for _ in range(config.MAX_TOOL_ITERATIONS):
        try:
            response = _create_completion_with_retry(
                client, [{"role": "system", "content": system_prompt}] + history
            )
        except groq.BadRequestError:
            # The conversation itself may still be answerable without another
            # file operation. Fall back to text-only mode instead of losing the
            # user's turn when the provider rejects malformed tool-call JSON.
            print("\n[warning] Tool-call formatting failed; retrying without tools.")
            fallback_prompt = (
                system_prompt
                + " The tool interface is temporarily unavailable. Do not attempt "
                "to use tools. Answer only from the conversation context; if the "
                "request requires inspecting or changing files, say that clearly."
            )
            try:
                response = _create_completion_with_retry(
                    client,
                    [{"role": "system", "content": fallback_prompt}]
                    + _text_only_history(history),
                    enable_tools=False,
                )
            except groq.BadRequestError:
                print("\n[Error] The model could not complete this request. Try again.")
                break

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
