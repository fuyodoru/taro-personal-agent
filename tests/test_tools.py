import unittest
from unittest.mock import Mock, patch

from core.agent import Agent
from tools.registry import get_tool, get_tools
from tools.terminal import classify_command


class TestTerminalSafety(unittest.TestCase):
    def test_safe_command_is_classified_safe(self):
        self.assertEqual(classify_command("pwd"), "SAFE")

    def test_blocked_command_is_classified_block(self):
        self.assertEqual(classify_command("sudo reboot"), "BLOCK")

    def test_shell_chaining_requires_confirmation(self):
        self.assertEqual(classify_command("pwd && whoami"), "CONFIRM")

    def test_pipe_requires_confirmation(self):
        self.assertEqual(classify_command("ls | grep test"), "CONFIRM")

    def test_redirection_requires_confirmation(self):
        self.assertEqual(classify_command("echo test > file.txt"), "CONFIRM")

    def test_empty_command_is_blocked(self):
        self.assertEqual(classify_command(""), "BLOCK")

    def test_malformed_command_is_blocked(self):
        self.assertEqual(classify_command("echo 'unterminated"), "BLOCK")


class TestToolRegistry(unittest.TestCase):
    def test_get_known_tool(self):
        tool = get_tool("list_directory")

        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "list_directory")

    def test_get_unknown_tool(self):
        self.assertIsNone(get_tool("does_not_exist"))

    def test_anthropic_tool_schema(self):
        tools = get_tools()
        names = {tool["name"] for tool in tools}

        self.assertIn("list_directory", names)
        self.assertIn("read_file", names)
        self.assertIn("search_files", names)
        self.assertIn("run_terminal", names)
        self.assertIn("add_memory", names)

        for tool in tools:
            self.assertIn("name", tool)
            self.assertIn("description", tool)
            self.assertIn("input_schema", tool)


class TestAgentPermissions(unittest.TestCase):
    def setUp(self):
        self.agent = Agent()

    @patch("core.agent.input", return_value="y")
    def test_confirmation_allows_action(self, mock_input):
        tool_spec = Mock()
        tool_spec.name = "test_tool"
        tool_spec.risk = "EXECUTE"

        self.assertTrue(
            self.agent._confirm_tool(
                tool_spec,
                {"value": "test"},
            )
        )

        mock_input.assert_called_once()

    @patch("core.agent.input", return_value="n")
    def test_confirmation_denies_action(self, mock_input):
        tool_spec = Mock()
        tool_spec.name = "test_tool"
        tool_spec.risk = "EXECUTE"

        self.assertFalse(
            self.agent._confirm_tool(
                tool_spec,
                {"value": "test"},
            )
        )

        mock_input.assert_called_once()

    @patch("core.agent.input", return_value="")
    def test_confirmation_defaults_to_denied(self, mock_input):
        tool_spec = Mock()
        tool_spec.name = "test_tool"
        tool_spec.risk = "EXECUTE"

        self.assertFalse(
            self.agent._confirm_tool(
                tool_spec,
                {"value": "test"},
            )
        )


