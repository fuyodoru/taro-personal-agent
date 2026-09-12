from dataclasses import dataclass
from typing import Callable
from tools.git import git_status

from tools.terminal import run_terminal

from tools.filesystem import (
    list_directory,
    read_file,
    search_files,
)

from memory.memory import (
    add_memory,
    get_memories,
    search_memories,
    delete_memory,
)


@dataclass
class ToolSpec:
    name: str
    function: Callable
    description: str
    parameters: dict
    risk: str
    requires_confirmation: bool


TOOLS = {
    # =========================
    # FILESYSTEM
    # =========================

    "list_directory": ToolSpec(
        name="list_directory",
        function=list_directory,
        description="List the contents of a directory.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path. Defaults to the user's home directory.",
                }
            },
            "required": [],
        },
        risk="READ",
        requires_confirmation=False,
    ),

    "read_file": ToolSpec(
        name="read_file",
        function=read_file,
        description="Read the contents of a UTF-8 text file.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path of the text file to read.",
                }
            },
            "required": ["path"],
        },
        risk="READ",
        requires_confirmation=False,
    ),

    "search_files": ToolSpec(
        name="search_files",
        function=search_files,
        description="Search for files and directories by name.",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Text to search for in file or directory names.",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search inside. Defaults to the user's home directory.",
                },
            },
            "required": ["query"],
        },
        risk="READ",
        requires_confirmation=False,
    ),
    # =========================
    # GIT
    # =========================

    "git_status": ToolSpec(
        name="git_status",
        function=git_status,
        description="Check whether a directory is a Git repository and report its current branch.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory to inspect. Defaults to the user's home directory.",
                },
            },
            "required": [],
        },
        risk="READ",
        requires_confirmation=False,
    ),
    # =========================
    # TERMINAL
    # =========================

    "run_terminal": ToolSpec(
        name="run_terminal",
        function=run_terminal,
        description="Execute a terminal command through Tarō's safety-controlled terminal layer.",
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The terminal command to execute.",
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory. Defaults to the user's home directory.",
                },
            },
            "required": ["command"],
        },
        risk="EXECUTE",
        requires_confirmation=True,
    ),

    # =========================
    # MEMORY
    # =========================

    "add_memory": ToolSpec(
        name="add_memory",
        function=add_memory,
        description="Save a piece of information to Tarō's persistent memory.",
        parameters={
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The information that should be remembered.",
                },
                "category": {
                    "type": "string",
                    "description": "Memory category, such as preference, project, personal, or general.",
                },
            },
            "required": ["content"],
        },
        risk="MEMORY_WRITE",
        requires_confirmation=True,
    ),

    "get_memories": ToolSpec(
        name="get_memories",
        function=get_memories,
        description="Retrieve all stored memories.",
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
        risk="MEMORY_READ",
        requires_confirmation=False,
    ),

    "search_memories": ToolSpec(
        name="search_memories",
        function=search_memories,
        description="Search Tarō's persistent memory using semantic similarity.",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Concept or information to search for in memory.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of memories to return.",
                },
                "threshold": {
                    "type": "number",
                    "description": "Minimum similarity score.",
                },
            },
            "required": ["query"],
        },
        risk="MEMORY_READ",
        requires_confirmation=False,
    ),

    "delete_memory": ToolSpec(
        name="delete_memory",
        function=delete_memory,
        description="Delete a stored memory matching the exact content.",
        parameters={
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Exact content of the memory to delete.",
                }
            },
            "required": ["content"],
        },
        risk="MEMORY_DELETE",
        requires_confirmation=True,
    ),
}


def get_tools():
    """
    Return tools in Anthropic's tool schema format.
    """

    return [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.parameters,
        }
        for tool in TOOLS.values()
    ]


def get_tool(name: str):
    """
    Return a tool specification by name.
    """

    return TOOLS.get(name)