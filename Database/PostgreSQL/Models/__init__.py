"""All PostgreSQL models. Importing this package registers every table on Base.metadata."""

from Database.PostgreSQL.Models.Case import Case
from Database.PostgreSQL.Models.Evidence import Evidence
from Database.PostgreSQL.Models.EvidenceMetadata import EvidenceMetadata
from Database.PostgreSQL.Models.InvestigationEvent import InvestigationEvent
from Database.PostgreSQL.Models.AnalysisJob import AnalysisJob
from Database.PostgreSQL.Models.AnalysisExecution import AnalysisExecution
from Database.PostgreSQL.Models.AnalysisResult import AnalysisResult
from Database.PostgreSQL.Models.AnalysisFinding import AnalysisFinding
from Database.PostgreSQL.Models.ArtifactRecord import ArtifactRecord
from Database.PostgreSQL.Models.OutboxEvent import OutboxCheckpoint, OutboxEvent
from Database.PostgreSQL.Models.Worker import WorkerProcess
from Database.PostgreSQL.Models.Notification import Notification

__all__ = [
    "Case", "Evidence", "EvidenceMetadata", "InvestigationEvent",
    "AnalysisJob", "AnalysisExecution", "AnalysisResult", "AnalysisFinding", "ArtifactRecord",
    "OutboxEvent", "OutboxCheckpoint", "WorkerProcess", "Notification",
]
