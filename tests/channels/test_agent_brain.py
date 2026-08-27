"""Unit and Integration Tests for AutonomousAgentBrain."""
import asyncio
import os
from unittest.mock import MagicMock, patch
import pytest

from app.tools.agent_brain import AutonomousAgentBrain


def test_ab_01_tool_execution():
    """AB-01: Agent brain executes local tools properly."""
    brain = AutonomousAgentBrain(api_key="mock_key")

    # Test open_application
    with patch.object(brain.pc_pilot, "launch_app", return_value="Launched notepad") as mock_launch:
        res, photo = brain.execute_tool("open_application", {"app_name": "notepad"})
        assert res == "Launched notepad"
        mock_launch.assert_called_once_with("notepad")

    # Test close_application_or_tab
    with patch.object(brain.pc_pilot, "close_app", return_value="Closed notepad") as mock_close:
        res, photo = brain.execute_tool("close_application_or_tab", {"target": "notepad"})
        assert res == "Closed notepad"
        mock_close.assert_called_once_with("notepad")

    # Test browse_or_search_web (search)
    with patch.object(brain.pc_pilot, "search_google", return_value="Searched Google") as mock_search:
        res, photo = brain.execute_tool("browse_or_search_web", {"search_query": "AI agents"})
        assert res == "Searched Google"
        mock_search.assert_called_once_with("AI agents")

    # Test control_pc_system (lock)
    with patch.object(brain.pc_pilot, "lock_pc", return_value="Locked PC") as mock_lock:
        res, photo = brain.execute_tool("control_pc_system", {"action": "lock_pc"})
        assert res == "Locked PC"
        mock_lock.assert_called_once()


def test_ab_02_mock_llm_tool_dispatch():
    """AB-02: LLM tool calling is parsed and executed dynamically."""
    brain = AutonomousAgentBrain(api_key="mock_key")
    mock_client = MagicMock()
    
    # Mock LLM returning tool call for close_application_or_tab
    mock_tool_call = MagicMock()
    mock_tool_call.function.name = "close_application_or_tab"
    mock_tool_call.function.arguments = '{"target": "notepad"}'

    mock_msg = MagicMock()
    mock_msg.tool_calls = [mock_tool_call]
    mock_msg.content = None

    mock_choice = MagicMock()
    mock_choice.message = mock_msg

    mock_res = MagicMock()
    mock_res.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_res
    brain._client = mock_client

    with patch.object(brain.pc_pilot, "close_app", return_value="Closed notepad, Boss."):
        res, photo = asyncio.run(brain.process_user_intent("notepad-a close pannu"))
        assert "Closed notepad, Boss." in res
        assert photo is None


def test_ab_03_mock_llm_conversational_response():
    """AB-03: Conversational prompt produces direct text response without tool call."""
    brain = AutonomousAgentBrain(api_key="mock_key")
    mock_client = MagicMock()

    mock_msg = MagicMock()
    mock_msg.tool_calls = None
    mock_msg.content = "TCP is connection-oriented while UDP is connectionless, Boss!"

    mock_choice = MagicMock()
    mock_choice.message = mock_msg

    mock_res = MagicMock()
    mock_res.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_res
    brain._client = mock_client

    res, photo = asyncio.run(brain.process_user_intent("Explain TCP vs UDP"))
    assert "TCP is connection-oriented" in res
    assert photo is None


def test_ab_04_universal_tools_execution():
    """AB-04: Universal tools (terminal, file manager, python runner) execute properly."""
    brain = AutonomousAgentBrain(api_key="mock_key")

    # 1. Run Python Code
    py_code = "print(2 + 3)"
    res, _ = brain.execute_tool("run_python_code", {"code": py_code})
    assert "5" in res

    # 2. Manage Files (write & read)
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
        tpath = tmp.name

    try:
        w_res, _ = brain.execute_tool("manage_files", {"action": "write", "file_path": tpath, "content": "Hello Jarvis"})
        assert "created / updated successfully" in w_res

        r_res, _ = brain.execute_tool("manage_files", {"action": "read", "file_path": tpath})
        assert "Hello Jarvis" in r_res
    finally:
        if os.path.exists(tpath):
            os.remove(tpath)

    # 3. Execute Terminal Command
    with patch("subprocess.check_output", return_value="v1.0.0\n"):
        c_res, _ = brain.execute_tool("execute_terminal_command", {"command": "git --version"})
        assert "git --version" in c_res
        assert "v1.0.0" in c_res

