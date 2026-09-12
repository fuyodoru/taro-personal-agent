# Tarō

> A personal AI agent powered by Claude.

Tarō is a local personal AI assistant designed to run on the user's computer.

Unlike a simple chatbot, Tarō can use tools, access files, execute terminal commands through a safety layer, and maintain persistent memory.

The project is built around the Anthropic Messages API and Claude tool use.

---

## Features

### Claude-powered reasoning

Tarō uses Claude as its primary language model through the Anthropic API.

The agent maintains conversation state and allows Claude to decide when a tool is required.

### Tool use

Tarō can interact with the local computer through a controlled tool layer.

Current tools include:

- `list_directory`
- `read_file`
- `search_files`
- `run_terminal`
- `add_memory`
- `get_memories`
- `search_memories`
- `delete_memory`

Claude does not directly execute these functions.

Instead, Claude requests a tool through `tool_use`, and Tarō executes the requested operation and returns the result through `tool_result`.

### Persistent memory

Tarō maintains persistent memories in a local JSON store.

The agent can:

- store information
- retrieve memories
- search relevant memories
- delete stored memories

Memory retrieval is performed before sending the current request to Claude so that relevant information can be included as context.

### Human-in-the-loop safety

Actions that modify persistent memory or execute terminal commands require user confirmation.

For example:

```text
==================================================
Tarō Permission Request
==================================================
Tool: run_terminal
Risk: EXECUTE
Arguments: {'command': 'pwd'}

Allow this action? [y/N]:
```

The user explicitly controls whether the operation is allowed.

### Filesystem access

Tarō can inspect files and directories through dedicated filesystem tools.

The filesystem layer resolves user paths and handles common filesystem errors without exposing raw exceptions to the agent.

### Multilingual interaction

Tarō includes a language detection layer supporting:

- English
- Turkish
- Italian
- Japanese
- German
- French
- Spanish
- Portuguese

The detected language is passed explicitly to the model as the current response language.

---

## Architecture

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
                ┌─────────────────┼─────────────────┐
                │                 │                 │
                ▼                 ▼                 ▼
        Language Detection   Memory Retrieval   Conversation
                │                 │                 │
                └─────────────────┼─────────────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │   Claude API     │
                         │ Anthropic Model  │
                         └────────┬─────────┘
                                  │
                             tool_use
                                  │
                                  ▼
                         ┌──────────────────┐
                         │ Permission Layer │
                         └────────┬─────────┘
                                  │
                         ┌────────┴────────┐
                         │                 │
                         ▼                 ▼
                   User approval       Tool execution
                                           │
                                           ▼
                                     tool_result
                                           │
                                           ▼
                                      Claude
```

---

## Tool Execution Flow

Tarō uses the Anthropic tool-use pattern.

```text
User request
     │
     ▼
   Claude
     │
     │ tool_use
     ▼
Tarō Agent
     │
     ▼
Permission check
     │
     ├── denied ──────► tool_result
     │
     └── approved
            │
            ▼
       Tool execution
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

This allows Tarō to separate model reasoning from local computer operations.

---

## Safety Model

Tarō does not give Claude unrestricted access to the operating system.

Tool execution is mediated by Tarō's tool registry and permission layer.

Terminal commands are additionally classified by the terminal safety layer.

Commands can be classified as:

```text
SAFE
CONFIRM
BLOCK
```

Dangerous system commands such as:

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

Commands outside the explicitly safe command set require additional protection.

Persistent memory writes and deletions also require explicit user confirmation.

---

## Project Structure

```text
taro/
│
├── brain/
│   ├── __init__.py
│   └── llm.py
│
├── config/
│   └── __init__.py
│
├── core/
│   ├── __init__.py
│   └── agent.py
│
├── docs/
│   └── architecture.md
│
├── memory/
│   ├── __init__.py
│   ├── memories.json
│   └── memory.py
│
├── tools/
│   ├── __init__.py
│   ├── filesystem.py
│   ├── registry.py
│   └── terminal.py
│
├── tests/
│   └── __init__.py
│
├── vision/
│   └── __init__.py
│
├── voice/
│   └── __init__.py
│
├── language.py
├── main.py
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Installation

### Requirements

- Python 3.14+
- An Anthropic API key
- Internet access for Claude API requests

Clone the repository:

```bash
git clone <YOUR_REPOSITORY_URL>
cd taro
```

Create a virtual environment:

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Configuration

Create a `.env` file in the project root:

```env
ANTHROPIC_API_KEY=your_api_key_here
TARO_MODEL=claude-sonnet-4-6
```

Never commit `.env` to Git.

The repository includes `.env` in `.gitignore`.

---

## Running Tarō

Activate the virtual environment:

```bash
source .venv/bin/activate
```

Start Tarō:

```bash
python main.py
```

You should see:

```text
Tarō is online.
Type 'exit' or 'quit' to stop.
```

---

## Examples

### Filesystem tool

```text
You: What files are in my home directory?
```

Tarō can request:

```text
list_directory
```

The tool result is returned to Claude, which then produces the final response.

### Terminal tool

```text
You: Run pwd in the terminal.
```

Tarō requests permission before executing the command:

```text
Tarō Permission Request

Tool: run_terminal
Risk: EXECUTE
Arguments: {'command': 'pwd'}

Allow this action? [y/N]:
```

### Memory

```text
You: Remember that I am building a personal AI assistant called Taro.
```

Tarō requests confirmation before storing the memory.

Later:

```text
You: What do you know about the AI assistant I'm building?
```

Relevant memory can be retrieved and provided to Claude as context.

---

## Design Principles

Tarō is designed around several principles.

### 1. Model and execution are separate

Claude decides what should happen.

Tarō decides how that operation is safely executed.

### 2. Tools are explicit

Computer capabilities are exposed through named tools rather than unrestricted model access.

### 3. Risky operations require consent

The user remains in control of operations that can modify state or execute commands.

### 4. Memory is contextual

Stored memories are retrieved based on relevance rather than blindly injecting the entire memory store into every request.

### 5. The agent should be honest

Tarō should never claim that an operation succeeded without receiving a successful tool result.

---

## Development Roadmap

### Current

- [x] Claude API integration
- [x] Conversation loop
- [x] Anthropic tool use
- [x] Filesystem tools
- [x] Terminal tool
- [x] Permission layer
- [x] Persistent memory
- [x] Multilingual interaction
- [x] Environment variable configuration

### Planned

- [ ] Remove the remaining Ollama dependency from semantic memory
- [ ] Expand automated test coverage
- [ ] Improve memory architecture
- [ ] Add structured agent workflows
- [ ] Add more robust tool orchestration
- [ ] Improve observability and execution tracing
- [ ] Add a richer interactive interface
- [ ] Create demonstrations and workshops around agent development

---

## Why Tarō?

Tarō is an experiment in building a practical personal AI agent rather than a simple conversational interface.

The project explores how a language model can be connected to:

- persistent state
- local tools
- filesystem operations
- terminal execution
- permission systems
- multilingual interaction

while keeping the user in control of computer-side actions.

---

## License

This project is currently under development.
