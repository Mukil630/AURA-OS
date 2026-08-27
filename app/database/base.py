"""Base Declarative Class and Mixins for SQLAlchemy Models."""
from datetime import datetime, timezone
import json
from typing import Any, Dict
from sqlalchemy import DateTime, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models in MUKIL MASTER AGENT."""
    pass


class TimestampMixin:
    """Mixin adding standardized created_at and updated_at UTC timestamps."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


def dump_json(obj: Any) -> str:
    """Helper to serialize complex dicts to JSON text for SQLite/PostgreSQL compatibility."""
    if obj is None:
        return "{}"
    if isinstance(obj, str):
        return obj
    return json.dumps(obj, default=str)


def load_json(json_str: Any) -> Dict[str, Any]:
    """Helper to parse JSON text back to dictionary."""
    if not json_str:
        return {}
    if isinstance(json_str, dict):
        return json_str
    try:
        return json.loads(json_str)
    except Exception:
        return {}
