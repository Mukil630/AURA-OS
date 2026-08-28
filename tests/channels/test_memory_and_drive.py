"""Unit Tests for Persistent MemoryVault and 5TB Google Drive Vault Manager."""
import json
import os
import tempfile
from unittest.mock import patch

from app.connectors.drive.drive_vault import (
    DriveVaultManager,
    MASTER_RESUME_URL,
    MASTER_VAULT_URL,
)
from app.tools.agent_brain import AutonomousAgentBrain
from app.tools.memory_vault import MemoryVault


def test_mem_01_profile_and_context():
    """MEM-01: MemoryVault loads default profile and updates context."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("app.tools.memory_vault.MEMORY_DIR", tmp_dir), \
             patch("app.tools.memory_vault.PROFILE_FILE", os.path.join(tmp_dir, "profile.json")), \
             patch("app.tools.memory_vault.CONTEXT_FILE", os.path.join(tmp_dir, "context.json")), \
             patch("app.tools.memory_vault.CONVERSATIONS_FILE", os.path.join(tmp_dir, "convos.json")), \
             patch("app.tools.memory_vault.DOCUMENTS_FILE", os.path.join(tmp_dir, "docs.json")):
            vault = MemoryVault()
            prof = vault.get_profile()
            assert prof["user_name"] == "Mukil"
            assert prof["master_resume_link"] == MASTER_RESUME_URL

            vault.update_context("active_goal", "Placement Sprint")
            ctx = vault.get_context()
            assert ctx["active_goal"] == "Placement Sprint"


def test_mem_02_record_conversation_and_save_document():
    """MEM-02: Records conversation turns and saves important documents."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch("app.tools.memory_vault.MEMORY_DIR", tmp_dir), \
             patch("app.tools.memory_vault.PROFILE_FILE", os.path.join(tmp_dir, "profile.json")), \
             patch("app.tools.memory_vault.CONTEXT_FILE", os.path.join(tmp_dir, "context.json")), \
             patch("app.tools.memory_vault.CONVERSATIONS_FILE", os.path.join(tmp_dir, "convos.json")), \
             patch("app.tools.memory_vault.DOCUMENTS_FILE", os.path.join(tmp_dir, "docs.json")):
            vault = MemoryVault()
            vault.record_conversation_turn("Mukil", "Apply for AI Engineer jobs")
            vault.record_conversation_turn("JARVIS", "Application package prepared")

            saved_doc = vault.save_important_document(
                title="Master Placement Resume",
                doc_type="resume",
                drive_link=MASTER_RESUME_URL,
                notes="Official resume for all tech applications",
            )
            assert saved_doc["title"] == "Master Placement Resume"

            docs = vault.list_documents()
            assert len(docs) == 1
            assert docs[0]["title"] == "Master Placement Resume"

            prompt_mem = vault.get_prompt_memory_context()
            assert "Master Placement Resume" in prompt_mem
            assert MASTER_RESUME_URL in prompt_mem


def test_drive_01_vault_manager():
    """DRIVE-01: DriveVaultManager returns master resume and 5TB vault links."""
    mgr = DriveVaultManager()
    assert mgr.get_master_resume_link() == MASTER_RESUME_URL
    assert mgr.get_master_vault_url() == MASTER_VAULT_URL

    summary = mgr.get_vault_summary()
    assert "MUKIL 5TB GOOGLE DRIVE MASTER VAULT MATRIX" in summary
    assert "SGC Billing Dual Vault" in summary


def test_brain_01_drive_and_memory_tool_dispatch():
    """BRAIN-01: AutonomousAgentBrain dispatches drive and memory tools."""
    brain = AutonomousAgentBrain(api_key="mock_key")

    # Test view_drive_vaults
    res, _ = brain.execute_tool("view_drive_vaults", {})
    assert "MUKIL 5TB GOOGLE DRIVE MASTER VAULT MATRIX" in res

    # Test save_memory_or_document
    res_mem, _ = brain.execute_tool(
        "save_memory_or_document",
        {
            "title": "Semester 7 Project Code",
            "doc_type": "project_code",
            "notes": "Agentic AI operating system codebase",
        },
    )
    assert "Saved to 5TB Drive Vault Index" in res_mem
    assert "Semester 7 Project Code" in res_mem
