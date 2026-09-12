import json
import time

from brain.llm import chat_with_model
from tools.registry import get_tools, get_tool
from tools.terminal import classify_command

from memory.memory import search_memories

from language import detect_language


# =========================================================
# AGENT CONFIGURATION
# =========================================================

MAX_TOOL_ITERATIONS = 10

CACHEABLE_RISKS = {
    "READ",
    "MEMORY_READ",
}


class Agent:

    def __init__(self):
        self.messages = []

        # Tool cache lives only for the current
        # Agent workflow / user request.
        self.tool_cache = {}

    # =========================================================
    # LANGUAGE
    # =========================================================

    def _detect_language(
        self,
        user_input: str,
    ) -> str:

        start = time.perf_counter()

        language = detect_language(
            user_input
        )

        elapsed = (
            time.perf_counter()
            - start
        )

        print(
            f"[Language] {language}"
        )

        print(
            f"[Timing] Language: "
            f"{elapsed:.3f}s"
        )

        return language

    # =========================================================
    # MEMORY
    # =========================================================

    def _get_relevant_memories(
        self,
        user_input: str,
    ) -> list[dict]:

        start = time.perf_counter()

        results = []
        seen = set()

        try:

            matches = search_memories(
                user_input
            )

            for memory in matches:

                content = memory.get(
                    "content",
                    "",
                )

                if (
                    content
                    and content not in seen
                ):

                    results.append(
                        memory
                    )

                    seen.add(
                        content
                    )

        except Exception as error:

            print(
                f"[Memory] Search error: "
                f"{type(error).__name__}: "
                f"{error}"
            )

        results = results[:5]

        elapsed = (
            time.perf_counter()
            - start
        )

        print(
            f"[Memory] Results: "
            f"{len(results)}"
        )

        print(
            f"[Timing] Memory: "
            f"{elapsed:.3f}s"
        )

        return results

    def _build_memory_context(
        self,
        memories: list[dict],
    ) -> str:

        if not memories:
            return ""

        lines = [
            "Relevant information from Tarō's long-term memory:",
            "",
        ]

        for memory in memories:

            category = memory.get(
                "category",
                "general",
            )

            content = memory.get(
                "content",
                "",
            )

            if content:

                lines.append(
                    f"- [{category}] {content}"
                )

        return "\n".join(
            lines
        )

    # =========================================================
    # TOOL CACHE
    # =========================================================

    def _build_tool_cache_key(
        self,
        tool_name: str,
        arguments: dict,
    ) -> str:
        """
        Build a deterministic cache key for a tool call.

        Arguments are serialized with sorted keys so that
        equivalent dictionaries produce the same key.
        """

        normalized_arguments = json.dumps(
            arguments,
            sort_keys=True,
            ensure_ascii=False,
        )

        return (
            f"{tool_name}:"
            f"{normalized_arguments}"
        )

    # =========================================================
    # TOOL PERMISSION
    # =========================================================

    def _confirm_tool(
        self,
        tool_spec,
        arguments,
    ) -> bool:

        print(
            "\n" + "=" * 50
        )

        print(
            "Tarō Permission Request"
        )

        print(
            "=" * 50
        )

        print(
            f"Tool: {tool_spec.name}"
        )

        print(
            f"Risk: {tool_spec.risk}"
        )

        print(
            f"Arguments: {arguments}"
        )

        answer = input(
            "\nAllow this action? [y/N]: "
        ).strip().lower()

        return answer in (
            "y",
            "yes",
        )

    # =========================================================
    # TOOL EXECUTION
    # =========================================================

    def _execute_tool(
        self,
        tool_use_block,
    ) -> str:
        """
        Execute an Anthropic tool_use content block.

        Terminal tools use command-level safety
        classification:

            SAFE    -> execute automatically
            CONFIRM -> ask the user
            BLOCK   -> never execute

        Cacheable read-only tools can reuse results
        within the current workflow.
        """

        tool_name = (
            tool_use_block.name
        )

        arguments = (
            tool_use_block.input
            or {}
        )

        tool_spec = get_tool(
            tool_name
        )

        if tool_spec is None:

            return (
                f"Error: Unknown tool "
                f"'{tool_name}'."
            )

        # =====================================================
        # TOOL CACHE
        # =====================================================

        cache_key = self._build_tool_cache_key(
            tool_name,
            arguments,
        )

        if (
            tool_spec.risk in CACHEABLE_RISKS
            and cache_key in self.tool_cache
        ):

            print(
                f"[Tool cache] HIT: "
                f"{tool_name}"
            )

            return self.tool_cache[
                cache_key
            ]

        # =====================================================
        # DETERMINE PERMISSION REQUIREMENT
        # =====================================================

        requires_confirmation = (
            tool_spec.requires_confirmation
        )

        # =====================================================
        # TERMINAL SAFETY CLASSIFICATION
        # =====================================================

        if tool_name == "run_terminal":

            command = arguments.get(
                "command",
                "",
            )

            classification = classify_command(
                command
            )

            print(
                f"[Safety] Terminal command "
                f"classification: {classification}"
            )

            # -------------------------------------------------
            # BLOCK
            # -------------------------------------------------

            if classification == "BLOCK":

                return (
                    "BLOCKED: This command is considered "
                    "too dangerous for Tarō to execute."
                )

            # -------------------------------------------------
            # SAFE
            # -------------------------------------------------

            elif classification == "SAFE":

                requires_confirmation = False

            # -------------------------------------------------
            # CONFIRM
            # -------------------------------------------------

            elif classification == "CONFIRM":

                requires_confirmation = True

        # =====================================================
        # USER CONFIRMATION
        # =====================================================

        if requires_confirmation:

            allowed = self._confirm_tool(
                tool_spec,
                arguments,
            )

            if not allowed:

                return (
                    "Action denied by the user."
                )

        # =====================================================
        # EXECUTE TOOL
        # =====================================================

        try:

            result = tool_spec.function(
                **arguments
            )

            result = str(
                result
            )

            # -------------------------------------------------
            # STORE CACHE RESULT
            # -------------------------------------------------

            if tool_spec.risk in CACHEABLE_RISKS:

                self.tool_cache[
                    cache_key
                ] = result

                print(
                    f"[Tool cache] STORE: "
                    f"{tool_name}"
                )

            return result

        except TypeError as error:

            return (
                f"Tool argument error "
                f"for '{tool_name}': "
                f"{error}"
            )

        except Exception as error:

            return (
                f"Tool execution error: "
                f"{type(error).__name__}: "
                f"{error}"
            )

    # =========================================================
    # CLAUDE / TOOL LOOP
    # =========================================================

    def _run_claude_loop(
        self,
        language: str,
    ) -> str:
        """
        Run Claude until it produces a final text response.

        Claude may request multiple tools. Tool results are
        returned to Claude and the loop continues until Claude
        produces a normal text response.

        The workflow is bounded by MAX_TOOL_ITERATIONS to
        prevent unbounded tool execution.
        """

        for iteration in range(
            1,
            MAX_TOOL_ITERATIONS + 1,
        ):

            print(
                f"\n[Agent] Workflow step "
                f"{iteration}/"
                f"{MAX_TOOL_ITERATIONS}"
            )

            response = chat_with_model(
                self.messages,
                get_tools(),
                response_language=language,
            )

            # =================================================
            # CONVERT ANTHROPIC CONTENT BLOCKS
            # =================================================

            assistant_content = [
                block.model_dump()
                for block in response.content
            ]

            # =================================================
            # FIND TOOL USE BLOCKS
            # =================================================

            tool_use_blocks = [
                block
                for block in response.content
                if block.type == "tool_use"
            ]

            # =================================================
            # TOOL USE
            # =================================================

            if tool_use_blocks:

                # Store Claude's complete assistant message.
                self.messages.append(
                    {
                        "role": "assistant",
                        "content": assistant_content,
                    }
                )

                tool_results = []

                for tool_use in tool_use_blocks:

                    result = self._execute_tool(
                        tool_use
                    )

                    print(
                        f"\n[Tool result: "
                        f"{tool_use.name}]"
                    )

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": result,
                        }
                    )

                # -------------------------------------------------
                # Anthropic requires tool_result blocks inside
                # a user message.
                # -------------------------------------------------

                self.messages.append(
                    {
                        "role": "user",
                        "content": tool_results,
                    }
                )

                # Claude receives the tool results and decides
                # whether another tool is required.
                continue

            # =================================================
            # FINAL TEXT RESPONSE
            # =================================================

            text_blocks = [
                block.text
                for block in response.content
                if block.type == "text"
            ]

            answer = (
                "\n".join(
                    text_blocks
                ).strip()
            )

            # Store Claude's final response.
            self.messages.append(
                {
                    "role": "assistant",
                    "content": assistant_content,
                }
            )

            print(
                f"\n[Agent] Workflow completed "
                f"in {iteration} step(s)."
            )

            return answer

        # =====================================================
        # WORKFLOW LIMIT
        # =====================================================

        return (
            "The task reached Tarō's maximum "
            "workflow step limit before Claude "
            "produced a final response."
        )

    # =========================================================
    # MAIN LOOP
    # =========================================================

    def run(self):

        print(
            "Tarō is online."
        )

        print(
            "Type 'exit' or 'quit' to stop."
        )

        while True:

            try:

                user_input = input(
                    "\nYou: "
                ).strip()

            except (
                KeyboardInterrupt,
                EOFError,
            ):

                print(
                    "\nTarō: Goodbye."
                )

                break

            if not user_input:
                continue

            if user_input.lower() in (
                "exit",
                "quit",
            ):

                print(
                    "Tarō: Goodbye."
                )

                break

            # =================================================
            # RESET WORKFLOW CACHE
            # =================================================

            self.tool_cache.clear()

            # =================================================
            # LANGUAGE
            # =================================================

            language = (
                self._detect_language(
                    user_input
                )
            )

            # =================================================
            # MEMORY
            # =================================================

            memories = (
                self._get_relevant_memories(
                    user_input
                )
            )

            memory_context = (
                self._build_memory_context(
                    memories
                )
            )

            # =================================================
            # CONTEXT
            # =================================================

            parts = []

            parts.append(
                f"Response language: "
                f"{language}"
            )

            if memory_context:

                parts.append(
                    memory_context
                )

            parts.append(
                "Current user message:\n"
                + user_input
            )

            contextual_message = (
                "\n\n".join(parts)
            )

            self.messages.append(
                {
                    "role": "user",
                    "content": contextual_message,
                }
            )

            # =================================================
            # CLAUDE / TOOL LOOP
            # =================================================

            try:

                answer = (
                    self._run_claude_loop(
                        language
                    )
                )

                print(
                    f"Tarō: {answer}"
                )

            except Exception as error:

                print(
                    "Tarō: Something went wrong: "
                    f"{type(error).__name__}: "
                    f"{error}"
                )


def main():

    agent = Agent()

    agent.run()


if __name__ == "__main__":
    main()