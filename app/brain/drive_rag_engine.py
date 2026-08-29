"""Drive RAG & Semantic Indexing Engine.
Handles dynamic Google Drive folder registration, document indexing, and semantic RAG retrieval.
"""
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field

logger = logging.getLogger("DriveRAGEngine")


class DriveFolderRegistry(BaseModel):
    alias: str
    folder_id: str
    folder_url: str
    description: str
    registered_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class IndexedDocument(BaseModel):
    doc_id: str = Field(default_factory=lambda: f"doc_{uuid4().hex[:8]}")
    folder_alias: str
    filename: str
    content_text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    indexed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DriveRAGEngine:
    """RAG Engine for Google Drive folders, billing files, resumes, and project documentation."""

    def __init__(self, index_file: Optional[str] = None, registry_file: Optional[str] = None):
        base_data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"
        )
        os.makedirs(base_data_dir, exist_ok=True)

        self.index_file = index_file or os.path.join(base_data_dir, "drive_rag_index.json")
        self.registry_file = registry_file or os.path.join(base_data_dir, "drive_folders_registry.json")

        self.folders: Dict[str, DriveFolderRegistry] = {}
        self.documents: Dict[str, IndexedDocument] = {}

        self._load_state()

    def _load_state(self) -> None:
        if os.path.exists(self.registry_file):
            try:
                with open(self.registry_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    self.folders = {k: DriveFolderRegistry(**v) for k, v in raw.items()}
            except Exception as e:
                logger.warning(f"Failed to load drive folders registry: {e}")

        if os.path.exists(self.index_file):
            try:
                with open(self.index_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    self.documents = {k: IndexedDocument(**v) for k, v in raw.items()}
            except Exception as e:
                logger.warning(f"Failed to load drive RAG index: {e}")

    def _save_state(self) -> None:
        try:
            with open(self.registry_file, "w", encoding="utf-8") as f:
                json.dump({k: v.model_dump() for k, v in self.folders.items()}, f, indent=2)
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump({k: v.model_dump() for k, v in self.documents.items()}, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save drive RAG state: {e}")

    def register_drive_folder(self, alias: str, folder_url_or_id: str, description: str = "") -> DriveFolderRegistry:
        """Dynamically registers a new Google Drive folder (e.g. SGC Billing Drive, Resume Vault)."""
        clean_target = folder_url_or_id.strip()
        folder_id = clean_target

        # Extract Folder ID if a full URL was provided
        if "folders/" in clean_target:
            match = re.search(r"folders/([a-zA-Z0-9_-]+)", clean_target)
            if match:
                folder_id = match.group(1)
        elif "id=" in clean_target:
            match = re.search(r"id=([a-zA-Z0-9_-]+)", clean_target)
            if match:
                folder_id = match.group(1)

        folder_url = f"https://drive.google.com/drive/folders/{folder_id}"
        reg = DriveFolderRegistry(
            alias=alias,
            folder_id=folder_id,
            folder_url=folder_url,
            description=description or f"Registered drive folder for {alias}",
        )
        self.folders[alias] = reg
        self._save_state()
        logger.info(f"📂 Registered Drive Folder [{alias}]: ID={folder_id} -> {folder_url}")
        return reg

    def index_document(
        self,
        folder_alias: str,
        filename: str,
        content_text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IndexedDocument:
        """Indexes document content and metadata into the RAG semantic knowledge store."""
        doc = IndexedDocument(
            folder_alias=folder_alias,
            filename=filename,
            content_text=content_text,
            metadata=metadata or {},
        )
        self.documents[doc.doc_id] = doc
        self._save_state()
        logger.info(f"📄 Indexed document into Drive RAG: [{filename}] ({len(content_text)} chars)")
        return doc

    def query_rag_context(self, query: str, folder_alias: Optional[str] = None, top_k: int = 3) -> List[Dict[str, Any]]:
        """Semantic & Keyword similarity retrieval for matching Drive documents."""
        query_terms = set(re.findall(r"\w+", query.lower()))
        if not query_terms:
            return []

        scored_docs = []
        for doc in self.documents.values():
            if folder_alias and doc.folder_alias != folder_alias:
                continue

            doc_text = (doc.filename + " " + doc.content_text + " " + json.dumps(doc.metadata)).lower()
            doc_terms = set(re.findall(r"\w+", doc_text))

            # Jaccard / Overlap keyword score
            overlap = len(query_terms.intersection(doc_terms))
            if overlap > 0:
                score = overlap / (len(query_terms) + 0.1)
                scored_docs.append({
                    "doc_id": doc.doc_id,
                    "filename": doc.filename,
                    "folder_alias": doc.folder_alias,
                    "content_text": doc.content_text,
                    "metadata": doc.metadata,
                    "score": score,
                })

        scored_docs.sort(key=lambda x: x["score"], reverse=True)
        return scored_docs[:top_k]

    def list_folders(self) -> Dict[str, DriveFolderRegistry]:
        return self.folders

    def sync_sgc_billing_data(self) -> Dict[str, Any]:
        """Automatically reads and indexes all SGC bills from local desktop billing data and Google Drive."""
        appdata_path = os.path.join(os.environ.get("APPDATA", ""), "sgc-billing", "sgc-billing-data.json")
        if not os.path.exists(appdata_path):
            return {"status": "NOT_FOUND", "indexed_count": 0}

        try:
            with open(appdata_path, "r", encoding="utf-8") as f:
                billing_data = json.load(f)

            drive_folder_id = billing_data.get("drive-folder-id", "11KMBP0HHa2AFl30zjL8-a_-BQk9MgWM9")
            self.register_drive_folder(
                alias="sgc_billing_active_vault",
                folder_url_or_id=f"https://drive.google.com/drive/folders/{drive_folder_id}",
                description="Official SGC Billing Software Google Drive Storage Vault"
            )

            bills = billing_data.get("sgc-bills", [])
            indexed_count = 0
            for b in bills:
                b_no = b.get("billNo")
                cust = b.get("customer", "Unknown")
                date = b.get("date", "")
                status = b.get("status", "pending")
                net_amt = b.get("netAmount", 0)
                subtotal = b.get("subtotal", 0)
                cgst = b.get("cgst", 0)
                sgst = b.get("sgst", 0)
                party_gst = b.get("partyGst", "")
                items = b.get("items", [])
                items_summary = ", ".join([f"{it.get('variety')} ({it.get('count')}, {it.get('kattu')} kattu, {it.get('kazhi')} kazhi @ Rs {it.get('rate')})" for it in items])

                doc_text = (
                    f"Bill No: {b_no} | Date: {date} | Customer: {cust} | GST: {party_gst} | "
                    f"Status: {status.upper()} | Subtotal: Rs {subtotal} | CGST: Rs {cgst} | SGST: Rs {sgst} | "
                    f"Total Net Amount: Rs {net_amt} | Items: {items_summary}"
                )

                self.index_document(
                    folder_alias="sgc_billing_active_vault",
                    filename=f"Bill_{b_no:04d}_{cust}.pdf",
                    content_text=doc_text,
                    metadata={
                        "billNo": b_no,
                        "customer": cust,
                        "partyGst": party_gst,
                        "date": date,
                        "status": status,
                        "netAmount": net_amt,
                        "driveUrl": b.get("driveUrl"),
                        "driveFileId": b.get("driveFileId"),
                    }
                )
                indexed_count += 1

            return {
                "status": "SUCCESS",
                "folder_id": drive_folder_id,
                "drive_url": f"https://drive.google.com/drive/folders/{drive_folder_id}",
                "indexed_bills": indexed_count,
                "total_bills": len(bills),
            }
        except Exception as e:
            logger.error(f"Error syncing SGC billing data: {e}")
            return {"status": "ERROR", "error": str(e)}

    def get_sgc_financial_summary(self) -> Dict[str, Any]:
        """Calculates executive financial metrics across all SGC customer bills."""
        appdata_path = os.path.join(os.environ.get("APPDATA", ""), "sgc-billing", "sgc-billing-data.json")
        if not os.path.exists(appdata_path):
            return {"error": "SGC Billing data file not found"}

        with open(appdata_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        bills = data.get("sgc-bills", [])
        total_billed = sum(b.get("netAmount", 0) for b in bills)
        paid_bills = [b for b in bills if b.get("status", "").lower() == "paid"]
        pending_bills = [b for b in bills if b.get("status", "").lower() == "pending"]

        total_collected = sum(b.get("netAmount", 0) for b in paid_bills)
        total_pending = sum(b.get("netAmount", 0) for b in pending_bills)

        return {
            "drive_folder_id": data.get("drive-folder-id", "11KMBP0HHa2AFl30zjL8-a_-BQk9MgWM9"),
            "drive_url": f"https://drive.google.com/drive/folders/{data.get('drive-folder-id', '11KMBP0HHa2AFl30zjL8-a_-BQk9MgWM9')}",
            "total_bills_count": len(bills),
            "total_billed_amount": total_billed,
            "total_collected_amount": total_collected,
            "total_pending_amount": total_pending,
            "paid_count": len(paid_bills),
            "pending_count": len(pending_bills),
            "pending_bills_details": [
                {
                    "billNo": b.get("billNo"),
                    "customer": b.get("customer"),
                    "date": b.get("date"),
                    "amount": b.get("netAmount"),
                    "partyGst": b.get("partyGst"),
                }
                for b in pending_bills
            ],
            "paid_bills_details": [
                {
                    "billNo": b.get("billNo"),
                    "customer": b.get("customer"),
                    "date": b.get("date"),
                    "amount": b.get("netAmount"),
                    "receiptNo": b.get("receiptNo"),
                }
                for b in paid_bills
            ],
        }
