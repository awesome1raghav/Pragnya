/* The NEXTRON API's response shapes, mirrored from the backend's OpenAPI (http://localhost:8000/docs).
   Field names stay snake_case, exactly as the API sends them. Change these only together with the backend. */

export type Meta = { request_id: string; timestamp: string };
export type Envelope<T> = { success: true; message: string; data: T; meta: Meta };
export type Pagination = { page: number; page_size: number; total_items: number; total_pages: number; has_next: boolean; has_previous: boolean };
export type Paginated<T> = { success: true; message: string; data: T[]; pagination: Pagination; meta: Meta };
export type ErrorBody = { code: string; message: string; details: unknown };

/* ── cases (NEX-CM) ── */
export const CASE_STATUSES = ['OPEN', 'EVIDENCE_COLLECTION', 'INVESTIGATION_IN_PROGRESS', 'REVIEW_REQUIRED', 'REVIEW_COMPLETED', 'REPORT_AVAILABLE', 'CLOSED', 'ARCHIVED'] as const;
export type CaseStatus = (typeof CASE_STATUSES)[number];
export const CASE_PRIORITIES = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] as const;
export type CasePriority = (typeof CASE_PRIORITIES)[number];
export const CASE_CATEGORIES = ['MEDIA_MANIPULATION', 'SYNTHETIC_MEDIA', 'SOURCE_VERIFICATION', 'CONTEXT_VERIFICATION', 'OTHER'] as const;
export type CaseCategory = (typeof CASE_CATEGORIES)[number];

export type Case = {
  case_id: string;
  case_number: string;
  title: string;
  description: string | null;
  objectives: string | null;
  category: CaseCategory;
  status: CaseStatus;
  priority: CasePriority;
  tags: string[];
  notes: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
  revision: number;
  evidence_count: number;
  last_activity_at: string;
};
export type CaseInput = { title: string; description?: string | null; objectives?: string | null; category?: CaseCategory; priority?: CasePriority; tags?: string[]; notes?: string | null };
export type CasePatch = Partial<CaseInput>;
export type CaseSortKey = 'created_at' | 'updated_at' | 'last_activity_at' | 'title' | 'priority' | 'case_number' | 'status';
export type CaseQuery = { search?: string; status?: CaseStatus[]; priority?: CasePriority[]; sort_by?: CaseSortKey; sort_order?: 'asc' | 'desc'; page?: number; page_size?: number; hide_test_records?: boolean };

export type CaseStatistics = { total_cases: number; active_cases: number; by_status: Record<CaseStatus, number>; by_priority: Record<CasePriority, number>; total_evidence: number };
export type CaseEvidenceStatistics = { case_id: string; evidence_total: number; evidence_by_media_type: Record<MediaType, number>; evidence_total_bytes: number; event_count: number };
export type CaseSummary = { case: Case; statistics: CaseEvidenceStatistics; recent_events: InvestigationEvent[]; last_activity_at: string };

/* ── events (append-only lifecycle and custody record) ── */
export type InvestigationEvent = { event_id: string; sequence: number; event_type: string; case_id: string; evidence_id: string | null; actor: string; payload: Record<string, unknown>; occurred_at: string };
export type EventPage = { success: true; message: string; data: InvestigationEvent[]; cursor: { after: number; next_after: number | null; has_more: boolean; limit: number }; meta: Meta };

/* ── evidence (NEX-CAP / NEX-EVD) ── */
export const MEDIA_TYPES = ['IMAGE', 'VIDEO', 'AUDIO'] as const;
export type MediaType = (typeof MEDIA_TYPES)[number];
export const SOURCE_TYPES = ['USER_UPLOAD', 'SHARED_FILE', 'SCREENSHOT', 'SCREEN_RECORDING', 'SOURCE_RETRIEVAL'] as const;
export type SourceType = (typeof SOURCE_TYPES)[number];
export const ACQUISITION_METHODS = ['DIRECT_UPLOAD', 'SHARE_INTENT', 'SCREEN_CAPTURE', 'CONNECTOR_RETRIEVAL'] as const;
export type AcquisitionMethod = (typeof ACQUISITION_METHODS)[number];

