"""Comprehensive 20-Scenario Test Suite for Phase 8.3 Google Drive Dual-Vault Connector."""
import hashlib
import pytest

from app.connectors.credential_manager import CredentialManager
from app.connectors.drive.connector import GoogleDriveConnector
from app.connectors.policy import ConnectorPolicyEngine
from app.connectors.router import CapabilityRouter
from app.core.contracts.connector import ConnectorExecutionRequest
from app.core.enums import ConnectorStatus, ConnectorType


# ── Scenario 01: Connector Registration ───────────────────────────────────────────────
def test_scenario_01_connector_registration():
    router = CapabilityRouter()
    drive_conn = GoogleDriveConnector(is_mock=True)
    router.register_connector(drive_conn)

    connectors = router.list_connectors()
    assert len(connectors) == 1
    assert connectors[0].connector_id == "connector_google_drive"
    assert connectors[0].connector_type == ConnectorType.GOOGLE_DRIVE
    assert connectors[0].is_mock is True


# ── Scenario 02: Capability Registration ─────────────────────────────────────────────
def test_scenario_02_capability_registration():
    drive_conn = GoogleDriveConnector(is_mock=True)
    caps = drive_conn.list_capabilities()
    assert len(caps) == 9
    cap_ids = [c.capability_id for c in caps]

    assert "drive.get_storage_info" in cap_ids
    assert "drive.search" in cap_ids
    assert "drive.list" in cap_ids
    assert "drive.get_metadata" in cap_ids
    assert "drive.upload" in cap_ids
    assert "drive.download" in cap_ids
    assert "drive.create_folder" in cap_ids
    assert "drive.sync_vault" in cap_ids
    assert "drive.trash_file" in cap_ids


# ── Scenario 03: OAuth Credential Isolation ───────────────────────────────────────────
def test_scenario_03_oauth_credential_isolation():
    cred_mgr = CredentialManager()
    raw_oauth = "ya29.a0AfH6SMD_superSecretOAuthToken123456789"

    contract = cred_mgr.set_credential(
        provider=ConnectorType.GOOGLE_DRIVE,
        token=raw_oauth,
        user_id="mukil",
    )

    assert contract.masked_value == "ya29****6789"
    assert raw_oauth not in contract.masked_value

    resolved = cred_mgr.get_credential(ConnectorType.GOOGLE_DRIVE, user_id="mukil")
    assert resolved == raw_oauth


# ── Scenario 04: Mock Search Files ───────────────────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_04_mock_search_files():
    router = CapabilityRouter()
    drive_conn = GoogleDriveConnector(is_mock=True)
    router.register_connector(drive_conn)

    req = ConnectorExecutionRequest(
        capability_id="drive.search",
        parameters={"query_text": "Resume"},
    )
    res = await router.dispatch(req)

    assert res.success is True
    assert res.status_code == 200
    assert res.data["match_count"] >= 1
    assert "Resume" in res.data["matches"][0]["name"]


# ── Scenario 05: Mock Upload File with Checksum ───────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_05_mock_upload_file_with_checksum():
    router = CapabilityRouter()
    drive_conn = GoogleDriveConnector(is_mock=True)
    router.register_connector(drive_conn)

    content = b"SGC BILLING INVOICE #2026-08 - TOTAL: $4,500.00"
    expected_hash = hashlib.sha256(content).hexdigest()

    req = ConnectorExecutionRequest(
        capability_id="drive.upload",
        parameters={
            "file_name": "SGC_Invoice_2026_08.pdf",
            "content_bytes": content.decode("utf-8"),
            "mime_type": "application/pdf",
            "parent_folder_id": GoogleDriveConnector.SGC_BILLING_1_ID,
        },
    )
    res = await router.dispatch(req)

    assert res.success is True
    assert res.status_code == 200
    assert res.data["checksum_sha256"] == expected_hash
    assert res.data["parent_folder_id"] == GoogleDriveConnector.SGC_BILLING_1_ID
    assert res.data["idempotent_hit"] is False


# ── Scenario 06: Mock Download File Integrity ─────────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_06_mock_download_file_integrity():
    router = CapabilityRouter()
    drive_conn = GoogleDriveConnector(is_mock=True)
    router.register_connector(drive_conn)

    req = ConnectorExecutionRequest(
        capability_id="drive.download",
        parameters={"file_id": GoogleDriveConnector.MASTER_RESUME_FILE_ID},
    )
    res = await router.dispatch(req)

    assert res.success is True
    assert res.status_code == 200
    assert res.data["integrity_verified"] is True
    assert res.data["name"] == "Mukil_Master_Resume.pdf"


