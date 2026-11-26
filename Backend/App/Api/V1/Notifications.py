"""Notification APIs: derived from outbox events; only the read state changes."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from Backend.App.Dependencies import get_db_session
from Backend.App.Realtime import Notifications
from Backend.App.Realtime.Notifications import NotificationRead, NotificationSummary
from Backend.App.Schemas.Common import ErrorEnvelope, SuccessEnvelope, envelope
from Backend.App.Schemas.Pagination import MAX_PAGE_SIZE, PaginatedEnvelope, paginated

router = APIRouter(tags=["Notifications"])


@router.get("/notifications", response_model=PaginatedEnvelope[NotificationRead], summary="Notifications, newest first")
def list_notifications(
    unread: bool = Query(default=False, description="Only unread notifications"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    session: Session = Depends(get_db_session),
):
    items, total = Notifications.list_page(session, page=page, page_size=page_size, unread_only=unread)
    return paginated(items, "Notifications retrieved successfully", page=page, page_size=page_size, total_items=total)


@router.get("/notifications/summary", response_model=SuccessEnvelope[NotificationSummary], summary="Unread and total counts")
def notification_summary(session: Session = Depends(get_db_session)):
    return envelope(Notifications.summary(session), "Notification counts retrieved successfully")


@router.patch("/notifications/{notification_id}/read", response_model=SuccessEnvelope[NotificationRead],
              responses={404: {"model": ErrorEnvelope, "description": "NOTIFICATION_NOT_FOUND"}}, summary="Mark one notification read")
def read_notification(notification_id: uuid.UUID, session: Session = Depends(get_db_session)):
    return envelope(Notifications.mark_read(session, notification_id), "Notification marked read")


@router.post("/notifications/read-all", response_model=SuccessEnvelope[dict], summary="Mark every notification read")
def read_all(session: Session = Depends(get_db_session)):
    return envelope({"marked": Notifications.mark_all_read(session)}, "All notifications marked read")