export type Evidence = {
  evidence_id: string;
  evidence_number: string;
  case_id: string;
  filename: string;
  declared_content_type: string | null;
  media_type: MediaType;
  detected_format: string;
  mime_type: string;
  file_size: number;
  sha256: string;
  hash_algorithm: 'SHA-256';
  preservation_status: 'PRESERVED';
  source_type: SourceType;
  acquisition_method: AcquisitionMethod;
  description: string | null;
  acquired_by: string;
  received_at: string;
  preserved_at: string;
  created_at: string;
};
export type EvidenceListItem = Evidence & { case_number: string; case_title: string };
export type JobReference = { job_id: string; job_number: string; state: JobState };
export type UploadedEvidence = Evidence & { duplicates_in_case: { evidence_id: string; evidence_number: string }[]; analysis_job: JobReference | null };
export type EvidenceQuery = { case_id?: string; media_type?: MediaType; search?: string; page?: number; page_size?: number };
export type EvidenceStatistics = { total_evidence: number; by_media_type: Record<MediaType, number>; by_preservation_status: Record<string, number>; total_bytes: number };

export type IntegrityVerification = { evidence_id: string; result: 'MATCH' | 'MISMATCH' | 'MISSING'; recorded_sha256: string; computed_sha256: string | null; recorded_size: number; computed_size: number | null; verified_at: string; note: string };
export type IntegrityState = { evidence_id: string; recorded_sha256: string; hash_algorithm: 'SHA-256'; recorded_size: number; preserved_at: string; last_verification: IntegrityVerification | null };

/* ── metadata (NEX-MET) ── */
export type MetadataStatus = 'EXTRACTED' | 'UNAVAILABLE' | 'FAILED';
export type Metadata = { metadata_id: string; evidence_id: string; status: MetadataStatus; extractor: string; extractor_version: string; input_sha256: string; extracted_at: string; version_count: number; summary: Record<string, unknown>; raw: Record<string, unknown> | null; error: string | null };

/* ── system and health ── */
export type Liveness = { status: 'ALIVE'; service: string; version: string; environment: string };
export type ReadinessCheck = { status: 'PASS' | 'FAIL'; reachable?: boolean; migrations_current?: boolean; latency_ms?: number | null; writable?: boolean; reason: string | null };
export type Readiness = { status: 'READY'; checks: { database: ReadinessCheck; storage: ReadinessCheck } };
export type DatabaseStatus = {
  status: 'HEALTHY' | 'DEGRADED'; database: 'postgresql'; server_version: string; database_name: string; latency_ms: number;
  migrations: { current: string[]; head: string[]; up_to_date: boolean };
  connection_pool: { checked_out: number | null; idle: number | null; overflow: number | null; maximum: number | null };
  checked_at: string; last_successful_check: string;
};
export type StorageStatus = { status: 'HEALTHY'; backend: 'local-filesystem'; writable: boolean; free_bytes: number | null; max_upload_bytes: number; checked_at: string };

export type ModuleStatus = 'IMPLEMENTED' | 'PARTIAL' | 'NOT_IMPLEMENTED';
export type ModuleInfo = { module_id: string; number: number; name: string; group: string; executed_by: 'DOMAIN_SERVICE' | 'T-MIR' | 'SOURCE_JOB' | 'HUMAN_REVIEW' | 'REPORT_JOB'; status: ModuleStatus; upstream: string[]; downstream: string[]; capabilities: string[]; endpoints: string[]; note: string | null };
export type ModuleEdge = { upstream: string; downstream: string; kind: 'REQUIRED' | 'CONDITIONAL' | 'OPTIONAL'; reason: string };
export type ModuleCatalogue = { source: string; groups: string[]; modules: ModuleInfo[]; edges: ModuleEdge[]; tmir: { status: ModuleStatus; coordinates: string[] }; execution_tracking: 'PERSISTED' };

/* ── search ── */
export type SearchHitType = 'CASE' | 'EVIDENCE' | 'SOURCE' | 'FINDING' | 'REPORT' | 'REVIEW';
export type SearchHit = { type: SearchHitType; id: string; title: string; subtitle: string; case_id: string; case_number: string; evidence_id: string | null };
export type SearchResults = { query: string; hits: SearchHit[]; searched_types: string[]; not_searchable_yet: string[] };