# ── Scenario 07: File Metadata Retrieval ──────────────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_07_file_metadata_retrieval():
    router = CapabilityRouter()
    drive_conn = GoogleDriveConnector(is_mock=True)
    router.register_connector(drive_conn)

    req = ConnectorExecutionRequest(
        capability_id="drive.get_metadata",
        parameters={"file_id": GoogleDriveConnector.MASTER_RESUME_FILE_ID},
    )
    res = await router.dispatch(req)

    assert res.success is True
    assert res.data["file_id"] == GoogleDriveConnector.MASTER_RESUME_FILE_ID
    assert res.data["mime_type"] == "application/pdf"
    assert res.data["parent_folder_id"] == GoogleDriveConnector.PRIMARY_VAULT_ID


# ── Scenario 08: Dynamic Storage Quota Retrieval ──────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_08_dynamic_storage_quota_retrieval():
    router = CapabilityRouter()
    drive_conn = GoogleDriveConnector(is_mock=True)
    router.register_connector(drive_conn)

    req = ConnectorExecutionRequest(capability_id="drive.get_storage_info", parameters={})
    res = await router.dispatch(req)

    assert res.success is True
    assert res.status_code == 200
    assert res.data["total_bytes"] > 0
    assert res.data["free_bytes"] > 0
    assert res.data["usage_percent"] >= 0.0


# ── Scenario 09: Upload Checksum Verification ─────────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_09_upload_checksum_verification():
    drive_conn = GoogleDriveConnector(is_mock=True)
    data = b"Arbitrary binary data payload for checksum test"
    expected_sha = hashlib.sha256(data).hexdigest()

    req = ConnectorExecutionRequest(
        capability_id="drive.upload",
        parameters={"file_name": "data.bin", "content_bytes": data.decode("utf-8")},
    )
    res = await drive_conn.execute_capability(req)

    assert res.success is True
    assert res.data["checksum_sha256"] == expected_sha


# ── Scenario 10: Duplicate / Idempotent Upload Handling ───────────────────────────────
@pytest.mark.anyio
async def test_scenario_10_duplicate_idempotent_upload():
    router = CapabilityRouter()
    drive_conn = GoogleDriveConnector(is_mock=True)
    router.register_connector(drive_conn)

    payload = {
        "file_name": "IdempotentTest.pdf",
        "content_bytes": "Exact same content for idempotency test",
        "parent_folder_id": GoogleDriveConnector.PRIMARY_VAULT_ID,
    }

    # Upload 1
    r1 = await router.dispatch(ConnectorExecutionRequest(capability_id="drive.upload", parameters=payload))
    assert r1.success is True
    assert r1.data["idempotent_hit"] is False
    first_file_id = r1.data["file_id"]

    # Upload 2 (Exact duplicate)
    r2 = await router.dispatch(ConnectorExecutionRequest(capability_id="drive.upload", parameters=payload))
    assert r2.success is True
    assert r2.data["idempotent_hit"] is True
    assert r2.data["file_id"] == first_file_id  # Returns existing file ID without duplicating


# ── Scenario 11: Download Integrity Verification Error ────────────────────────────────
@pytest.mark.anyio
async def test_scenario_11_download_integrity_verification_error():
    router = CapabilityRouter()
    drive_conn = GoogleDriveConnector(is_mock=True)
    router.register_connector(drive_conn)

    req = ConnectorExecutionRequest(
        capability_id="drive.download",
        parameters={"file_id": "non_existent_file_id_999"},
    )
    res = await router.dispatch(req)

    assert res.success is False
    assert res.status_code == 404
    assert "does not exist" in res.error_message.lower()


# ── Scenario 12: Path Permission Boundary Rejection ───────────────────────────────────
@pytest.mark.anyio
async def test_scenario_12_path_permission_boundary_rejection():
    router = CapabilityRouter()
    drive_conn = GoogleDriveConnector(is_mock=True)
    router.register_connector(drive_conn)

    # Attempting to upload to restricted path /System/ or /Private/
    req = ConnectorExecutionRequest(
        capability_id="drive.upload",
        parameters={
            "file_name": "exploit.sh",
            "path": "/System/config.sys",
            "content_bytes": "malicious content",
        },
    )
    res = await router.dispatch(req)

    assert res.success is False
    assert res.status_code == 403
    assert "permission denied" in res.error_message.lower()


