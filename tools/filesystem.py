from pathlib import Path


def resolve_path(path: str = "~") -> Path:
    """
    Resolve a user-provided path safely.
    """

    path = str(path).strip()

    # Explicit home-relative path
    if path.startswith("~"):
        return Path(path).expanduser().resolve()

    candidate = Path(path).expanduser()

    # Existing absolute path
    if candidate.is_absolute() and candidate.exists():
        return candidate.resolve()

    # If the model gives something like /taro,
    # try ~/taro.
    if candidate.is_absolute():
        home_candidate = Path.home() / candidate.relative_to("/")

        if home_candidate.exists():
            return home_candidate.resolve()

        # If the model gives /home/wrong-user/...
        parts = candidate.parts

        if len(parts) >= 3 and parts[1] == "home":
            relative_parts = parts[3:]
            home_candidate = Path.home().joinpath(*relative_parts)

            if home_candidate.exists():
                return home_candidate.resolve()

    # Relative paths are resolved from the user's home directory.
    return (Path.home() / candidate).resolve()


def list_directory(path: str = "~") -> str:
    """
    List the contents of a directory.

    Args:
        path: The directory to inspect.
    """

    directory = resolve_path(path)

    if not directory.exists():
        return f"Directory does not exist: {directory}"

    if not directory.is_dir():
        return f"Not a directory: {directory}"

    items = []

    for item in sorted(
        directory.iterdir(),
        key=lambda x: (not x.is_dir(), x.name.lower())
    ):
        if item.is_dir():
            items.append(f"[DIR]  {item.name}")
        else:
            items.append(f"[FILE] {item.name}")

    if not items:
        return f"The directory is empty: {directory}"

    return f"Contents of {directory}:\n" + "\n".join(items)


def read_file(path: str) -> str:
    """
    Read the contents of a text file.

    Args:
        path: The path to the file.
    """

    file_path = resolve_path(path)

    if not file_path.exists():
        return f"File does not exist: {file_path}"

    if not file_path.is_file():
        return f"Not a file: {file_path}"

    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"Cannot read this file as UTF-8 text: {file_path}"
    except PermissionError:
        return f"Permission denied: {file_path}"
    except OSError as error:
        return f"Could not read file: {error}"

    return f"Contents of {file_path}:\n\n{content}"


def search_files(query: str, path: str = "~") -> str:
    """
    Search for files and directories by name.

    Args:
        query: Text to search for in file or directory names.
        path: Directory to search inside.
    """

    root = resolve_path(path)

    if not root.exists():
        return f"Directory does not exist: {root}"

    if not root.is_dir():
        return f"Not a directory: {root}"

    query = query.lower().strip()

    if not query:
        return "Search query cannot be empty."

    results = []

    try:
        for item in root.rglob("*"):
            relative_parts = item.relative_to(root).parts

            if any(
                part.startswith(".") or part == ".venv"
                for part in relative_parts
            ):
                continue

            if query in item.name.lower():
                item_type = "DIR" if item.is_dir() else "FILE"
                results.append(f"[{item_type}] {item}")

            if len(results) >= 50:
                break

    except PermissionError:
        return f"Permission denied while searching: {root}"
    except OSError as error:
        return f"Search error: {error}"

    if not results:
        return f"No files or directories matching '{query}' were found in {root}."

    result_text = "\n".join(results)

    if len(results) >= 50:
        result_text += "\n\n[Search limited to 50 results.]"

    return f"Search results for '{query}' in {root}:\n{result_text}"