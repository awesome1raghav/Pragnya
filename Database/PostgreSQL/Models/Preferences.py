"""Operator preferences (Step 8): one row per operator, versioned for optimistic concurrency.

Two browser tabs editing settings at once must not silently overwrite each other: every update names the version it
was based on, and a stale version is refused (409 PREFERENCES_CONFLICT) instead of applied.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from Database.PostgreSQL.Base import Base


class OperatorPreferences(Base):
    __tablename__ = "operator_preferences"
    __table_args__ = (CheckConstraint("version >= 1", name="version_positive"),)

    operator: Mapped[str] = mapped_column(String(100), primary_key=True)
    preferences: Mapped[dict] = mapped_column(JSONB, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