/* ── jobs, T-MIR runs and analysis (plan Step 3) ── */
export const JOB_STATES = ['QUEUED', 'RUNNING', 'COMPLETED', 'PARTIALLY_COMPLETED', 'FAILED', 'CANCELLED'] as const;
export type JobState = (typeof JOB_STATES)[number];
export type JobType = 'INVESTIGATION_RUN' | 'SOURCE_RESOLUTION' | 'REPORT_GENERATION' | 'PROJECTION_REBUILD';
export type ExecutionState = 'PENDING' | 'QUEUED' | 'WAITING_FOR_DEPENDENCIES' | 'RUNNING' | 'COMPLETED' | 'PARTIALLY_COMPLETED' | 'FAILED' | 'CANCELLED' | 'SKIPPED' | 'UNAVAILABLE';
export type JobProgress = { planned: number; finished: number; by_state: Partial<Record<ExecutionState, number>>; current: string | null };
export type Job = {
  job_id: string; job_number: string; job_type: JobType; case_id: string; case_number: string | null; evidence_id: string | null; evidence_number: string | null;
  state: JobState; priority: number; requested_by: string; parameters: Record<string, unknown>; progress: JobProgress | null;
  attempt: number; max_attempts: number; cancel_requested: boolean; error: { code: string; message: string } | null; worker_id: string | null;
  heartbeat_at: string | null; available_at: string; created_at: string; started_at: string | null; finished_at: string | null; duration_ms: number | null;
};
export type JobQuery = { state?: JobState; active?: boolean; case_id?: string; evidence_id?: string; job_type?: JobType; page?: number; page_size?: number };
export type PlanEntry = {
  key: string; module_id: string; module_name: string; group: string; scope_kind: 'EVIDENCE' | 'PAIR' | 'CASE'; scope_ref: string; evidence_id: string | null;
  applicable: boolean; state: ExecutionState; reason: string | null; detail: string | null; execution_id: string | null; result_id: string | null;
  reused_from_job_id: string | null; interrupted_attempts: string[]; limitations: string[];
};
export type Execution = {
  execution_id: string; job_id: string; module_id: string; module_name: string; scope_kind: string; scope_ref: string; attempt: number; state: ExecutionState;
  state_reason: string | null; state_detail: string | null; input_fingerprint: string; module_version: string; tool_versions: Record<string, string>;
  error: { errors: { code: string; message: string; retryable: boolean }[] } | null; result_id: string | null;
  created_at: string; started_at: string | null; finished_at: string | null; duration_ms: number | null;
};
export type Run = Job & { plan: PlanEntry[]; executions: Execution[] };
export type Finding = {
  finding_id: string; result_id: string; module_id: string; module_name: string; evidence_ids: string[]; assertion: 'OBSERVATION' | 'INFERENCE' | 'INCONCLUSIVE';
  finding_type: string; title: string; description: string | null; score: number | null; score_kind: string | null; confidence: number | null;
  confidence_basis: string | null; payload: Record<string, unknown>; created_at: string;
};
export type Region = { x: number; y: number; w: number; h: number; frame_seconds: number | null };
export type TimeRange = { start_seconds: number; end_seconds: number };
export type FindingPayload = { region: Region | null; time_range: TimeRange | null; supporting_artifact_ids: string[]; limitations: string[]; measurement: Record<string, unknown> };
export type Artifact = { artifact_id: string; kind: 'FRAME' | 'FRAME_SET' | 'AUDIO_TRACK' | 'THUMBNAIL' | 'HEATMAP' | 'FEATURE_VECTOR' | 'FINGERPRINT' | 'OTHER'; mime_type: string; sha256: string; size_bytes: number; evidence_id: string | null; execution_id: string | null; attributes: Record<string, unknown>; created_at: string };
export type EvidenceModuleResult = { evidence_id: string; evidence_number: string; filename: string; media_type: MediaType; applicable: boolean; latest: Execution | null; result_id: string | null; status: ExecutionState | null; status_reason: string | null; limitations: string[]; tool_versions: Record<string, string>; findings: Finding[]; artifacts: Artifact[] };
export type ModuleResults = { module_id: string; module_name: string; case_id: string; evidence: EvidenceModuleResult[] };
export type ModuleAnalysis = { module_id: string; module_name: string; group: string; applicable: boolean; latest: Execution | null; current_result_id: string | null };
export type EvidenceAnalysis = { evidence_id: string; latest_job: Job | null; jobs: Job[]; modules: ModuleAnalysis[]; findings: Finding[]; artifacts: Artifact[] };
export type AnalysisResult = { result_id: string; execution_id: string; job_id: string; case_id: string; module_id: string; module_name: string; status: ExecutionState; schema_version: string; envelope: Record<string, unknown>; created_at: string; superseded_at: string | null };

