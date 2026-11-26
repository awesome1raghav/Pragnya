"""Live events over WebSocket: /ws/events, /ws/jobs/{job_id}, /ws/cases/{case_id}.

Protocol (server -> client, JSON):
  {"type": "event", "sequence": n, "event_type": ..., ...}   one outbox event (see Realtime/Outbox.as_message)
  {"type": "replay_complete", "after": a, "latest": n}       everything after `?after=` has been sent
  {"type": "heartbeat", "latest": n}                         every 25 s while idle

Without `after` the stream starts at the newest event (live only). A client resumes by reconnecting with
`?after=<last sequence it processed>`: missed events are replayed from PostgreSQL first, then live events follow. The same event is never sent twice on one connection.
Browsers must connect from an allowed origin (CORS_ORIGINS); clients without an Origin header are accepted
(the API binds to 127.0.0.1 and has no authentication yet: archive §17.1).
"""

import asyncio
import contextlib
import uuid
from collections import deque

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from Backend.App.Realtime import Outbox

router = APIRouter(tags=["Live events"])

HEARTBEAT_SECONDS = 25.0
REPLAY_BATCH = 500


def _replay(factory, after: int, case_id, job_id) -> list[dict]:
    with factory() as session:
        return [Outbox.as_message(e) for e in Outbox.events_after(session, after, limit=REPLAY_BATCH, case_id=case_id, job_id=job_id)]


def _latest(factory) -> int:
    with factory() as session:
        return Outbox.latest_sequence(session)


async def _serve(websocket: WebSocket, after: int | None, case_id: uuid.UUID | None, job_id: uuid.UUID | None) -> None:
    app = websocket.app
    origin = websocket.headers.get("origin")
    if origin and origin not in app.state.settings.CORS_ORIGINS:
        await websocket.close(code=1008, reason="Origin not allowed")
        return
    await websocket.accept()
    hub, factory = app.state.hub, app.state.session_factory
    subscription = hub.subscribe(case_id=case_id, job_id=job_id)  # before replay, so nothing falls between the two
    live_only = after is None
    if live_only:  # "from now": no replay; what the dispatcher has not yet fanned out still arrives through the hub
        dispatched = app.state.dispatcher.cursor
        after = dispatched.position if dispatched is not None else await run_in_threadpool(_latest, factory)
    sent: set[int] = set()
    order: deque[int] = deque()

    async def send(message: dict) -> None:
        seq = message["sequence"]
        if seq <= after or seq in sent:  # the client already has everything up to `after`
            return
        sent.add(seq)
        order.append(seq)
        if len(order) > 20_000:
            sent.discard(order.popleft())
        await websocket.send_json({"type": "event"} | message)

    async def reader() -> None:
        with contextlib.suppress(WebSocketDisconnect):
            while True:
                text = await websocket.receive_text()
                if text == "ping":
                    await websocket.send_json({"type": "pong"})

    reading = asyncio.create_task(reader())
    try:
        cursor = after
        while not live_only:
            batch = await run_in_threadpool(_replay, factory, cursor, case_id, job_id)
            for message in batch:
                await send(message)
            if len(batch) < REPLAY_BATCH:
                break
            cursor = batch[-1]["sequence"]
        latest = await run_in_threadpool(_latest, factory)
        await websocket.send_json({"type": "replay_complete", "after": after, "latest": latest})

        while not reading.done():
            if subscription.overflowed:
                await websocket.close(code=1013, reason="Client too slow; reconnect with ?after=")
                return
            getter = asyncio.ensure_future(subscription.queue.get())
            done, _ = await asyncio.wait({getter, reading}, timeout=HEARTBEAT_SECONDS, return_when=asyncio.FIRST_COMPLETED)
            if getter in done:
                await send(getter.result())
            else:
                getter.cancel()
                if not reading.done():
                    dispatcher = app.state.dispatcher
                    latest = dispatcher.cursor.position if dispatcher.cursor else latest
                    await websocket.send_json({"type": "heartbeat", "latest": latest})
    except (WebSocketDisconnect, RuntimeError):
        pass  # the client went away mid-send
    finally:
        hub.unsubscribe(subscription)
        reading.cancel()
        with contextlib.suppress(asyncio.CancelledError, WebSocketDisconnect, RuntimeError):
            await reading


@router.websocket("/ws/events")
async def ws_events(websocket: WebSocket, after: int | None = Query(default=None, ge=0), case_id: uuid.UUID | None = None,
                    job_id: uuid.UUID | None = None):
    await _serve(websocket, after, case_id, job_id)


@router.websocket("/ws/jobs/{job_id}")
async def ws_job(websocket: WebSocket, job_id: uuid.UUID, after: int | None = Query(default=None, ge=0)):
    await _serve(websocket, after, None, job_id)


@router.websocket("/ws/cases/{case_id}")
async def ws_case(websocket: WebSocket, case_id: uuid.UUID, after: int | None = Query(default=None, ge=0)):
    await _serve(websocket, after, case_id, None)
