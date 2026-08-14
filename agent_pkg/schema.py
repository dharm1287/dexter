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
            "name": "patch_file",
            "description": "Apply a unified diff to an existing file. Use this for small, targeted edits instead of rewriting a whole file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path of the file to edit."},
                    "patch": {
                        "type": "string",
                        "description": "Unified diff containing one or more @@ hunks. File headers are optional.",
                    },
                },
                "required": ["path", "patch"],
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
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run an approved test, lint, build, or read-only Git command in the project. Commands are argument arrays, not shell strings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "For example: [\"python\", \"-m\", \"pytest\"] or [\"npm\", \"run\", \"build\"].",
                    },
                    "path": {
                        "type": "string",
                        "description": "Relative working directory, defaults to the project root.",
                    },
                },
                "required": ["command"],
            },
        },
    },
]

SYSTEM_PROMPT = (
    "You are a careful, concise coding agent. You have tools to list, read, "
    "and edit files with targeted unified diffs, plus a limited command tool "
    "for tests, linters, builds, and read-only Git inspection. Use them as needed to "
    "understand existing code before changing it. Explain briefly what you "
    "did after finishing. Prefer patch_file for focused edits to existing files; "
    "use write_file for new files or complete replacements. Use run_command after changes when a "
    "relevant permitted test or check is available."
)
