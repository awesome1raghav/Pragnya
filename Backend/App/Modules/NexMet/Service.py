"""NEX-MET Metadata Intelligence: extract from the preserved original and record a new version.

Extraction reads the stored original, never the staging copy, and records the evidence's SHA-256 as its
input. Since Step 3 it runs inside T-MIR (Orchestration/TMir/Executors.py), in two halves:

  extract()  reads the file and runs Pillow / FFprobe; touches no database, may be slow, may time out;
  record()   adds the metadata version and its custody event to the caller's transaction (no commit),
             so T-MIR commits it together with the execution's result: both exist, or neither does.

A failure is recorded as a FAILED or UNAVAILABLE version, not raised.
"""

from sqlalchemy.orm import Session

from Backend.App.Modules.NexEvd import ChainOfCustody
from Backend.App.Modules.NexMet import MetadataExtractor
from Backend.App.Storage.StorageInterface import EvidenceStorage
from Database.PostgreSQL.Models import Evidence, EvidenceMetadata

_EVENT = {
    "EXTRACTED": ChainOfCustody.METADATA_EXTRACTED,
    "UNAVAILABLE": ChainOfCustody.METADATA_UNAVAILABLE,
    "FAILED": ChainOfCustody.METADATA_FAILED,
}


def extract(storage: EvidenceStorage, evidence: Evidence, *, ffprobe: str, timeout_seconds: float) -> MetadataExtractor.ExtractionResult:
    path = storage.local_path(evidence.storage_key)
    if path is None or not path.is_file():
        return MetadataExtractor.ExtractionResult("FAILED", "storage", "n/a", {}, None, "The preserved original is not readable")
    return MetadataExtractor.extract(path, evidence.media_type, ffprobe=ffprobe, timeout_seconds=timeout_seconds)


def record(
    session: Session, evidence: Evidence, result: MetadataExtractor.ExtractionResult, actor: str, *, job_id: str | None = None
) -> EvidenceMetadata:
    row = EvidenceMetadata(
        evidence_id=evidence.id,
        status=result.status,
        extractor=result.extractor,
        extractor_version=result.extractor_version,
        input_sha256=evidence.sha256,
        summary=result.summary,
        raw=result.raw,
        error=result.error,
    )
    session.add(row)
    session.flush()
    ChainOfCustody.record(session, evidence, _EVENT[result.status], actor, {
        "metadata_id": str(row.id),
        "extractor": result.extractor,
        "extractor_version": result.extractor_version,
        "input_sha256": evidence.sha256,
        "error": result.error,
        "job_id": job_id,
    })
    return row