class TestAgentToolExecution(unittest.TestCase):
    def setUp(self):
        self.agent = Agent()

    def test_unknown_tool_returns_error(self):
        tool_use = Mock()
        tool_use.name = "unknown_tool"
        tool_use.input = {}

        result = self.agent._execute_tool(tool_use)

        self.assertIn("Unknown tool", result)

    @patch("core.agent.get_tool")
    def test_denied_tool_is_not_executed(self, mock_get_tool):
        function = Mock(return_value="executed")

        tool_spec = Mock()
        tool_spec.name = "test_tool"
        tool_spec.risk = "EXECUTE"
        tool_spec.requires_confirmation = True
        tool_spec.function = function

        mock_get_tool.return_value = tool_spec

        tool_use = Mock()
        tool_use.name = "test_tool"
        tool_use.input = {"value": "test"}

        with patch.object(self.agent, "_confirm_tool", return_value=False):
            result = self.agent._execute_tool(tool_use)

        self.assertEqual(result, "Action denied by the user.")
        function.assert_not_called()

    @patch("core.agent.get_tool")
    def test_approved_tool_is_executed(self, mock_get_tool):
        function = Mock(return_value="success")

        tool_spec = Mock()
        tool_spec.name = "test_tool"
        tool_spec.risk = "EXECUTE"
        tool_spec.requires_confirmation = True
        tool_spec.function = function

        mock_get_tool.return_value = tool_spec

        tool_use = Mock()
        tool_use.name = "test_tool"
        tool_use.input = {"value": "test"}

        with patch.object(self.agent, "_confirm_tool", return_value=True):
            result = self.agent._execute_tool(tool_use)

        self.assertEqual(result, "success")
        function.assert_called_once_with(value="test")
    @patch("core.agent.get_tool")
    @patch("core.agent.classify_command")
    def test_safe_terminal_command_skips_confirmation(
        self,
        mock_classify,
        mock_get_tool,
    ):
        function = Mock(
            return_value="Exit code: 0\n\nSTDOUT:\n/home/ranpo"
        )

        tool_spec = Mock()
        tool_spec.name = "run_terminal"
        tool_spec.risk = "EXECUTE"
        tool_spec.requires_confirmation = True
        tool_spec.function = function

        mock_get_tool.return_value = tool_spec
        mock_classify.return_value = "SAFE"

        tool_use = Mock()
        tool_use.name = "run_terminal"
        tool_use.input = {
            "command": "pwd"
        }

        with patch.object(
            self.agent,
            "_confirm_tool",
        ) as mock_confirm:

            result = self.agent._execute_tool(
                tool_use
            )

        mock_confirm.assert_not_called()

        function.assert_called_once_with(
            command="pwd"
        )

        self.assertIn(
            "Exit code: 0",
            result,
        )

    @patch("core.agent.get_tool")
    @patch("core.agent.classify_command")
    def test_confirm_terminal_command_requires_approval(
        self,
        mock_classify,
        mock_get_tool,
    ):
        function = Mock(
            return_value="Exit code: 0"
        )

        tool_spec = Mock()
        tool_spec.name = "run_terminal"
        tool_spec.risk = "EXECUTE"
        tool_spec.requires_confirmation = True
        tool_spec.function = function

        mock_get_tool.return_value = tool_spec
        mock_classify.return_value = "CONFIRM"

        tool_use = Mock()
        tool_use.name = "run_terminal"
        tool_use.input = {
            "command": "echo hello"
        }

        with patch.object(
            self.agent,
            "_confirm_tool",
            return_value=True,
        ) as mock_confirm:

            result = self.agent._execute_tool(
                tool_use
            )

        mock_confirm.assert_called_once_with(
            tool_spec,
            {
                "command": "echo hello"
            },
        )

        function.assert_called_once_with(
            command="echo hello"
        )

        self.assertEqual(
            result,
            "Exit code: 0",
        )

    @patch("core.agent.get_tool")
    @patch("core.agent.classify_command")
    def test_blocked_terminal_command_is_rejected(
        self,
        mock_classify,
        mock_get_tool,
    ):
        function = Mock()

        tool_spec = Mock()
        tool_spec.name = "run_terminal"
        tool_spec.risk = "EXECUTE"
        tool_spec.requires_confirmation = True
        tool_spec.function = function

        mock_get_tool.return_value = tool_spec
        mock_classify.return_value = "BLOCK"

        tool_use = Mock()
        tool_use.name = "run_terminal"
        tool_use.input = {
            "command": "sudo reboot"
        }

        with patch.object(
            self.agent,
            "_confirm_tool",
        ) as mock_confirm:

            result = self.agent._execute_tool(
                tool_use
            )

        mock_confirm.assert_not_called()
        function.assert_not_called()

        self.assertIn(
            "BLOCKED",
            result,
        )

    @patch("core.agent.get_tool")
    @patch("core.agent.classify_command")
    def test_denied_terminal_command_is_not_executed(
        self,
        mock_classify,
        mock_get_tool,
    ):
        function = Mock()

        tool_spec = Mock()
        tool_spec.name = "run_terminal"
        tool_spec.risk = "EXECUTE"
        tool_spec.requires_confirmation = True
        tool_spec.function = function

        mock_get_tool.return_value = tool_spec
        mock_classify.return_value = "CONFIRM"

        tool_use = Mock()
        tool_use.name = "run_terminal"
        tool_use.input = {
            "command": "echo hello"
        }

        with patch.object(
            self.agent,
            "_confirm_tool",
            return_value=False,
        ) as mock_confirm:

            result = self.agent._execute_tool(
                tool_use
            )

        mock_confirm.assert_called_once()

        function.assert_not_called()

        self.assertEqual(
            result,
            "Action denied by the user.",
        )
    @patch("core.agent.get_tool")
    def test_tool_argument_error_is_reported(self, mock_get_tool):
        function = Mock(side_effect=TypeError("bad argument"))

        tool_spec = Mock()
        tool_spec.name = "test_tool"
        tool_spec.risk = "EXECUTE"
        tool_spec.requires_confirmation = False
        tool_spec.function = function

        mock_get_tool.return_value = tool_spec

        tool_use = Mock()
        tool_use.name = "test_tool"
        tool_use.input = {"value": "test"}

        result = self.agent._execute_tool(tool_use)

        self.assertIn("Tool argument error", result)
class TestAgentWorkflow(unittest.TestCase):
    def setUp(self):
        self.agent = Agent()

    @patch("core.agent.chat_with_model")
    def test_workflow_returns_final_response(
        self,
        mock_chat,
    ):
        final_response = Mock()
        final_response.content = [
            Mock(
                type="text",
                text="Task completed.",
            )
        ]

        mock_chat.return_value = final_response

        result = self.agent._run_claude_loop(
            "English"
        )

        self.assertEqual(
            result,
            "Task completed.",
        )

        mock_chat.assert_called_once()

    @patch("core.agent.chat_with_model")
    def test_workflow_respects_iteration_limit(
        self,
        mock_chat,
    ):
        tool_response = Mock()

        tool_use = Mock()
        tool_use.type = "tool_use"
        tool_use.name = "list_directory"
        tool_use.id = "tool-use-id"
        tool_use.input = {}

        tool_response.content = [
            tool_use
        ]

        mock_chat.return_value = tool_response

        with patch.object(
            self.agent,
            "_execute_tool",
            return_value="tool result",
        ):

            result = self.agent._run_claude_loop(
                "English"
            )

        self.assertIn(
            "maximum workflow step limit",
            result,
        )

        self.assertEqual(
            mock_chat.call_count,
            10,
        )

if __name__ == "__main__":
    unittest.main()
