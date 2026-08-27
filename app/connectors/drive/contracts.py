"""Data contracts for Google Drive Dual-Vault, File Metadata, and Checksum Verification."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import Field

from app.core.contracts.base import VersionedContractBase


class DriveFileContract(VersionedContractBase):
    """Metadata contract representing a file stored in Google Drive."""
    file_id: str = Field(default_factory=lambda: f"drv_{uuid4().hex[:12]}", description="Google Drive file ID.")
    name: str = Field(..., description="File name with extension.")
    mime_type: str = Field(default="application/octet-stream", description="Standard MIME type.")
    size_bytes: int = Field(default=0, ge=0, description="File byte size.")
    checksum_sha256: str = Field(..., description="SHA-256 integrity hash.")
    vault: str = Field(default="primary", description="'primary' or 'backup'.")
    parent_folder_id: str = Field(..., description="Google Drive parent folder ID.")
    parent_folder_path: str = Field(default="/MasterVault/", description="Logical vault path.")
    web_view_link: Optional[str] = Field(default=None, description="Drive web viewing URL.")
    is_trashed: bool = Field(default=False, description="True if moved to trash.")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp."
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last updated timestamp."
    )


class DriveStorageInfoContract(VersionedContractBase):
    """Dynamic Google Drive storage quota diagnostic."""
    total_bytes: int = Field(..., description="Total storage allocated in bytes.")
    used_bytes: int = Field(..., description="Total storage consumed in bytes.")
    free_bytes: int = Field(..., description="Free storage available in bytes.")
    usage_percent: float = Field(..., description="Usage percentage (0.0 to 100.0).")
    quota_type: str = Field(default="unlimited_enterprise", description="Storage plan tier.")


class DualVaultSyncResult(VersionedContractBase):
    """Audit result for a primary-to-backup vault file synchronization."""
    sync_id: str = Field(default_factory=lambda: f"sync_{uuid4().hex[:10]}", description="Unique sync job ID.")
    file_id: str = Field(..., description="Target file ID.")
    file_name: str = Field(..., description="File name synchronized.")
    primary_vault_id: str = Field(..., description="Primary vault folder ID.")
    backup_vault_id: str = Field(..., description="Backup vault folder ID.")
    primary_checksum: str = Field(..., description="Primary vault SHA256 checksum.")
    backup_checksum: str = Field(..., description="Backup vault SHA256 checksum.")
    is_synchronized: bool = Field(..., description="True if checksums match perfectly.")
    sync_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Sync completion timestamp."
    )
    message: str = Field(default="Synchronized successfully.", description="Status message.")
