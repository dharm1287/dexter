#!/usr/bin/env python3
"""
A simple coding agent powered by the Groq API.

The agent can read and write files within a chosen project directory,
using tool-calling in a loop until the task is done. See agent_pkg/ for
the implementation, split into config, tools, schema, and core modules.

Setup:
    pip install groq python-dotenv --break-system-packages
    Create a .env file next to this script containing:
        GROQ_API_KEY=gsk_your_key_here
    (or export GROQ_API_KEY as a regular environment variable instead)

Usage:
    python agent.py /path/to/project
    (then type instructions at the prompt; Ctrl+C or "exit" to quit)
"""

from agent_pkg.cli import main

if __name__ == "__main__":
    main()
