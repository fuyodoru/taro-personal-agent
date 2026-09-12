import subprocess
from pathlib import Path


def git_status(path: str = "~") -> str:
    """
    Check whether a directory is a Git repository.

    Args:
        path: Directory to inspect.
    """

    directory = Path(path).expanduser().resolve()

    if not directory.exists():
        return f"Directory does not exist: {directory}"

    if not directory.is_dir():
        return f"Not a directory: {directory}"

    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(directory),
                "rev-parse",
                "--is-inside-work-tree",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

    except FileNotFoundError:
        return "Git is not installed or could not be found."

    except subprocess.TimeoutExpired:
        return "Git status check timed out."

    except PermissionError:
        return f"Permission denied: {directory}"

    except OSError as error:
        return f"Git error: {error}"

    if result.returncode != 0:
        return f"Git repository: NO\nPath: {directory}"

    try:
        branch_result = subprocess.run(
            [
                "git",
                "-C",
                str(directory),
                "branch",
                "--show-current",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

    except Exception:
        branch_result = None

    branch = ""

    if branch_result and branch_result.returncode == 0:
        branch = branch_result.stdout.strip()

    response = (
        f"Git repository: YES\n"
        f"Path: {directory}"
    )

    if branch:
        response += f"\nBranch: {branch}"

    return response
