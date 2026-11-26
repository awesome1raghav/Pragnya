"""NEX-CM case lifecycle rules. Status changes only here, never through PATCH."""

from Backend.App.Core.Exceptions import ErrorCode, NextronError
from Database.PostgreSQL.Models import Case

ARCHIVED = "ARCHIVED"


def ensure_writable(case: Case) -> None:
    if case.status == ARCHIVED:
        raise NextronError(409, ErrorCode.CASE_ARCHIVED, "The case is archived; reopen it before changing it")


def archive(case: Case) -> str:
    """Archive from any non-archived status; returns the status archived from."""
    ensure_writable(case)
    previous = case.status
    case.archived_from_status = previous
    case.status = ARCHIVED
    return previous


def reopen(case: Case) -> str:
    """Restore the status the case had when archived; returns that status."""
    if case.status != ARCHIVED:
        raise NextronError(409, ErrorCode.CASE_NOT_ARCHIVED, "Only an archived case can be reopened")
    restored = case.archived_from_status or "OPEN"
    case.status = restored
    case.archived_from_status = None
    return restored


def on_evidence_preserved(case: Case) -> str | None:
    """First preserved evidence moves an OPEN case to EVIDENCE_COLLECTION. Returns the new status if changed."""
    if case.status == "OPEN":
        case.status = "EVIDENCE_COLLECTION"
        return case.status
    return None
