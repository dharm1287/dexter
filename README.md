# My Coding Agent

A lightweight command-line coding agent powered by the [Groq API](https://console.groq.com/). Give it a project directory and an instruction; it can inspect that directory and create or update files to complete the task.

## Features

- Interactive terminal chat loop
- Groq-powered tool calling using `llama-3.3-70b-versatile`
- Sandboxed `list_files`, `read_file`, `write_file`, `patch_file`, `run_command`, and `run_tests` tools
- Approved command execution for tests, linters, builds, and read-only Git checks
- Automatic test detection for `npm test`, `pytest`, and Python `unittest`
- File access restricted to the directory supplied at launch
- Retry handling for malformed model tool calls

## Requirements

- Python 3.9 or newer
- A Groq API key

## Setup

1. Install the dependencies:

   ```bash
   pip install groq python-dotenv
   ```

2. Create a `.env` file in this repository:

   ```env
   GROQ_API_KEY=gsk_your_key_here
   ```

   Alternatively, set `GROQ_API_KEY` as an environment variable.

   The default model is `openai/gpt-oss-120b`. To use another Groq model, set
   `GROQ_MODEL`, for example:

   ```env
   GROQ_MODEL=qwen/qwen3.6-27b
   ```

## Usage

Run the agent with the directory it should work in:

```bash
python agent.py /path/to/project
```

For example:

```bash
python agent.py ./newproject
```

Then enter a task at the prompt, such as:

```text
You: Add a function that validates email addresses and create tests for it.
```

Type `exit` or `quit`, or press `Ctrl+C`, to end the session.

## How it works

`agent.py` starts the command-line interface. Each instruction is sent to Groq along with a system prompt and the conversation history. When the model requests a tool, the agent runs it and returns the result to the model. This repeats until the model responds without requesting another tool.

The implementation is organized as follows:

```text
agent.py             Application entry point
agent_pkg/
  cli.py             Interactive command-line loop
  core.py            Groq request, tool-call, and retry loop
  tools.py           Sandboxed project file operations
  schema.py          Tool definitions and system prompt
  config.py          Model and runtime configuration
```

## Safety and limits

- The agent resolves all tool paths relative to the selected project directory and rejects paths that escape it.
- It can overwrite files when the model calls `write_file`; use a version-controlled project and review changes before committing.
- `patch_file` applies unified-diff hunks to an existing file and refuses patches whose context no longer matches, preventing stale edits from being applied silently.
- `run_command` accepts an argument array rather than a shell string and only permits common test, lint, build, and read-only Git commands. It runs inside the selected project directory, times out after two minutes, and truncates large output.
- `run_tests` detects a package test script, pytest configuration, or Python test directory and runs the appropriate approved command. The agent is instructed to use its output to fix and rerun failing tests when possible.
- Each instruction is capped at 15 tool-call iterations to prevent runaway loops.
- If Groq rejects a malformed tool call, the agent retries with the prior tool
  results represented as normal conversation context. This lets context-only
  follow-ups complete; requests that need a new file operation may need to be
  retried.
- The model, token limit, temperature, and retry settings are configured in `agent_pkg/config.py`.

## License

No license has been specified for this project yet.
