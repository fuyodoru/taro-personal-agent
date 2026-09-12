# Tarō Architecture

This document describes the internal architecture of Tarō and the interaction between the agent, Claude, memory, tools, and the permission layer.

---

## 1. High-Level Architecture

Tarō is structured around a separation between model reasoning and local execution.

Claude is responsible for interpreting the user's request and deciding whether a tool is required.

Tarō is responsible for:

- maintaining conversation state
- detecting the response language
- retrieving relevant memory
- exposing available tools
- executing tools
- enforcing permission checks
- returning tool results to Claude

The high-level flow is:

```text
                         ┌──────────────────┐
                         │       User       │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │   Tarō Agent     │
                         └────────┬─────────┘
                                  │
               ┌──────────────────┼──────────────────┐
               │                  │                  │
               ▼                  ▼                  ▼
       Language Detection   Memory Retrieval   Conversation
               │                  │                  │
               └──────────────────┼──────────────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │    Claude API    │
                         │ Anthropic Model  │
                         └────────┬─────────┘
                                  │
                         text / tool_use
                                  │
                                  ▼
                         ┌──────────────────┐
                         │ Tool Registry    │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │ Permission Layer │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │ Tool Execution   │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │   tool_result    │
                         └────────┬─────────┘
                                  │
                                  ▼
                               Claude
                                  │
                                  ▼
                            Final response
```

---

## 2. Core Components

## 2.1 Agent

Location:

```text
core/agent.py
```

The `Agent` class is the central orchestration layer.

It manages:

- conversation history
- language detection
- memory retrieval
- Claude requests
- tool execution
- permission checks
- tool result handling

The Agent owns the main interaction loop.

Conceptually:

```text
User input
    │
    ▼
Agent
    │
    ├── Detect language
    │
    ├── Retrieve relevant memory
    │
    ├── Build contextual message
    │
    └── Send request to Claude
```

---

# 3. Claude Integration

Location:

```text
brain/llm.py
```

Tarō uses the Anthropic Messages API.

The model is configured through:

```env
TARO_MODEL=claude-sonnet-4-6
```

The Anthropic API key is loaded from:

```env
ANTHROPIC_API_KEY=...
```

The API client is initialized through the Anthropic Python SDK.

The Agent passes:

- conversation messages
- tool definitions
- current response language

to Claude.

The system prompt defines Tarō's:

- personality
- language behavior
- memory behavior
- tool behavior
- filesystem rules
- terminal rules
- response style

---

# 4. Conversation State

The Agent maintains conversation history in:

```python
self.messages
```

Messages follow the Anthropic Messages API structure.

A basic conversation looks like:

```text
User
  │
  ▼
{
    "role": "user",
    "content": "..."
}
  │
  ▼
Claude
  │
  ▼
{
    "role": "assistant",
    "content": [...]
}
```

The Agent keeps the conversation state and sends the accumulated messages to Claude on subsequent turns.

---

# 5. Tool Use

Tarō uses Anthropic's tool-use mechanism.

Tools are defined in:

```text
tools/registry.py
```

Each tool has a `ToolSpec` containing:

```text
name
function
description
parameters
risk
requires_confirmation
```

The registry converts these definitions into Anthropic-compatible tool schemas.

Conceptually:

```python
{
    "name": "read_file",
    "description": "...",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string"
            }
        },
        "required": ["path"]
    }
}
```

Claude receives these definitions and can decide when one is appropriate.

---

# 6. Tool Execution Loop

When Claude responds with a `tool_use` block, the Agent does not immediately produce a final response.

Instead, it executes the tool-use loop.

```text
                  Claude
                    │
                    │ tool_use
                    ▼
              Tarō Agent
                    │
                    ▼
              Tool Registry
                    │
                    ▼
            Permission Check
                    │
             ┌──────┴──────┐
             │             │
           denied        allowed
             │             │
             │             ▼
             │       Tool Execution
             │             │
             └──────┬──────┘
                    │
                    ▼
               tool_result
                    │
                    ▼
                  Claude
                    │
                    ▼
             Final response
```

This loop can repeat if Claude requests additional tools.

