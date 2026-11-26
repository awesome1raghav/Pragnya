"""Execution vocabulary shared by T-MIR, the Job Service, every module and the API.

The value sets are defined once, on the database models (their CHECK constraints), and mirrored here as
enums; an import-time assertion keeps the two identical.
"""

from enum import StrEnum

from Database.PostgreSQL.Models.AnalysisExecution import EXECUTION_STATES, EXECUTION_TERMINAL_STATES, EXPLAINED_STATES, SCOPE_KINDS
from Database.PostgreSQL.Models.AnalysisJob import JOB_STATES, JOB_TERMINAL_STATES, JOB_TYPES


class ExecutionState(StrEnum):
    """A module execution's state (Flowchart B §5.1, plus UNAVAILABLE: conflict C-10)."""

    PENDING = "PENDING"
    QUEUED = "QUEUED"
    WAITING_FOR_DEPENDENCIES = "WAITING_FOR_DEPENDENCIES"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"
    UNAVAILABLE = "UNAVAILABLE"  # the module's tool or model is not installed or not licensed

    @property
    def terminal(self) -> bool:
        return self.value in EXECUTION_TERMINAL_STATES

    @property
    def produced_output(self) -> bool:
        """True when downstream modules may consume this execution's result."""
        return self in (ExecutionState.COMPLETED, ExecutionState.PARTIALLY_COMPLETED)

    @property
    def needs_reason(self) -> bool:
        return self.value in EXPLAINED_STATES


class SkipReason(StrEnum):
    NOT_APPLICABLE = "NOT_APPLICABLE"   # the module does not apply to this evidence or pair (e.g. audio forensics on an image)
    UPSTREAM_FAILED = "UPSTREAM_FAILED"  # a REQUIRED upstream ended without output
    NO_INPUT = "NO_INPUT"               # nothing to work on (e.g. no comparable pair was proposed)
    SUPERSEDED = "SUPERSEDED"           # newer evidence or sources replaced the planned inputs
    CANCELLED = "CANCELLED"             # the job was cancelled before this module started


class FailureReason(StrEnum):
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"
    LEASE_EXPIRED = "LEASE_EXPIRED"    # the worker stopped heartbeating (crash); retried as a new attempt
    INVALID_INPUT = "INVALID_INPUT"
    TOOL_UNAVAILABLE = "TOOL_UNAVAILABLE"


class JobState(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    @property
    def terminal(self) -> bool:
        return self.value in JOB_TERMINAL_STATES


class JobType(StrEnum):
    INVESTIGATION_RUN = "INVESTIGATION_RUN"      # T-MIR: the 12 coordinated modules
    SOURCE_RESOLUTION = "SOURCE_RESOLUTION"      # Source Service: NEX-SRC retrieval
    REPORT_GENERATION = "REPORT_GENERATION"      # Report Service: NEX-RPT
    PROJECTION_REBUILD = "PROJECTION_REBUILD"    # Neo4j / Qdrant rebuild from PostgreSQL


class ScopeKind(StrEnum):
    EVIDENCE = "EVIDENCE"
    PAIR = "PAIR"
    CASE = "CASE"


assert {s.value for s in ExecutionState} == set(EXECUTION_STATES)
assert {s.value for s in JobState} == set(JOB_STATES)
assert {s.value for s in JobType} == set(JOB_TYPES)
assert {s.value for s in ScopeKind} == set(SCOPE_KINDS)