# ── Scenario 13: Emergency Kill Switch Blocks Drive ───────────────────────────────────
@pytest.mark.anyio
async def test_scenario_13_emergency_kill_switch_blocks_drive():
    policy = ConnectorPolicyEngine()
    router = CapabilityRouter(policy_engine=policy)
    drive_conn = GoogleDriveConnector(is_mock=True)
    router.register_connector(drive_conn)

    # Deactivate drive connector
    policy.disable_connector("connector_google_drive")
    assert policy.is_connector_enabled("connector_google_drive") is False

    req = ConnectorExecutionRequest(capability_id="drive.get_storage_info", parameters={})
    res = await router.dispatch(req)

    assert res.success is False
    assert res.status_code == 503
    assert "emergency kill-switch" in res.error_message.lower()

    # Re-enable
    policy.enable_connector("connector_google_drive")
    res2 = await router.dispatch(req)
    assert res2.success is True


# ── Scenario 14: Rate Limiting Enforcement (429) ──────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_14_rate_limiting_enforcement_429():
    policy = ConnectorPolicyEngine()
    router = CapabilityRouter(policy_engine=policy)
    drive_conn = GoogleDriveConnector(is_mock=True)
    router.register_connector(drive_conn)

    # Set ceiling of 2 calls/min for drive upload
    policy.set_rate_limit("drive.upload", 2)
    assert policy.check_and_consume_rate_limit("drive.upload") is True
    assert policy.check_and_consume_rate_limit("drive.upload") is True

    # 3rd call should trigger 429
    req = ConnectorExecutionRequest(
        capability_id="drive.upload",
        parameters={"file_name": "doc.pdf", "content_bytes": "test"},
    )
    res = await router.dispatch(req)

    assert res.success is False
    assert res.status_code == 429
    assert "rate limit exceeded" in res.error_message.lower()


# ── Scenario 15: Google API 401 Handling ──────────────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_15_google_api_401_handling():
    # Live mode without credentials returns 401
    drive_conn = GoogleDriveConnector(is_mock=False)
    req = ConnectorExecutionRequest(capability_id="drive.get_storage_info", parameters={})
    res = await drive_conn.execute_capability(req, credentials=None)

    assert res.success is False
    assert res.status_code == 401
    assert "authentication failure" in res.error_message.lower()


# ── Scenario 16: Payload Size Boundary Rejection (413) ────────────────────────────────
@pytest.mark.anyio
async def test_scenario_16_payload_size_boundary_rejection_413():
    drive_conn = GoogleDriveConnector(is_mock=True)
    req = ConnectorExecutionRequest(
        capability_id="drive.upload",
        parameters={
            "file_name": "massive_file.zip",
            "size_bytes": 200 * 1024 * 1024,  # 200 MB (Limit is 100MB)
        },
    )
    res = await drive_conn.execute_capability(req)

    assert res.success is False
    assert res.status_code == 413
    assert "payload too large" in res.error_message.lower()


# ── Scenario 17: Dual Vault Synchronization Success ───────────────────────────────────
@pytest.mark.anyio
async def test_scenario_17_dual_vault_synchronization_success():
    router = CapabilityRouter()
    drive_conn = GoogleDriveConnector(is_mock=True)
    router.register_connector(drive_conn)

    # 1. Upload to Primary Vault
    up_req = ConnectorExecutionRequest(
        capability_id="drive.upload",
        parameters={"file_name": "MasterPlan2026.pdf", "content_bytes": "Strategic AI Agent Blueprint 2026"},
    )
    up_res = await router.dispatch(up_req)
    file_id = up_res.data["file_id"]

    # 2. Sync to Backup Vault
    sync_req = ConnectorExecutionRequest(
        capability_id="drive.sync_vault",
        parameters={"file_id": file_id},
    )
    sync_res = await router.dispatch(sync_req)

    assert sync_res.success is True
    assert sync_res.status_code == 200
    assert sync_res.data["is_synchronized"] is True
    assert sync_res.data["primary_checksum"] == sync_res.data["backup_checksum"]


