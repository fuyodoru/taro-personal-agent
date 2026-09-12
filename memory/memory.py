import json
import math
from datetime import datetime
from pathlib import Path

import ollama


# ==========================================================
# CONFIGURATION
# ==========================================================

MEMORY_FILE = Path(__file__).parent / "memories.json"

EMBEDDING_MODEL = "nomic-embed-text"

# Similarity threshold.
#
# Higher = stricter matching
# Lower  = more memories returned
#
# 0.60 is a reasonable starting point.
SIMILARITY_THRESHOLD = 0.60

# Maximum number of semantic memories returned.
MAX_RESULTS = 5


# ==========================================================
# FILE HANDLING
# ==========================================================

def _load_memories() -> list[dict]:
    """
    Load memories from memories.json.
    """

    if not MEMORY_FILE.exists():
        return []

    try:
        with MEMORY_FILE.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

    except json.JSONDecodeError:
        return []

    except OSError:
        return []

    if not isinstance(data, list):
        return []

    return data


def _save_memories(memories: list[dict]) -> None:
    """
    Save memories to memories.json.
    """

    MEMORY_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_file = MEMORY_FILE.with_suffix(
        ".json.tmp"
    )

    with temporary_file.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            memories,
            file,
            ensure_ascii=False,
            indent=2,
        )

    temporary_file.replace(MEMORY_FILE)


# ==========================================================
# EMBEDDINGS
# ==========================================================

def _get_embedding(text: str) -> list[float]:
    """
    Generate an embedding for text using Ollama.
    """

    text = str(text).strip()

    if not text:
        return []

    response = ollama.embed(
        model=EMBEDDING_MODEL,
        input=text,
    )

    embeddings = response.embeddings

    if not embeddings:
        return []

    return list(embeddings[0])


# ==========================================================
# COSINE SIMILARITY
# ==========================================================

def _cosine_similarity(
    vector_a: list[float],
    vector_b: list[float],
) -> float:
    """
    Calculate cosine similarity between two vectors.

    Returns a value approximately between -1 and 1.
    Higher means more semantically similar.
    """

    if not vector_a or not vector_b:
        return 0.0

    if len(vector_a) != len(vector_b):
        return 0.0

    dot_product = sum(
        a * b
        for a, b in zip(vector_a, vector_b)
    )

    magnitude_a = math.sqrt(
        sum(a * a for a in vector_a)
    )

    magnitude_b = math.sqrt(
        sum(b * b for b in vector_b)
    )

    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0

    return dot_product / (
        magnitude_a * magnitude_b
    )


# ==========================================================
# MEMORY MIGRATION
# ==========================================================

def _ensure_embeddings(
    memories: list[dict],
) -> bool:
    """
    Make sure every memory has an embedding.

    This automatically upgrades old memories that were
    created before semantic memory existed.

    Returns:
        True if memories were modified.
    """

    changed = False

    for memory in memories:

        content = memory.get(
            "content",
            "",
        ).strip()

        if not content:
            continue

        embedding = memory.get("embedding")

        # Already has an embedding.
        if (
            isinstance(embedding, list)
            and len(embedding) > 0
        ):
            continue

        try:
            new_embedding = _get_embedding(
                content
            )

        except Exception as error:
            print(
                "Memory embedding error: "
                f"{type(error).__name__}: {error}"
            )
            continue

        if not new_embedding:
            continue

        memory["embedding"] = new_embedding

        changed = True

    return changed


def migrate_memories() -> None:
    """
    Generate embeddings for old memories.

    Safe to run multiple times.
    Existing embeddings are not regenerated.
    """

    memories = _load_memories()

    if not memories:
        return

    changed = _ensure_embeddings(
        memories
    )

    if changed:
        _save_memories(memories)


# ==========================================================
# ADD MEMORY
# ==========================================================

