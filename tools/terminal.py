import shlex
import subprocess
from pathlib import Path


BLOCKED_COMMANDS = {
    "sudo",
    "shutdown",
    "reboot",
    "poweroff",
    "halt",
    "mkfs",
    "fdisk",
    "parted",
}


SAFE_COMMANDS = {
    "pwd",
    "ls",
    "find",
    "which",
    "whoami",
    "id",
    "uname",
    "date",
    "git",
    "python",
    "python3",
    "pip",
    "pip3",
    "nvidia-smi",
    "ollama",
}


def classify_command(command: str) -> str:
    """
    Classify a terminal command.

    Returns:
        SAFE
        CONFIRM
        BLOCK
    """

    try:
        parts = shlex.split(command)
    except ValueError:
        return "BLOCK"

    if not parts:
        return "BLOCK"

    executable = Path(parts[0]).name.lower()

    # Never allow shell execution tricks.
    dangerous_shell_tokens = [
        ";",
        "&&",
        "||",
        "|",
        ">",
        ">>",
        "<",
        "`",
        "$(",
    ]

    if any(token in command for token in dangerous_shell_tokens):
        return "CONFIRM"

    if executable in BLOCKED_COMMANDS:
        return "BLOCK"

    if executable in SAFE_COMMANDS:
        return "SAFE"

    return "CONFIRM"


def run_terminal(command: str, cwd: str = "~") -> str:
    """
    Execute a terminal command.

    The command itself is classified before execution.
    Dangerous commands are blocked.
    Commands that are not explicitly safe require confirmation
    through the Agent permission layer.
    """

    command = command.strip()

    if not command:
        return "No command was provided."

    classification = classify_command(command)

    if classification == "BLOCK":
        return (
            "BLOCKED: This command is considered too dangerous "
            "for Tarō to execute."
        )

    working_directory = Path(cwd).expanduser().resolve()

    if not working_directory.exists():
        return f"Working directory does not exist: {working_directory}"

    if not working_directory.is_dir():
        return f"Working directory is not a directory: {working_directory}"

    try:
        parts = shlex.split(command)

        result = subprocess.run(
            parts,
            cwd=working_directory,
            capture_output=True,
            text=True,
            timeout=30,
        )

    except FileNotFoundError:
        return f"Command not found: {command}"

    except subprocess.TimeoutExpired:
        return "Command timed out after 30 seconds."

    except PermissionError:
        return "Permission denied while executing the command."

    except Exception as error:
        return f"Terminal error: {error}"

    output = result.stdout.strip()
    error = result.stderr.strip()

    response = f"Exit code: {result.returncode}"

    if output:
        response += f"\n\nSTDOUT:\n{output}"

    if error:
        response += f"\n\nSTDERR:\n{error}"

    return response