# ── Scenario 18: Dual Vault Checksum Mismatch Detection ───────────────────────────────
@pytest.mark.anyio
async def test_scenario_18_dual_vault_checksum_mismatch_detection():
    router = CapabilityRouter()
    drive_conn = GoogleDriveConnector(is_mock=True)
    router.register_connector(drive_conn)

    # 1. Upload file
    up_res = await router.dispatch(
        ConnectorExecutionRequest(
            capability_id="drive.upload",
            parameters={"file_name": "CriticalFinance.pdf", "content_bytes": "Financial statement"},
        )
    )
    file_id = up_res.data["file_id"]

    # 2. Force corrupt checksum during sync
    corrupt_req = ConnectorExecutionRequest(
        capability_id="drive.sync_vault",
        parameters={"file_id": file_id, "force_corrupt_checksum": "corrupted_sha256_hash_99999"},
    )
    sync_res = await router.dispatch(corrupt_req)

    assert sync_res.success is False
    assert sync_res.status_code == 422
    assert sync_res.data["is_synchronized"] is False
    assert "mismatch" in sync_res.error_message.lower()


# ── Scenario 19: Safe Trash File Soft Delete ───────────────────────────────────────────
@pytest.mark.anyio
async def test_scenario_19_safe_trash_file_soft_delete():
    router = CapabilityRouter()
    drive_conn = GoogleDriveConnector(is_mock=True)
    router.register_connector(drive_conn)

    # Upload temporary file
    up_res = await router.dispatch(
        ConnectorExecutionRequest(
            capability_id="drive.upload",
            parameters={"file_name": "TempScratch.txt", "content_bytes": "Temporary scratch"},
        )
    )
    file_id = up_res.data["file_id"]

    # Move to trash
    trash_res = await router.dispatch(
        ConnectorExecutionRequest(
            capability_id="drive.trash_file",
            parameters={"file_id": file_id},
        )
    )
    assert trash_res.success is True
    assert trash_res.data["is_trashed"] is True
    assert trash_res.data["action"] == "moved_to_trash"

    # Search should no longer surface trashed file
    search_res = await router.dispatch(
        ConnectorExecutionRequest(
            capability_id="drive.search",
            parameters={"file_name": "TempScratch.txt"},
        )
    )
    assert search_res.data["match_count"] == 0


# ── Scenario 20: Complete Real File Lifecycle Workflow ────────────────────────────────
@pytest.mark.anyio
async def test_scenario_20_complete_file_lifecycle_workflow():
    """
    Step 1: Get dynamic storage quota
    Step 2: Upload SGC Billing PDF to Primary Vault (SHA256 computed)
    Step 3: Introspect metadata
    Step 4: Replicate to Backup Vault & Cross-verify Checksums
    Step 5: Verify Idempotent re-upload
    """
    router = CapabilityRouter()
    drive_conn = GoogleDriveConnector(is_mock=True)
    router.register_connector(drive_conn)

    # 1. Quota
    r1 = await router.dispatch(ConnectorExecutionRequest(capability_id="drive.get_storage_info", parameters={}))
    assert r1.success is True

    # 2. Upload
    doc_payload = b"SGC BILLING INVOICE #8892 - CLIENT: GLOBAL LOGISTICS - AMOUNT: $12,400.00"
    r2 = await router.dispatch(
        ConnectorExecutionRequest(
            capability_id="drive.upload",
            parameters={
                "file_name": "SGC_Invoice_8892.pdf",
                "content_bytes": doc_payload.decode("utf-8"),
                "parent_folder_id": GoogleDriveConnector.SGC_BILLING_1_ID,
            },
        )
    )
    assert r2.success is True
    file_id = r2.data["file_id"]
    sha256 = r2.data["checksum_sha256"]

    # 3. Metadata
    r3 = await router.dispatch(ConnectorExecutionRequest(capability_id="drive.get_metadata", parameters={"file_id": file_id}))
    assert r3.success is True
    assert r3.data["checksum_sha256"] == sha256

    # 4. Sync to Backup Vault (Dual Vault Sync)
    r4 = await router.dispatch(ConnectorExecutionRequest(capability_id="drive.sync_vault", parameters={"file_id": file_id}))
    assert r4.success is True
    assert r4.data["is_synchronized"] is True

    # 5. Idempotent check
    r5 = await router.dispatch(
        ConnectorExecutionRequest(
            capability_id="drive.upload",
            parameters={
                "file_name": "SGC_Invoice_8892.pdf",
                "content_bytes": doc_payload.decode("utf-8"),
                "parent_folder_id": GoogleDriveConnector.SGC_BILLING_1_ID,
            },
        )
    )
    assert r5.success is True
    assert r5.data["idempotent_hit"] is True
    assert r5.data["file_id"] == file_id
