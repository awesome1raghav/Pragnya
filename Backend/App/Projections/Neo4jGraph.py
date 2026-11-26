"""Neo4j projection of the evidence graph: a rebuildable copy, never a source of truth.

The worker calls `tick()` when it is idle. It reads outbox events after the "neo4j" checkpoint; for every case with a
`graph.snapshot_created` event it replaces that case's subgraph with the case's latest snapshot (delete and
recreate in one Neo4j transaction, so running it twice gives the same graph). Then the checkpoint advances. If Neo4j
is down, nothing advances and the next tick retries. `rebuild()` (job PROJECTION_REBUILD) re-projects every case's
latest snapshot from PostgreSQL (replacing each case's subgraph; nodes of cases this database does not hold are left
alone) and moves the checkpoint to the newest event.

Nodes: label :NexNode plus :Case/:Evidence/:Source/:Finding; properties are the snapshot's scalar values plus case_id.
Relationships: CONTAINS, RETRIEVED_AS, CANDIDATE_VERSION, ABOUT, CITES, each with the `record` that supports it.
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from Backend.App.Config import Settings
from Backend.App.Realtime import Outbox
from Backend.App.Realtime.Cursor import GapSafeCursor
from Database.PostgreSQL.Models import Case, GraphSnapshot, OutboxCheckpoint, OutboxEvent

logger = logging.getLogger("nextron.projection.neo4j")
logging.getLogger("neo4j.notifications").setLevel(logging.WARNING)  # schema and planner notices are informational
CONSUMER = "neo4j"
LABELS = {"CASE": "Case", "EVIDENCE": "Evidence", "SOURCE": "Source", "FINDING": "Finding"}
RELATIONSHIPS = ("CONTAINS", "RETRIEVED_AS", "CANDIDATE_VERSION", "ABOUT", "CITES")
BATCH = 500


def _scalars(d: dict) -> dict:
    return {k: v for k, v in d.items() if k not in ("from", "to") and (v is None or isinstance(v, (str, int, float, bool)))}


class Neo4jGraph:
    def __init__(self, settings: Settings, factory: sessionmaker[Session]):
        self.settings, self.factory = settings, factory
        self._driver = None
        self._cursor: GapSafeCursor | None = None  # gap-safe: a late-committing lower sequence is not skipped

    @property
    def configured(self) -> bool:
        return bool(self.settings.NEO4J_URI)

    def driver(self):
        if self._driver is None:
            from neo4j import GraphDatabase

            self._driver = GraphDatabase.driver(self.settings.NEO4J_URI, auth=(self.settings.NEO4J_USER, self.settings.NEO4J_PASSWORD.get_secret_value()),
                                                connection_timeout=5, max_connection_lifetime=600)
            with self._driver.session() as s:
                s.run("CREATE CONSTRAINT nexnode_id IF NOT EXISTS FOR (n:NexNode) REQUIRE n.id IS UNIQUE").consume()
        return self._driver

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    # ── projecting ─────────────────────────────────────────────────────────────────────────
    def project_case(self, case_id: uuid.UUID, snap: GraphSnapshot | None) -> None:
        def work(tx):
            tx.run("MATCH (n:NexNode {case_id: $case}) DETACH DELETE n", case=str(case_id)).consume()
            if snap is None:
                return
            for kind, label in LABELS.items():
                rows = [{"id": n["id"], "props": _scalars(n) | {"case_id": str(case_id), "snapshot_id": str(snap.id)}} for n in snap.nodes if n["type"] == kind]
                for i in range(0, len(rows), BATCH):
                    tx.run(f"UNWIND $rows AS r CREATE (n:NexNode:{label}) SET n = r.props", rows=rows[i:i + BATCH]).consume()
            for rel in RELATIONSHIPS:
                rows = [{"a": e["from"], "b": e["to"], "props": _scalars(e)} for e in snap.edges if e["type"] == rel]
                for i in range(0, len(rows), BATCH):
                    tx.run(f"UNWIND $rows AS r MATCH (a:NexNode {{id: r.a}}) MATCH (b:NexNode {{id: r.b}}) CREATE (a)-[x:{rel}]->(b) SET x = r.props",
                           rows=rows[i:i + BATCH]).consume()

        with self.driver().session() as s:
            s.execute_write(work)

    @staticmethod
    def _latest(session: Session, case_id: uuid.UUID) -> GraphSnapshot | None:
        return session.scalars(select(GraphSnapshot).where(GraphSnapshot.case_id == case_id).order_by(GraphSnapshot.created_at.desc()).limit(1)).first()

    def _checkpoint(self, session: Session, *, lock: bool = False) -> OutboxCheckpoint:
        cp = session.get(OutboxCheckpoint, CONSUMER, with_for_update=lock)
        if cp is None:
            cp = OutboxCheckpoint(consumer=CONSUMER, last_sequence=0)
            session.add(cp)
            session.flush()
        return cp

    def tick(self, limit: int = 1000) -> int:
        """Project cases with new snapshots; returns how many cases were projected."""
        if not self.configured:
            return 0
        with self.factory() as session:
            cp = self._checkpoint(session, lock=True)
            if self._cursor is None or self._cursor.position < cp.last_sequence:
                self._cursor = GapSafeCursor(cp.last_sequence)
            events = [e for e in session.scalars(select(OutboxEvent).where(OutboxEvent.sequence > self._cursor.position)
                                                 .order_by(OutboxEvent.sequence).limit(limit)).all() if self._cursor.is_new(e.sequence)]
            cases = list(dict.fromkeys(e.case_id for e in events if e.event_type == "graph.snapshot_created" and e.case_id))
            for case_id in cases:
                self.project_case(case_id, self._latest(session, case_id))  # raises if Neo4j is down: nothing advances
            for e in events:
                self._cursor.mark(e.sequence)
            self._cursor.tick()
            if self._cursor.position != cp.last_sequence:
                cp.last_sequence = self._cursor.position
                session.commit()
            else:
                session.rollback()
            return len(cases)

    def rebuild(self) -> dict:
        with self.factory() as session:
            cp = self._checkpoint(session, lock=True)
            head = Outbox.latest_sequence(session)
            cases = session.scalars(select(Case.id).order_by(Case.case_number)).all()
            projected = 0
            for case_id in cases:
                snap = self._latest(session, case_id)
                if snap is not None:
                    self.project_case(case_id, snap)
                    projected += 1
            cp.last_sequence = max(cp.last_sequence, head)
            session.commit()
        self._cursor = None
        return {"cases_projected": projected, "checkpoint": head}

    # ── status ─────────────────────────────────────────────────────────────────────────────
    def status(self, session: Session) -> dict:
        head = Outbox.latest_sequence(session)
        cp = session.get(OutboxCheckpoint, CONSUMER)
        at = cp.last_sequence if cp else 0
        pending = session.scalar(select(OutboxEvent.sequence).where(OutboxEvent.sequence > at, OutboxEvent.event_type == "graph.snapshot_created")
                                 .order_by(OutboxEvent.sequence).limit(1))
        out = {"consumer": CONSUMER, "configured": self.configured, "checkpoint": at, "latest_sequence": head, "lag_events": max(head - at, 0),
               "snapshots_pending": pending is not None, "reachable": None, "nodes": None, "relationships": None, "server_version": None, "error": None}
        if not self.configured:
            out["error"] = "NEO4J_URI is not set; the projection is disabled"
            return out
        try:
            records, _, _ = self.driver().execute_query(
                "CALL dbms.components() YIELD versions WITH versions[0] AS v "
                "OPTIONAL MATCH (n:NexNode) WITH v, count(n) AS nodes OPTIONAL MATCH (:NexNode)-[r]->() RETURN v, nodes, count(r) AS rels")
            out.update(reachable=True, server_version=records[0]["v"], nodes=records[0]["nodes"], relationships=records[0]["rels"])
        except Exception as exc:  # noqa: BLE001 — reported, not raised
            out.update(reachable=False, error=f"{type(exc).__name__}: {str(exc)[:200]}")
            self.close()
        return out
