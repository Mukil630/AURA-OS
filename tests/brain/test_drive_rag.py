"""Unit & Integration Tests for Drive RAG & Semantic Retrieval Engine."""
import asyncio
import pytest
from app.brain.drive_rag_engine import DriveRAGEngine
from app.brain.master_orchestrator import MasterOrchestrator


def test_01_drive_folder_registration(tmp_path):
    index_f = str(tmp_path / "rag_index.json")
    reg_f = str(tmp_path / "folders_reg.json")
    rag = DriveRAGEngine(index_file=index_f, registry_file=reg_f)

    # Register Drive Folder URL
    url = "https://drive.google.com/drive/folders/155EqYOwPJ2Fc9QfqVSrZu5VnYzZgRcyZ"
    folder = rag.register_drive_folder(alias="sgc_billing_vault_1", folder_url_or_id=url, description="SGC Billing Bills")

    assert folder.alias == "sgc_billing_vault_1"
    assert folder.folder_id == "155EqYOwPJ2Fc9QfqVSrZu5VnYzZgRcyZ"
    assert "folders/155EqYOw" in folder.folder_url


def test_02_drive_document_indexing_and_rag_search(tmp_path):
    index_f = str(tmp_path / "rag_index.json")
    reg_f = str(tmp_path / "folders_reg.json")
    rag = DriveRAGEngine(index_file=index_f, registry_file=reg_f)

    # Index 2 sample billing documents
    rag.index_document(
        folder_alias="sgc_billing_vault_1",
        filename="Bill_101_Rajesh_Contractor.pdf",
        content_text="Customer: Rajesh Contractor, 20L Tractor Emulsion, 5L Primer. Total: Rs 14,500. Date: 2026-08-25",
        metadata={"customer": "Rajesh", "amount": 14500, "status": "PAID"}
    )
    rag.index_document(
        folder_alias="sgc_billing_vault_1",
        filename="Bill_102_Suresh_Builders.pdf",
        content_text="Customer: Suresh Builders, 50L Apex Ultima Weatherproof. Total: Rs 38,000. Date: 2026-08-26",
        metadata={"customer": "Suresh", "amount": 38000, "status": "PENDING"}
    )

    # Search for Rajesh's bill
    hits = rag.query_rag_context("Rajesh contractor paint bill amount")
    assert len(hits) >= 1
    assert "Rajesh" in hits[0]["filename"]
    assert hits[0]["metadata"]["amount"] == 14500

    # Search for Suresh's bill
    hits2 = rag.query_rag_context("Suresh builders Apex Ultima")
    assert len(hits2) >= 1
    assert "Suresh" in hits2[0]["filename"]


def test_03_master_orchestrator_drive_rag_integration(tmp_path):
    async def run_test():
        index_f = str(tmp_path / "rag_index.json")
        reg_f = str(tmp_path / "folders_reg.json")
        rag = DriveRAGEngine(index_file=index_f, registry_file=reg_f)
        
        rag.index_document(
            folder_alias="sgc_billing_vault",
            filename="Bill_200_Karur_Decor.pdf",
            content_text="Customer: Karur Decor, 10L Royale Luxury Paint, Total: Rs 12,000",
            metadata={"customer": "Karur Decor", "amount": 12000}
        )

        orchestrator = MasterOrchestrator(drive_rag=rag)

        # 1. Test Drive URL Registration prompt
        resp1 = await orchestrator.process_user_input("https://drive.google.com/drive/folders/1iaHzDzC7KiJk2FlMdS7eNW7vkYxDeaXZ billing folder")
        assert resp1.response_type == "RAG_DRIVE_ANSWER"
        assert "Linked Successfully" in resp1.text
        assert "1iaHzDzC7KiJk2FlMdS7eNW7vkYxDeaXZ" in resp1.text

        # 2. Test RAG document query prompt
        resp2 = await orchestrator.process_user_input("Karur Decor bill details and amount")
        assert resp2.response_type == "RAG_DRIVE_ANSWER"
        assert "Karur Decor" in resp2.text
        assert len(resp2.rag_matches) >= 1

    asyncio.run(run_test())


def test_04_sgc_billing_sync_and_financial_summary(tmp_path):
    index_f = str(tmp_path / "rag_index.json")
    reg_f = str(tmp_path / "folders_reg.json")
    rag = DriveRAGEngine(index_file=index_f, registry_file=reg_f)

    # Sync live SGC billing data
    sync_res = rag.sync_sgc_billing_data()
    assert sync_res["status"] == "SUCCESS"
    assert sync_res["folder_id"] == "11KMBP0HHa2AFl30zjL8-a_-BQk9MgWM9"

    # Verify Financial Summary
    summary = rag.get_sgc_financial_summary()
    assert summary["drive_folder_id"] == "11KMBP0HHa2AFl30zjL8-a_-BQk9MgWM9"
    assert summary["total_bills_count"] >= 6
    assert summary["total_billed_amount"] > 0
    assert summary["total_collected_amount"] >= 866
    assert summary["total_pending_amount"] > 0

    # Query customer MSK Fabrics
    hits = rag.query_rag_context("M.S.K Fabrics pending balance", folder_alias="sgc_billing_active_vault")
    assert len(hits) >= 1
    assert "M.S.K Fabrics" in hits[0]["filename"]
    assert hits[0]["metadata"]["netAmount"] == 5488
