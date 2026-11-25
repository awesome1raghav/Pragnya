"""
NEXTRON Database: PostgreSQL Declarative Base
"""

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime, timezone
import uuid


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )
