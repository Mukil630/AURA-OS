"""Unit and Integration Tests for PCPilot & Browser Automation."""
from unittest.mock import patch
import pytest

from app.tools.pc_pilot import PCPilot


def test_pc_01_google_search():
    """PC-01: PCPilot constructs Google search URL properly."""
    pilot = PCPilot()
    with patch("webbrowser.open") as mock_open:
        res = pilot.search_google("fastapi best practices")
        assert "fastapi best practices" in res
        mock_open.assert_called_once_with("https://www.google.com/search?q=fastapi+best+practices")


def test_pc_02_youtube_search():
    """PC-02: PCPilot constructs YouTube search URL properly."""
    pilot = PCPilot()
    with patch("webbrowser.open") as mock_open:
        res = pilot.search_youtube("lofi beats")
        assert "lofi beats" in res
        mock_open.assert_called_once_with("https://www.youtube.com/results?search_query=lofi+beats")


def test_pc_03_known_sites():
    """PC-03: PCPilot resolves known sites (github, linkedin, etc.)."""
    pilot = PCPilot()
    with patch("webbrowser.open") as mock_open:
        res = pilot.open_known_site("github")
        assert res is not None
        assert "Github" in res
        mock_open.assert_called_once_with("https://github.com")

        res_unknown = pilot.open_known_site("non_existent_site_xyz")
        assert res_unknown is None


def test_pc_04_intent_routing():
    """PC-04: try_execute_pc_intent matches natural search, volume, and app commands."""
    pilot = PCPilot()
    
    with patch("webbrowser.open"):
        # Google search
        handled, msg, _ = pilot.try_execute_pc_intent("search python tutorials on google")
        assert handled is True
        assert "python tutorials" in msg

        # YouTube search
        handled, msg, _ = pilot.try_execute_pc_intent("open youtube and play hans zimmer")
        assert handled is True
        assert "hans zimmer" in msg

        # Open known site
        handled, msg, _ = pilot.try_execute_pc_intent("open linkedin")
        assert handled is True
        assert "Linkedin" in msg

    # Lock PC
    with patch("ctypes.windll.user32.LockWorkStation"):
        handled, msg, _ = pilot.try_execute_pc_intent("lock my pc")
        assert handled is True
        assert "Locked" in msg

    # Unhandled natural conversational text
    handled, msg, _ = pilot.try_execute_pc_intent("What is recursion?")
    assert handled is False


def test_pc_05_close_app_and_tabs():
    """PC-05: Tests closing apps and browser tabs."""
    pilot = PCPilot()
    
    with patch("pyautogui.hotkey") as mock_hotkey:
        handled, msg, _ = pilot.try_execute_pc_intent("close youtube")
        assert handled is True
        assert "Closed active browser tab" in msg
        mock_hotkey.assert_called_with("ctrl", "w")

        handled, msg, _ = pilot.try_execute_pc_intent("close notepad")
        assert handled is True
        assert "Closed" in msg