def add_memory(
    content: str,
    category: str = "general",
) -> str:
    """
    Add a new semantic memory.
    """

    content = str(content).strip()
    category = str(category).strip()

    if not content:
        return "Memory content cannot be empty."

    if not category:
        category = "general"

    # Generate semantic embedding.
    try:
        embedding = _get_embedding(
            content
        )

    except Exception as error:
        return (
            "Could not create memory embedding: "
            f"{type(error).__name__}: {error}"
        )

    if not embedding:
        return (
            "Could not create memory embedding."
        )

    memories = _load_memories()

    memory = {
        "content": content,
        "category": category,
        "created_at": datetime.now().isoformat(),
        "embedding": embedding,
    }

    memories.append(memory)

    try:
        _save_memories(memories)

    except OSError as error:
        return (
            f"Could not save memory: {error}"
        )

    return (
        f'Memory saved successfully: "{content}"'
    )


# ==========================================================
# GET ALL MEMORIES
# ==========================================================

def get_memories() -> list[dict]:
    """
    Return all memories.

    Embeddings are hidden from the returned data because
    the LLM does not need to see the raw vectors.
    """

    memories = _load_memories()

    # Make sure old memories are upgraded.
    changed = _ensure_embeddings(
        memories
    )

    if changed:
        _save_memories(memories)

    cleaned = []

    for memory in memories:

        cleaned.append({
            "content": memory.get(
                "content",
                "",
            ),
            "category": memory.get(
                "category",
                "general",
            ),
            "created_at": memory.get(
                "created_at",
                "",
            ),
        })

    return cleaned


# ==========================================================
# SEMANTIC MEMORY SEARCH
# ==========================================================

def search_memories(
    query: str,
    limit: int = MAX_RESULTS,
    threshold: float = SIMILARITY_THRESHOLD,
) -> list[dict]:
    """
    Search memories semantically.

    Example:

        search_memories(
            "I want to learn programming"
        )

    can find:

        "Python öğrenmek istiyorum"

    even if the words are different.
    """

    query = str(query).strip()

    if not query:
        return []

    memories = _load_memories()

    if not memories:
        return []

    # ------------------------------------------------------
    # Make sure old memories have embeddings.
    # ------------------------------------------------------

    changed = _ensure_embeddings(
        memories
    )

    if changed:
        _save_memories(memories)

    # ------------------------------------------------------
    # Embed the user's query.
    # ------------------------------------------------------

    try:
        query_embedding = _get_embedding(
            query
        )

    except Exception as error:
        print(
            "Memory search embedding error: "
            f"{type(error).__name__}: {error}"
        )
        return []

    if not query_embedding:
        return []

    # ------------------------------------------------------
    # Compare query against every memory.
    # ------------------------------------------------------

    scored_memories = []

    for memory in memories:

        embedding = memory.get(
            "embedding"
        )

        if not isinstance(
            embedding,
            list,
        ):
            continue

        similarity = _cosine_similarity(
            query_embedding,
            embedding,
        )

        if similarity >= threshold:

            scored_memories.append({
                "content": memory.get(
                    "content",
                    "",
                ),
                "category": memory.get(
                    "category",
                    "general",
                ),
                "created_at": memory.get(
                    "created_at",
                    "",
                ),
                "similarity": similarity,
            })

    # ------------------------------------------------------
    # Highest similarity first.
    # ------------------------------------------------------

    scored_memories.sort(
        key=lambda memory: memory["similarity"],
        reverse=True,
    )

    return scored_memories[:limit]

# ==========================================================
# DELETE MEMORY
# ==========================================================

def delete_memory(
    content: str,
) -> str:
    """
    Delete memories matching the exact content.
    """

    content = str(content).strip()

    if not content:
        return "Memory content cannot be empty."

    memories = _load_memories()

    if not memories:
        return "No memories found."

    original_count = len(memories)

    memories = [
        memory
        for memory in memories
        if memory.get("content", "").strip() != content
    ]

    deleted_count = (
        original_count - len(memories)
    )

    if deleted_count == 0:
        return (
            f'No memory found with content: "{content}"'
        )

    try:
        _save_memories(memories)

    except OSError as error:
        return (
            f"Could not save memories: {error}"
        )

    return (
        f'Deleted {deleted_count} memory '
        f'entry: "{content}"'
    )


# ==========================================================
# INITIAL MIGRATION
# ==========================================================
# ==========================================================
# INITIAL MIGRATION
# ==========================================================

# When this module is imported, old memories are upgraded.
try:
    migrate_memories()
except Exception:
    pass