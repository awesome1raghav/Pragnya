"""In-process fan-out of outbox events to connected WebSocket clients.

Each connection subscribes with optional case and job filters and gets its own bounded queue. A client that
falls too far behind is disconnected rather than blocking everyone; it reconnects with `?after=<sequence>`
and the WebSocket endpoint replays what it missed from PostgreSQL. The hub itself stores nothing durable.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any

QUEUE_LIMIT = 1000


@dataclass(eq=False)
class Subscription:
    case_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(QUEUE_LIMIT))
    overflowed: bool = False

    def wants(self, message: dict[str, Any]) -> bool:
        if self.case_id is not None and message.get("case_id") != str(self.case_id):
            return False
        if self.job_id is not None and message.get("job_id") != str(self.job_id):
            return False
        return True


class Hub:
    def __init__(self) -> None:
        self._subscriptions: set[Subscription] = set()

    def subscribe(self, *, case_id: uuid.UUID | None = None, job_id: uuid.UUID | None = None) -> Subscription:
        sub = Subscription(case_id=case_id, job_id=job_id)
        self._subscriptions.add(sub)
        return sub

    def unsubscribe(self, sub: Subscription) -> None:
        self._subscriptions.discard(sub)

    @property
    def connections(self) -> int:
        return len(self._subscriptions)

    def publish(self, messages: list[dict[str, Any]]) -> None:
        for sub in list(self._subscriptions):
            for message in messages:
                if not sub.wants(message):
                    continue
                try:
                    sub.queue.put_nowait(message)
                except asyncio.QueueFull:
                    sub.overflowed = True
                    break