---

# 7. Tool Result Handling

Anthropic requires tool results to be returned using a `tool_result` content block.

The result contains the ID of the original tool request:

```python
{
    "type": "tool_result",
    "tool_use_id": tool_use.id,
    "content": result
}
```

The Agent sends these results back to Claude as a user message.

This preserves the relationship between:

```text
tool_use
    │
    │ tool_use_id
    ▼
tool_result
```

Claude can then use the result to generate the final response or request another tool.

---

# 8. Tool Registry

Location:

```text
tools/registry.py
```

The registry provides a single place where Tarō's capabilities are defined.

Current tools:

```text
Filesystem
├── list_directory
├── read_file
└── search_files

Terminal
└── run_terminal

Memory
├── add_memory
├── get_memories
├── search_memories
└── delete_memory
```

The registry separates tool metadata from the actual implementation.

This makes tools easier to expose to Claude without giving Claude direct access to arbitrary Python functions.

---

# 9. Filesystem Layer

Location:

```text
tools/filesystem.py
```

The filesystem layer provides controlled file operations.

Current operations:

```text
list_directory
read_file
search_files
```

Paths are resolved through:

```python
resolve_path()
```

The filesystem layer handles:

- relative paths
- home-relative paths
- existing absolute paths
- missing files
- invalid directories
- permission errors
- UTF-8 decoding errors

The LLM does not directly access Python's filesystem APIs.

Instead:

```text
Claude
  │
  ▼
read_file
  │
  ▼
filesystem.py
  │
  ▼
actual filesystem
```

---

# 10. Terminal Safety Layer

Location:

```text
tools/terminal.py
```

Terminal execution is separated from the Agent itself.

Commands are classified as:

```text
SAFE
CONFIRM
BLOCK
```

The terminal layer maintains explicit lists of:

```python
SAFE_COMMANDS
BLOCKED_COMMANDS
```

Dangerous commands such as:

```text
sudo
shutdown
reboot
poweroff
halt
mkfs
fdisk
parted
```

are blocked.

Commands that are not explicitly safe require additional protection through Tarō's permission layer.

The terminal tool also:

- prevents shell chaining
- blocks shell redirection
- uses `subprocess.run`
- applies a timeout
- captures stdout
- captures stderr
- returns the process exit code

---

# 11. Permission Layer

Permission handling is implemented by the Agent.

Tools can specify:

```python
requires_confirmation=True
```

When a tool requires confirmation, Tarō displays:

```text
==================================================
Tarō Permission Request
==================================================
Tool: ...
Risk: ...
Arguments: ...

Allow this action? [y/N]:
```

The operation is executed only when the user explicitly approves it.

For example:

```text
Claude
  │
  │ run_terminal
  ▼
Tarō
  │
  ▼
Permission Request
  │
  ├── n → operation denied
  │
  └── y → operation executed
```

This creates a human-in-the-loop boundary between model decisions and potentially consequential local operations.

---

# 12. Memory Architecture

Location:

```text
memory/memory.py
```

Tarō stores persistent memories in:

```text
memory/memories.json
```

Memory entries contain information such as:

```text
content
category
created_at
embedding
```

The Agent performs memory retrieval before sending the current request to Claude.

The flow is:

```text
User request
     │
     ▼
search_memories()
     │
     ▼
Relevant memories
     │
     ▼
Memory context
     │
     ▼
Claude
```

Only relevant memories are included in the prompt.

The Agent currently limits the retrieved memory context to five entries.

---

# 13. Semantic Memory

The current memory implementation uses embeddings to perform semantic similarity search.

The memory system:

1. creates an embedding for stored memory
2. creates an embedding for the query
3. calculates cosine similarity
4. filters results using a similarity threshold
5. returns the highest-scoring memories

Conceptually:

```text
Stored memory
     │
     ▼
Embedding
     │
     ▼
Vector representation
     │
     │ cosine similarity
     │
     ▼
User query
     │
     ▼
Query embedding
```

The current embedding implementation still uses Ollama with `nomic-embed-text`.

This is separate from Tarō's language-model layer, which is powered by Claude.

