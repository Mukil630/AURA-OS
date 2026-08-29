"""Multi-Modal Output Dispatcher for Unified Voice, Image, Document & Text Delivery."""
import enum
import logging
import os
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("MultiModalDispatcher")


class MediaType(str, enum.Enum):
    TEXT = "TEXT"
    VOICE_AUDIO = "VOICE_AUDIO"
    PHOTO_IMAGE = "PHOTO_IMAGE"
    PDF_DOCUMENT = "PDF_DOCUMENT"


class DispatchedMessage(BaseModel):
    primary_media: MediaType = MediaType.TEXT
    text_content: str
    media_path: Optional[str] = None
    voice_audio_path: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MultiModalDispatcher:
    """Detects output media requirements and formats payloads for Telegram / Web / Voice clients."""

    def format_output(
        self,
        raw_text: str,
        produced_artifacts: Optional[List[str]] = None,
        prefer_voice: bool = False,
    ) -> DispatchedMessage:
        """Determines appropriate media encapsulation for output artifacts."""
        artifacts = produced_artifacts or []
        photo_path = None
        doc_path = None

        for art in artifacts:
            if not art or not isinstance(art, str) or not os.path.exists(art):
                continue
            lower_art = art.lower()
            if lower_art.endswith((".png", ".jpg", ".jpeg", ".webp")):
                photo_path = art
            elif lower_art.endswith((".pdf", ".csv", ".xlsx", ".json", ".zip")):
                doc_path = art

        if photo_path:
            return DispatchedMessage(
                primary_media=MediaType.PHOTO_IMAGE,
                text_content=raw_text,
                media_path=photo_path,
                metadata={"type": "screenshot_or_image"},
            )
        elif doc_path:
            return DispatchedMessage(
                primary_media=MediaType.PDF_DOCUMENT,
                text_content=raw_text,
                media_path=doc_path,
                metadata={"type": "document_or_report"},
            )
        else:
            return DispatchedMessage(
                primary_media=MediaType.VOICE_AUDIO if prefer_voice else MediaType.TEXT,
                text_content=raw_text,
                metadata={"type": "text_or_voice"},
            )
