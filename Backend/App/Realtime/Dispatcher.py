"""The outbox dispatcher: runs inside each API process as one asyncio task started by the lifespan.

Every OUTBOX_POLL_SECONDS it reads committed outbox events (from any process: the worker writes most of
them), lets the notification consumer process its batch, then hands the new events to the WebSocket hub.
Database work runs in the thread pool. If PostgreSQL is down the loop logs, waits and tries again.
"""

import asyncio
import logging

from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool

from Backend.App.Realtime import Outbox
from Backend.App.Realtime.Cursor import GapSafeCursor
from Backend.App.Realtime.Hub import Hub
from Backend.App.Realtime.Notifications import NotificationConsumer

logger = logging.getLogger("nextron.dispatcher")


class Dispatcher:
    def __init__(self, session_factory: sessionmaker[Session], hub: Hub, *, poll_seconds: float):
        self.factory = session_factory
        self.hub = hub
        self.poll_seconds = poll_seconds
        self.cursor: GapSafeCursor | None = None
        self.notifications = NotificationConsumer()
        self.delivered = 0
        self.healthy = False

    def _start_position(self) -> int:
        with self.factory() as session:
            return Outbox.latest_sequence(session)

    def _fetch(self) -> list[dict]:
        with self.factory() as session:
            events = Outbox.events_after(session, self.cursor.position, limit=1000)
            messages = []
            for e in events:
                if self.cursor.is_new(e.sequence):
                    messages.append(Outbox.as_message(e))
                    self.cursor.mark(e.sequence)
            self.cursor.tick()
            return messages

    def _notify(self) -> None:
        with self.factory() as session:
            self.notifications.process(session)

    async def poll_once(self) -> int:
        if self.cursor is None:
            self.cursor = GapSafeCursor(await run_in_threadpool(self._start_position))
        messages = await run_in_threadpool(self._fetch)
        await run_in_threadpool(self._notify)  # first, so a client refetching on job.completed finds its notification
        if messages:
            self.hub.publish(messages)
            self.delivered += len(messages)
        self.healthy = True
        return len(messages)

    async def run(self) -> None:
        while True:
            try:
                await self.poll_once()
                await asyncio.sleep(self.poll_seconds)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.healthy = False
                logger.warning("Outbox dispatch failed; retrying", exc_info=logger.isEnabledFor(logging.DEBUG))
                await asyncio.sleep(max(self.poll_seconds, 2.0))