A future version will replace this remaining Ollama dependency with a different memory architecture.

---

# 14. Language Detection

Location:

```text
language.py
```

Tarō detects the user's language before sending the request to Claude.

Supported languages include:

```text
English
Turkish
Italian
Japanese
German
French
Spanish
Portuguese
```

The detected language is explicitly provided to Claude as:

```text
CURRENT RESPONSE LANGUAGE
```

This prevents the model from relying solely on previous conversation language.

The language flow is:

```text
User input
    │
    ▼
Language detector
    │
    ▼
Detected language
    │
    ▼
Claude system instruction
    │
    ▼
Response in detected language
```

---

# 15. Separation of Responsibilities

One of Tarō's main architectural principles is separation of responsibilities.

### Claude

Responsible for:

- understanding natural language
- reasoning about the user's request
- deciding whether a tool is required
- selecting the appropriate tool
- interpreting tool results
- generating the final response

### Tarō

Responsible for:

- conversation state
- language detection
- memory retrieval
- tool registration
- permission checks
- tool execution
- returning tool results

### Tools

Responsible for:

- filesystem operations
- terminal operations
- memory operations

This separation prevents the model from being treated as an unrestricted execution layer.

---

# 16. Example: Filesystem Request

Suppose the user asks:

```text
What files are in my home directory?
```

The sequence is:

```text
1. User
      │
      ▼
2. Tarō Agent
      │
      ├── detect language
      ├── search memory
      └── build context
      │
      ▼
3. Claude
      │
      │ tool_use
      ▼
4. list_directory
      │
      ▼
5. Filesystem
      │
      ▼
6. Tool result
      │
      ▼
7. Claude
      │
      ▼
8. Final response
```

No manual filesystem command is required from the user.

---

# 17. Example: Protected Terminal Request

Suppose the user asks:

```text
Run pwd in the terminal.
```

The sequence is:

```text
User
  │
  ▼
Claude
  │
  │ tool_use: run_terminal
  ▼
Tarō
  │
  ▼
Permission Layer
  │
  ├── denied ──► tool_result
  │
  └── approved
          │
          ▼
      terminal.py
          │
          ▼
       stdout
          │
          ▼
      tool_result
          │
          ▼
        Claude
          │
          ▼
    Final response
```

The model can request the operation, but the Agent controls whether the operation is actually performed.

---

# 18. Current Architecture Summary

```text
┌─────────────────────────────────────────────────────────────┐
│                           USER                              │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                         TARŌ AGENT                          │
│                                                             │
│  ┌─────────────────┐     ┌──────────────────────────────┐   │
│  │ Language        │     │ Memory Retrieval             │   │
│  │ Detection       │     │                              │   │
│  └─────────────────┘     └──────────────────────────────┘   │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Conversation State                                    │  │
│  └───────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                      CLAUDE API                             │
│                                                             │
│  Reasoning + Tool Selection + Response Generation           │
└────────────────────────────┬────────────────────────────────┘
                             │
                        tool_use
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                       TOOL REGISTRY                         │
├───────────────────┬───────────────────┬─────────────────────┤
│ Filesystem        │ Terminal          │ Memory              │
│                   │                   │                     │
│ list_directory    │ run_terminal      │ add_memory          │
│ read_file         │                   │ get_memories        │
│ search_files      │                   │ search_memories     │
│                   │                   │ delete_memory       │
└───────────────────┴─────────┬─────────┴─────────────────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │ Permission Layer  │
                    └─────────┬─────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │ Local Execution   │
                    └─────────┬─────────┘
                              │
                              ▼
                         tool_result
                              │
                              ▼
                         CLAUDE API
                              │
                              ▼
                       Final Response
```

---

# 19. Future Architecture

Planned architectural improvements include:

- replacing the remaining Ollama embedding dependency
- structured agent workflows
- more advanced tool orchestration
- improved execution tracing
- stronger automated safety tests
- richer memory management
- additional interfaces for Tarō

The long-term goal is to evolve Tarō from a basic personal assistant into a modular personal agent platform where model reasoning, memory, tools, and execution policies remain independently replaceable.