/* ── notifications and workers ── */
export type Notification = { notification_id: string; sequence: number; event_type: string; severity: 'INFO' | 'WARNING' | 'ALERT'; title: string; body: string | null; link: string | null; case_id: string | null; job_id: string | null; created_at: string; read_at: string | null };
export type NotificationSummary = { unread: number; total: number };
export type WorkerInfo = { worker_id: string; hostname: string; pid: number; version: string; state: 'RUNNING' | 'STOPPED'; alive: boolean; current_job_id: string | null; started_at: string; heartbeat_at: string; stopped_at: string | null };
export type WorkersStatus = { alive: number; workers: WorkerInfo[]; lease_seconds: number; checked_at: string };

/* ── live events (WebSocket /ws/events) ── */
export type LiveEvent = { type: 'event'; sequence: number; event_id: string; schema_version: string; event_type: string; aggregate_type: string; aggregate_id: string; case_id: string | null; job_id: string | null; module_id: string | null; payload: Record<string, unknown>; created_at: string | null };
export type LiveMessage = LiveEvent | { type: 'replay_complete'; after: number; latest: number } | { type: 'heartbeat'; latest: number } | { type: 'pong' };

/* ── sources (NEX-SRC) and lineage (NEX-MOC), plan Step 5 ── */
export type SourceState = 'PENDING' | 'RETRIEVED' | 'METADATA_ONLY' | 'UNAVAILABLE' | 'RESTRICTED' | 'NOT_FOUND' | 'UNSUPPORTED' | 'RATE_LIMITED' | 'BLOCKED' | 'FAILED';
export type Source = {
  source_id: string; source_number: string; case_id: string; url: string; normalized_url: string; platform: string; state: SourceState; state_detail: string | null;
  revision: number; title: string | null; claimed_publication_time: string | null; evidence_id: string | null; notes: string | null; created_by: string;
  created_at: string; last_retrieved_at: string | null; job_id: string | null;
};
export type SourceObservation = {
  revision: number; connector: string; outcome: SourceState; detail: string | null; requested_url: string; final_url: string | null;
  redirects: { url: string; address: string | null; status: number | null }[]; http_status: number | null; content_type: string | null;
  bytes_received: number | null; media_sha256: string | null; evidence_id: string | null; metadata: Record<string, unknown>; retrieved_at: string;
};
export type Connector = { connector: string; available: boolean; covers: string; retrieves: string };
export type LineageNode = { evidence_id: string; evidence_number: string; filename: string; media_type: MediaType; source_type: SourceType; received_at: string; fingerprinted: boolean; sources: { source_id: string; source_number: string; url: string; claimed_publication_time: string | null; title: string | null }[] };
export type LineageEdge = { relationship_id: string; evidence_a: string; evidence_b: string; kind: string; status: 'CANDIDATE'; similarity: number; earlier_observed: string | null; ordering_basis: string | null; basis: Record<string, unknown>; created_at: string };
export type Lineage = { case_id: string; nodes: LineageNode[]; edges: LineageEdge[]; note: string };

