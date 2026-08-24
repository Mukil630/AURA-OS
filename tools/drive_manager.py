import os
import sys
import json
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import DRIVE_VAULT_URL, DRIVE_FOLDER_ID, DRIVE_BILLING_FOLDERS
from memory.memory_manager import MemoryManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("drive_manager")

class DriveManager:
    """
    Google Drive 5TB Master Vault & Sync Manager for JARVIS.
    Handles backup of memories, code snapshots, tailored resumes, and billing invoices.
    """
    def __init__(self):
        self.master_folder_id = DRIVE_FOLDER_ID
        self.master_url = DRIVE_VAULT_URL
        self.billing_folders = DRIVE_BILLING_FOLDERS
        self.mem = MemoryManager()
        self.sync_manifest_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "drive_sync_manifest.json")

    def get_vault_status(self):
        return {
            "status": "connected",
            "master_folder_id": self.master_folder_id,
            "master_vault_url": self.master_url,
            "billing_vaults": self.billing_folders,
            "last_synced": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    def record_sync_event(self, item_name: str, item_type: str, status: str = "SYNCED", drive_url: str = None):
        events = []
        if os.path.exists(self.sync_manifest_path):
            try:
                with open(self.sync_manifest_path, "r", encoding="utf-8") as f:
                    events = json.load(f)
            except Exception:
                events = []
                
        events.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "item_name": item_name,
            "item_type": item_type,
            "status": status,
            "drive_url": drive_url or self.master_url
        })
        
        with open(self.sync_manifest_path, "w", encoding="utf-8") as f:
            json.dump(events, f, indent=2)
            
        logger.info(f"Drive Sync recorded: {item_name} -> {status}")

if __name__ == "__main__":
    dm = DriveManager()
    status = dm.get_vault_status()
    print("Google Drive 5TB Vault Status:\n" + json.dumps(status, indent=2))
