/* Every backend call the frontend makes, by API domain (Flowchart B). Screens use these through
   `useQuery` (reads) or call them directly for writes, then invalidate the affected keys. */
import { query, request, requestRaw, upload, url } from './http';
import type {
  AcquisitionMethod, Case, CaseEvidenceStatistics, CaseInput, CasePatch, CaseQuery, CaseStatistics, CaseSummary, DatabaseStatus, EventPage,
  EvidenceListItem, EvidenceQuery, EvidenceStatistics, Evidence, IntegrityState, IntegrityVerification, Liveness, Metadata, ModuleCatalogue,
  Paginated, Readiness, SearchResults, SourceType, StorageStatus, UploadedEvidence,
  AnalysisResult, Connector, EvidenceAnalysis, Job, JobQuery, Lineage, ModuleResults, Notification, NotificationSummary, Run, Source, SourceObservation, WorkersStatus,
  GraphSnapshot, Reconstruction, Report, Review, ReviewInput, Preferences, SystemConfig, RecentFinding, Progress, AttentionItem,
  BacktrackingCandidate, BacktrackingComparison, BacktrackingOverview, BacktrackingOccurrence,
} from './types';

const e = encodeURIComponent;
const json = (body: unknown) => ({ body: JSON.stringify(body) });

export const api = {
  cases: {
    list: (q: CaseQuery = {}) => requestRaw<Paginated<Case>>(`/cases${query({ ...q })}`),
    statistics: () => request<CaseStatistics>('/cases/statistics'),
    get: (id: string) => request<Case>(`/cases/${e(id)}`),
    create: (input: CaseInput) => request<Case>('/cases', { method: 'POST', ...json(input) }),
    update: (id: string, patch: CasePatch) => request<Case>(`/cases/${e(id)}`, { method: 'PATCH', ...json(patch) }),
    archive: (id: string, reason?: string) => request<Case>(`/cases/${e(id)}/archive`, { method: 'POST', ...json({ reason: reason || null }) }),
    reopen: (id: string) => request<Case>(`/cases/${e(id)}/reopen`, { method: 'POST' }),
    summary: (id: string) => request<CaseSummary>(`/cases/${e(id)}/summary`),
    statisticsFor: (id: string) => request<CaseEvidenceStatistics>(`/cases/${e(id)}/statistics`),
    events: (id: string, after = 0, limit = 50) => requestRaw<EventPage>(`/cases/${e(id)}/events${query({ after, limit })}`),
  },
  evidence: {
    list: (q: EvidenceQuery = {}) => requestRaw<Paginated<EvidenceListItem>>(`/evidence${query({ ...q })}`),
    listForCase: (caseId: string, page = 1, pageSize = 50) => requestRaw<Paginated<Evidence>>(`/cases/${e(caseId)}/evidence${query({ page, page_size: pageSize })}`),
    statistics: () => request<EvidenceStatistics>('/evidence/statistics'),
    get: (id: string) => request<Evidence>(`/evidence/${e(id)}`),
    metadata: (id: string) => request<Metadata>(`/evidence/${e(id)}/metadata`),
    integrity: (id: string) => request<IntegrityState>(`/evidence/${e(id)}/integrity`),
    verify: (id: string) => request<IntegrityVerification>(`/evidence/${e(id)}/verify-integrity`, { method: 'POST' }),
    history: (id: string, after = 0, limit = 50) => requestRaw<EventPage>(`/evidence/${e(id)}/history${query({ after, limit })}`),
    previewUrl: (id: string) => url(`/evidence/${e(id)}/preview`),
    downloadUrl: (id: string) => url(`/evidence/${e(id)}/download`),
    upload: (caseId: string, file: File, fields: { source_type: SourceType; acquisition_method: AcquisitionMethod; description?: string }, onProgress?: (p: number) => void, signal?: AbortSignal) => {
      const form = new FormData();
      form.append('source_type', fields.source_type);
      form.append('acquisition_method', fields.acquisition_method);
      if (fields.description) form.append('description', fields.description);
      form.append('file', file, file.name);
      return upload<UploadedEvidence>(`/cases/${e(caseId)}/evidence`, form, onProgress, signal);
    },
  },
  system: {
    health: () => request<Liveness>('/health'),
    ready: () => requestRaw<{ data: Readiness }>('/health/ready').then(r => r.data),
    database: () => request<DatabaseStatus>('/system/database'),
    storage: () => request<StorageStatus>('/system/storage'),
    modules: () => request<ModuleCatalogue>('/system/modules'),
    workers: () => request<WorkersStatus>('/system/workers'),
    config: () => request<SystemConfig>('/system/config'),
  },
  preferences: {
    get: () => request<Preferences>('/preferences'),
    update: (version: number, preferences: Record<string, unknown>) => request<Preferences>('/preferences', { method: 'PATCH', ...json({ version, preferences }) }),
  },
  jobs: {
    list: (q: JobQuery = {}) => requestRaw<Paginated<Job>>(`/jobs${query({ ...q })}`),
    get: (id: string) => request<Job>(`/jobs/${e(id)}`),
    cancel: (id: string) => request<Job>(`/jobs/${e(id)}/cancel`, { method: 'POST' }),
    retry: (id: string) => request<Job>(`/jobs/${e(id)}/retry`, { method: 'POST' }),
  },
  runs: {
    start: (caseId: string, evidenceId?: string) => request<Job>(`/cases/${e(caseId)}/runs`, { method: 'POST', ...json({ evidence_id: evidenceId ?? null }) }),
    list: (caseId: string, page = 1, pageSize = 20) => requestRaw<Paginated<Job>>(`/cases/${e(caseId)}/runs${query({ page, page_size: pageSize })}`),
    get: (jobId: string) => request<Run>(`/runs/${e(jobId)}`),
  },
  analysis: {
    analyze: (evidenceId: string) => request<Job>(`/evidence/${e(evidenceId)}/analyze`, { method: 'POST' }),
    forEvidence: (evidenceId: string) => request<EvidenceAnalysis>(`/evidence/${e(evidenceId)}/analysis`),
    result: (resultId: string) => request<AnalysisResult>(`/analyses/${e(resultId)}`),
    resultUrl: (resultId: string) => url(`/analyses/${e(resultId)}`),
    moduleResults: (caseId: string, moduleId: string) => request<ModuleResults>(`/cases/${e(caseId)}/modules/${e(moduleId)}/results`),
    artifactUrl: (artifactId: string) => url(`/artifacts/${e(artifactId)}`),
  },
  sources: {
    add: (caseId: string, url: string, notes?: string) => request<Source>(`/cases/${e(caseId)}/sources`, { method: 'POST', ...json({ url, notes: notes || null }) }),
    list: (caseId?: string | null) => requestRaw<Paginated<Source>>(caseId ? `/cases/${e(caseId)}/sources` : '/sources'),
    get: (id: string) => request<Source>(`/sources/${e(id)}`),
    refresh: (id: string) => request<Source>(`/sources/${e(id)}/refresh`, { method: 'POST' }),
    history: (id: string) => request<SourceObservation[]>(`/sources/${e(id)}/history`),
    connectors: () => request<Connector[]>('/sources/connectors'),
  },
  lineage: (caseId: string) => request<Lineage>(`/cases/${e(caseId)}/lineage`),
  backtracking: {
    candidates: (caseId: string) => request<{ case_id: string; candidates: BacktrackingCandidate[] }>(`/cases/${e(caseId)}/backtracking/candidates?all_media=true`),
    comparisons: (caseId: string) => request<{ case_id: string; comparisons: BacktrackingComparison[] }>(`/cases/${e(caseId)}/backtracking/comparisons`),
    comparison: (caseId: string, id: string) => request<BacktrackingComparison>(`/cases/${e(caseId)}/backtracking/comparisons/${e(id)}`),
    overview: (caseId: string) => request<BacktrackingOverview>(`/cases/${e(caseId)}/backtracking/overview`),
    sources: (caseId: string) => request<{ source_occurrences: BacktrackingOccurrence[] }>(`/cases/${e(caseId)}/backtracking/source-occurrences`),
    compare: (caseId: string, seed_evidence_id: string, candidate_evidence_id: string) => request<BacktrackingComparison>(`/cases/${e(caseId)}/backtracking/verify`, { method: 'POST', ...json({ seed_evidence_id, candidate_evidence_id }) }),
    expand: (caseId: string, seed_evidence_id: string, max_comparisons = 100) => request<{ job_id: string; state: string; reused: boolean }>(`/cases/${e(caseId)}/backtracking/expand`, { method: 'POST', ...json({ seed_evidence_id, max_comparisons }) }),
  },
  workspace: {
    progress: (caseIds: string[]) => request<Progress[]>(`/investigation-progress${query({ case_ids: caseIds })}`),
    attention: (hideTestRecords: boolean, limit = 8) => request<AttentionItem[]>(`/attention${query({ hide_test_records: hideTestRecords, limit })}`),
  },
  findings: {
    recent: (limit = 8, assertion?: 'OBSERVATION' | 'INFERENCE' | 'INCONCLUSIVE') => request<RecentFinding[]>(`/findings${query({ limit, assertion })}`),
  },
  graph: (caseId: string) => request<GraphSnapshot>(`/cases/${e(caseId)}/graph`),
  reconstruction: (caseId: string) => request<Reconstruction>(`/cases/${e(caseId)}/reconstruction`),
  reviews: {
    list: (caseId: string, current = false) => request<Review[]>(`/cases/${e(caseId)}/reviews${query({ current })}`),
    create: (caseId: string, body: ReviewInput) => request<Review>(`/cases/${e(caseId)}/reviews`, { method: 'POST', ...json(body) }),
  },
  reports: {
    list: (caseId: string) => request<Report[]>(`/cases/${e(caseId)}/reports`),
    create: (caseId: string, kind: 'DRAFT' | 'FINAL') => request<Report>(`/cases/${e(caseId)}/reports`, { method: 'POST', ...json({ kind }) }),
    get: (id: string) => request<Report>(`/reports/${e(id)}`),
    downloadUrl: (id: string, format: 'pdf' | 'json') => url(`/reports/${e(id)}/download${query({ format })}`),
  },
  notifications: {
    list: (unread = false, page = 1, pageSize = 30) => requestRaw<Paginated<Notification>>(`/notifications${query({ unread: unread || undefined, page, page_size: pageSize })}`),
    summary: () => request<NotificationSummary>('/notifications/summary'),
    read: (id: string) => request<Notification>(`/notifications/${e(id)}/read`, { method: 'PATCH' }),
    readAll: () => request<{ marked: number }>('/notifications/read-all', { method: 'POST' }),
  },
  search: (q: string, limit = 6) => request<SearchResults>(`/search${query({ q, limit })}`),
};

export * from './types';
export { ApiError } from './http';
export { API_BASE } from './config';
