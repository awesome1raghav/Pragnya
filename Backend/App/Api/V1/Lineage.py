"""Lineage API (NEX-MOC): the case's current candidate relationships between versions of media."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from Backend.App.Dependencies import get_db_session
from Backend.App.Modules.NexCm.Service import get_case
from Backend.App.Schemas.Common import ErrorEnvelope, SuccessEnvelope, envelope
from Database.PostgreSQL.Models import Evidence, MediaFingerprint, MediaRelationship, SourceRecord

router = APIRouter(tags=["Lineage (NEX-MOC)"])


class LineageNode(BaseModel):
    evidence_id: uuid.UUID
    evidence_number: str
    filename: str
    media_type: str
    source_type: str
    received_at: datetime
    fingerprinted: bool
    sources: list[dict] = Field(description="Sources this evidence was retrieved from, with their claimed publication time")


class LineageEdge(BaseModel):
    relationship_id: uuid.UUID
    evidence_a: uuid.UUID
    evidence_b: uuid.UUID
    kind: str
    status: str = Field(description="Always CANDIDATE until reviewed (Step 7)")
    similarity: float
    earlier_observed: uuid.UUID | None
    ordering_basis: str | None
    basis: dict
    created_at: datetime


class Lineage(BaseModel):
    case_id: uuid.UUID
    nodes: list[LineageNode]
    edges: list[LineageEdge]
    note: str = ("Edges are candidates from fingerprint similarity. Similarity is not proof of common origin, and "
                 "'earlier observed' rests on the publication times the sources claim.")


@router.get("/cases/{case_id}/lineage", response_model=SuccessEnvelope[Lineage], responses={404: {"model": ErrorEnvelope}},
            summary="Current candidate relationships between the case's evidence")
def case_lineage(case_id: uuid.UUID, session: Session = Depends(get_db_session)):
    get_case(session, case_id)
    evidence = session.scalars(select(Evidence).where(Evidence.case_id == case_id).order_by(Evidence.evidence_number)).all()
    printed = set(session.scalars(select(MediaFingerprint.evidence_id).where(MediaFingerprint.case_id == case_id).group_by(MediaFingerprint.evidence_id)))
    sources: dict[uuid.UUID, list[dict]] = {}
    for s in session.scalars(select(SourceRecord).where(SourceRecord.case_id == case_id, SourceRecord.evidence_id.is_not(None))):
        sources.setdefault(s.evidence_id, []).append({"source_id": str(s.id), "source_number": s.display_number, "url": s.normalized_url,
                                                     "claimed_publication_time": s.claimed_publication_time, "title": s.title})
    edges = session.scalars(select(MediaRelationship).where(MediaRelationship.case_id == case_id, MediaRelationship.superseded_at.is_(None))
                            .order_by(MediaRelationship.similarity.desc())).all()
    data = Lineage(
        case_id=case_id,
        nodes=[LineageNode(evidence_id=e.id, evidence_number=e.display_number, filename=e.original_filename, media_type=e.media_type,
                           source_type=e.source_type, received_at=e.received_at, fingerprinted=e.id in printed, sources=sources.get(e.id, []))
               for e in evidence],
        edges=[LineageEdge(relationship_id=r.id, evidence_a=r.evidence_a, evidence_b=r.evidence_b, kind=r.kind, status=r.status,
                           similarity=r.similarity, earlier_observed=r.earlier_observed, ordering_basis=r.ordering_basis, basis=r.basis,
                           created_at=r.created_at) for r in edges],
    )
    return envelope(data, "Lineage retrieved successfully")
