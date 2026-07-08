"""Tool schema (OpenAI-style "function" format, used by Groq's API) and
the system prompt that governs the agent's behavior."""

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
