"""Global search (plan decision D-20): one endpoint the frontend's search box calls.

Searches what exists today: investigations and evidence. The response names the resource
types that cannot be searched yet, so the UI never implies it searched them.
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from Backend.App.Dependencies import get_db_session
from Backend.App.Schemas.Common import SuccessEnvelope, envelope
from Database.PostgreSQL.Repositories import CaseRepository, EvidenceRepository

router = APIRouter(tags=["Search"])

SEARCHED = ["CASE", "EVIDENCE"]
NOT_SEARCHABLE_YET = ["SOURCE", "FINDING", "REPORT"]


class SearchHit(BaseModel):
    type: Literal["CASE", "EVIDENCE"]
    id: uuid.UUID
    title: str
    subtitle: str
    case_id: uuid.UUID
    case_number: str


class SearchResults(BaseModel):
    query: str
    hits: list[SearchHit]
    searched_types: list[str]
    not_searchable_yet: list[str]


@router.get("/search", response_model=SuccessEnvelope[SearchResults], summary="Search investigations and evidence")
def search(
    q: str = Query(min_length=2, max_length=200, description="Case title/number, evidence filename/number or SHA-256 prefix"),
    limit: int = Query(default=8, ge=1, le=25, description="Maximum hits per resource type"),
    session: Session = Depends(get_db_session),
):
    text = q.strip()
    hits: list[SearchHit] = []
    for case in CaseRepository.search(session, text, limit=limit):
        hits.append(SearchHit(
            type="CASE", id=case.id, title=case.title, subtitle=f"{case.display_number} · {case.status}",
            case_id=case.id, case_number=case.display_number,
        ))
    for evidence, case_number, case_title in EvidenceRepository.search(session, text, limit=limit):
        number = f"CASE-{case_number:04d}"
        hits.append(SearchHit(
            type="EVIDENCE", id=evidence.id, title=evidence.original_filename,
            subtitle=f"{evidence.display_number} · {evidence.media_type} · {number} {case_title}",
            case_id=evidence.case_id, case_number=number,
        ))
    results = SearchResults(query=text, hits=hits, searched_types=SEARCHED, not_searchable_yet=NOT_SEARCHABLE_YET)
    return envelope(results, f"{len(hits)} result{'s' if len(hits) != 1 else ''}")
