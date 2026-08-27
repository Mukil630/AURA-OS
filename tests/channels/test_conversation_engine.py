"""Unit and Integration Tests for Natural ConversationEngine."""
import asyncio
from unittest.mock import MagicMock, patch
import pytest

from app.tools.conversation_engine import ConversationEngine


def test_ce_01_task_intent_detection():
    """CE-01: Engine distinguishes between explicit task execution and casual conversation."""
    engine = ConversationEngine(api_key="mock_key")
    
    # Casual conversations
    assert engine.is_task_intent("Hello Jarvis, how are you?") is False
    assert engine.is_task_intent("Explain binary search in python") is False
    assert engine.is_task_intent("What is Docker?") is False
    assert engine.is_task_intent("10.00 mani ku timer") is False
    
    # Explicit tasks
    assert engine.is_task_intent("run script test.py") is True
    assert engine.is_task_intent("execute command hostname") is True
    assert engine.is_task_intent("deploy to vercel") is True
    assert engine.is_task_intent("run automation suite") is True


def test_ce_02_empty_query_fallback():
    """CE-02: Engine handles empty queries safely."""
    engine = ConversationEngine(api_key=None)
    res = asyncio.run(engine.generate_chat_response(""))
    assert "Boss" in res


def test_ce_03_mock_chat_generation():
    """CE-03: Chat generation produces conversational answers without task ticket format."""
    engine = ConversationEngine(api_key="mock_key")
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "Hello Boss! Binary search works in O(log n) time by dividing the search range in half."
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response
    engine._client = mock_client

    res = asyncio.run(engine.generate_chat_response("Explain binary search"))
    assert "Binary search" in res
    assert "Task Accepted by Jarvis" not in res
    assert "Status: Running" not in res