/* ── evidence graph, reconstruction, reviews and reports (NEX-EGC, NEX-REC, NEX-INV, NEX-RPT), plan Step 7 ── */
export type GraphNodeType = 'CASE' | 'EVIDENCE' | 'SOURCE' | 'FINDING';
export type GraphNode = { id: string; type: GraphNodeType; label: string; [k: string]: unknown };
export type GraphEdge = { from: string; to: string; type: 'CONTAINS' | 'RETRIEVED_AS' | 'CANDIDATE_VERSION' | 'ABOUT' | 'CITES'; record: string; [k: string]: unknown };
export type GraphSnapshot = { snapshot_id: string; case_id: string; execution_id: string; nodes: GraphNode[]; edges: GraphEdge[]; counts: Record<string, number>; created_at: string };
export type TimelineEntry = { time: string; kind: 'RECEIVED' | 'RETRIEVED' | 'CLAIMED_CREATION' | 'CLAIMED_PUBLICATION'; label: string; by: string; evidence_id?: string | null; source_id?: string; raw?: string };
export type Reconstruction = { result_id: string | null; produced_at: string | null; timeline: TimelineEntry[]; conflicts: { finding_id: string; title: string; description: string | null; evidence_ids: string[]; assertion: string }[] };
export type ReviewSubject = 'FINDING' | 'RELATIONSHIP' | 'CASE_CONCLUSION' | 'BACKTRACK_COMPARISON';
export type BacktrackingCandidate = { evidence_id: string; display_number: string; filename: string; media_type: 'IMAGE' | 'VIDEO' | 'AUDIO'; sha256: string; size_bytes: number; fingerprint_indexed: boolean };
export type BacktrackingComparison = { id: string; case_id: string; seed_evidence_id: string; candidate_evidence_id: string; seed_sha256: string; candidate_sha256: string; created_at: string; current: boolean; algorithm: string; status: string; submitted_coverage_percent?: number | null; candidate_coverage_percent?: number | null; checks?: Record<string, Record<string, unknown>>; frame_pairs?: Record<string, unknown>[]; limitations: string[]; review?: { decision: ReviewDecision; rationale: string; reviewer: string; review_id: string; version: number } | null };
export type BacktrackingOverview = { case_id: string; nodes: { evidence_id: string; label: string; filename: string }[]; edges: { comparison_id: string; from: string; to: string; status: string; review_decision: ReviewDecision | null; algorithm: string; coverage_seed_percent: number | null; coverage_candidate_percent: number | null }[]; coverage: { compared_pairs: number; possible_video_pairs: number; pair_percent: number | null }; comparison_records: number; shown_records: number; truncated: boolean };
export type BacktrackingOccurrence = { source_id: string; source_number: string; observation_id: string | null; revision: number; url: string; final_url: string | null; platform: string; outcome: string; detail: string | null; claimed_publication_time: string | null; observed_at: string | null; preserved_evidence_id: string | null; backtracking_access: 'LOCAL_VIDEO' | 'UNSUPPORTED_MEDIA' | 'METADATA_ONLY' };
export type ReviewDecision = 'ACCEPTED' | 'REJECTED' | 'INCONCLUSIVE' | 'NEEDS_MORE_EVIDENCE';
export type Review = { review_id: string; review_number: string; case_id: string; subject_type: ReviewSubject; subject_id: string; version: number; decision: ReviewDecision; rationale: string; reconstruction_result_id: string | null; reviewer: string; created_at: string };
export type ReviewInput = { subject_type: ReviewSubject; subject_id: string; decision: ReviewDecision; rationale: string };
export type Report = { report_id: string; report_number: string; case_id: string; version: number; kind: 'DRAFT' | 'FINAL'; state: 'QUEUED' | 'GENERATED' | 'FAILED'; job_id: string | null; json_sha256: string | null; pdf_sha256: string | null; summary: Record<string, unknown>; error: string | null; requested_by: string; created_at: string; generated_at: string | null };

/* ── preferences and configuration (Step 8) ── */
export type NotificationPrefs = { runs_completed: boolean; runs_partial: boolean; runs_failed: boolean; runs_cancelled: boolean; sources: boolean; reports: boolean };
export type PreferenceDocument = { notifications: NotificationPrefs; analysis: { auto_analyze_on_upload: boolean | null }; reports: { default_download: 'pdf' | 'json' } };
export type Preferences = { operator: string; version: number; preferences: PreferenceDocument; effective: { auto_analyze_on_upload: boolean; integrity_notifications: string }; updated_at: string | null };
export type SystemConfig = {
  environment: string; version: string; operator: string; uploads: { max_bytes: number; auto_analyze_default: boolean };
  jobs: { lease_seconds: number; max_attempts: number; job_timeout_seconds: number; module_timeout_seconds: number };
  detectors: { enabled: boolean; image: string | null; speech: string | null; timeout_seconds: number }; projections: { neo4j: boolean; qdrant: boolean }; web_visual_search?: { enabled: boolean; key_configured: boolean }; cors_origins: string[];
};
export type RecentFinding = { finding_id: string; module_id: string; finding_type: string; assertion: 'OBSERVATION' | 'INFERENCE' | 'INCONCLUSIVE'; title: string; score: number | null; score_kind: string | null; created_at: string; case_id: string; case_number: string; evidence: { evidence_id: string; evidence_number: string | null }[] };

/* ── workspace summaries (UX transformation): derived from records at request time ── */
export type Stage = 'ACQUIRE' | 'ANALYSE' | 'REVIEW' | 'REPORT' | 'DONE';
export type Progress = {
  case_id: string; case_number: string; title: string; status: CaseStatus; test_record: boolean; evidence: number; by_media: Partial<Record<MediaType, number>>;
  image_evidence_id: string | null; runs_active: number; last_run_state: string | null; inferences: number; conclusion: string | null; reports: number;
  final_report: boolean; stage: Stage; next_action: string;
};
export type AttentionItem = { kind: 'RUN_FAILED' | 'ALERT' | 'WARNING' | 'AWAITING_REVIEW'; title: string; detail: string | null; link: string | null; case_id: string | null; at: string };
