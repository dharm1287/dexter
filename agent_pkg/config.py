"""Configuration and environment setup for the coding agent."""

import os

from dotenv import load_dotenv

# Load variables from a .env file in the current directory (if present).
load_dotenv()

# Groq recommends GPT-OSS 120B as the replacement for the deprecated
# llama-3.3-70b-versatile model. Override this per environment when needed,
# for example: GROQ_MODEL=qwen/qwen3.6-27b
MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
MAX_TOKENS = 4096
MAX_TOOL_ITERATIONS = 15  # safety cap so a stuck loop can't run forever
DEFAULT_TEMPERATURE = 0.2  # lower temperature = more reliable tool-call formatting
TOOL_CALL_RETRY_TEMPERATURE = 0.0  # used when a tool call fails to parse
MAX_TOOL_CALL_RETRIES = 2

# Commands executed by the agent are intentionally short lived and their output
# is capped so a noisy test suite cannot flood the conversation history.
COMMAND_TIMEOUT_SECONDS = 120
COMMAND_OUTPUT_LIMIT = 30_000

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")


def require_api_key() -> None:
    """Exit with a clear message if GROQ_API_KEY isn't set."""
    if not GROQ_API_KEY:
        raise SystemExit(
            "Error: GROQ_API_KEY is not set.\n"
            "Either export it as an environment variable, or create a .env "
            "file next to this script containing:\n"
            "    GROQ_API_KEY=gsk_your_key_here"
        )
