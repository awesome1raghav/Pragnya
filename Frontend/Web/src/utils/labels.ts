/* Human labels and colour tones for the API's enum values, plus formatting helpers.
   The API sends codes (OPEN, EVIDENCE_COLLECTION …); only this file turns them into words. */
import type { AcquisitionMethod, CaseCategory, CasePriority, CaseStatus, ExecutionState, JobState, JobType, MediaType, MetadataStatus, ModuleStatus, SourceType } from '@/api';

export type Tone = 'gold' | 'alert' | 'steel' | 'ok' | 'mute' | 'ink';
export const toneColor: Record<Tone, string> = { gold: '#e9a23b', alert: '#f0604d', steel: '#7fa6bf', ok: '#8fbf7a', mute: '#8d877c', ink: '#bdb6aa' };

export const statusLabel: Record<CaseStatus, string> = {
  OPEN: 'Open', EVIDENCE_COLLECTION: 'Collecting evidence', INVESTIGATION_IN_PROGRESS: 'In progress', REVIEW_REQUIRED: 'Review required',
  REVIEW_COMPLETED: 'Reviewed', REPORT_AVAILABLE: 'Report available', CLOSED: 'Closed', ARCHIVED: 'Archived',
};
export const statusTone: Record<CaseStatus, Tone> = {
  OPEN: 'ink', EVIDENCE_COLLECTION: 'steel', INVESTIGATION_IN_PROGRESS: 'gold', REVIEW_REQUIRED: 'alert',
  REVIEW_COMPLETED: 'ok', REPORT_AVAILABLE: 'ok', CLOSED: 'mute', ARCHIVED: 'mute',
};
export const priorityLabel: Record<CasePriority, string> = { LOW: 'Low', MEDIUM: 'Medium', HIGH: 'High', CRITICAL: 'Critical' };
export const priorityTone: Record<CasePriority, Tone> = { LOW: 'mute', MEDIUM: 'ink', HIGH: 'gold', CRITICAL: 'alert' };
export const categoryLabel: Record<CaseCategory, string> = {
  MEDIA_MANIPULATION: 'Media manipulation', SYNTHETIC_MEDIA: 'Synthetic media (suspected deepfake)', SOURCE_VERIFICATION: 'Source verification',
  CONTEXT_VERIFICATION: 'Context verification', OTHER: 'Other',
};
export const mediaLabel: Record<MediaType, string> = { IMAGE: 'Image', VIDEO: 'Video', AUDIO: 'Audio' };
export const sourceTypeLabel: Record<SourceType, string> = { USER_UPLOAD: 'User upload', SHARED_FILE: 'Shared file', SCREENSHOT: 'Screenshot', SCREEN_RECORDING: 'Screen recording', SOURCE_RETRIEVAL: 'Source retrieval' };
export const methodLabel: Record<AcquisitionMethod, string> = { DIRECT_UPLOAD: 'Direct upload', SHARE_INTENT: 'Share from another app', SCREEN_CAPTURE: 'Screen capture', CONNECTOR_RETRIEVAL: 'Connector retrieval' };
export const metadataLabel: Record<MetadataStatus, string> = { EXTRACTED: 'Extracted', UNAVAILABLE: 'Extractor unavailable', FAILED: 'Extraction failed' };
export const moduleStatusLabel: Record<ModuleStatus, string> = { IMPLEMENTED: 'Implemented', PARTIAL: 'Partial', NOT_IMPLEMENTED: 'Not built yet' };
export const moduleStatusTone: Record<ModuleStatus, Tone> = { IMPLEMENTED: 'ok', PARTIAL: 'gold', NOT_IMPLEMENTED: 'mute' };

/* jobs and module executions */
export const jobStateLabel: Record<JobState, string> = { QUEUED: 'Queued', RUNNING: 'Running', COMPLETED: 'Completed', PARTIALLY_COMPLETED: 'Partially completed', FAILED: 'Failed', CANCELLED: 'Cancelled' };
export const jobStateTone: Record<JobState, Tone> = { QUEUED: 'steel', RUNNING: 'gold', COMPLETED: 'ok', PARTIALLY_COMPLETED: 'gold', FAILED: 'alert', CANCELLED: 'mute' };
export const execStateLabel: Record<ExecutionState, string> = {
  PENDING: 'Pending', QUEUED: 'Queued', WAITING_FOR_DEPENDENCIES: 'Waiting', RUNNING: 'Running', COMPLETED: 'Completed', PARTIALLY_COMPLETED: 'Partial',
  FAILED: 'Failed', CANCELLED: 'Cancelled', SKIPPED: 'Skipped', UNAVAILABLE: 'Unavailable',
};
export const execStateTone: Record<ExecutionState, Tone> = {
  PENDING: 'mute', QUEUED: 'steel', WAITING_FOR_DEPENDENCIES: 'steel', RUNNING: 'gold', COMPLETED: 'ok', PARTIALLY_COMPLETED: 'gold',
  FAILED: 'alert', CANCELLED: 'mute', SKIPPED: 'mute', UNAVAILABLE: 'mute',
};
const REASON: Record<string, string> = {
  NOT_APPLICABLE: 'does not apply to this media', NO_INPUT: 'nothing to work on: a required input produced no output',
  UPSTREAM_FAILED: 'a required input failed', CANCELLED: 'job cancelled before it started', JOB_TIMEOUT: 'job ran out of time before it started',
  MODULE_NOT_IMPLEMENTED: 'not built yet', TOOL_UNAVAILABLE: 'its tool is not installed', TIMEOUT: 'exceeded its time limit', ERROR: 'error',
  LEASE_EXPIRED: 'worker stopped while running; retried', REUSED: 'result reused', SUPERSEDED: 'superseded by an identical concurrent run',
};
export const reasonLabel = (r: string | null | undefined) => (r ? REASON[r] ?? r.toLowerCase().replace(/_/g, ' ') : null);
/** The reason in words plus the recorded detail, without saying the same thing twice. */
export function explain(reason: string | null | undefined, detail: string | null | undefined) {
  const label = reasonLabel(reason);
  if (!detail) return label;
  if (!label || detail.toLowerCase().includes(label.toLowerCase())) return detail;
  return `${label} · ${detail}`;
}
export const jobTypeLabel: Record<JobType, string> = { INVESTIGATION_RUN: 'Investigation run', SOURCE_RESOLUTION: 'Source retrieval', REPORT_GENERATION: 'Report', PROJECTION_REBUILD: 'Projection rebuild' };
export const ms = (v: number | null | undefined) => v == null ? '—' : v < 1000 ? `${v} ms` : `${(v / 1000).toFixed(v < 10_000 ? 1 : 0)} s`;

/** Statuses that count as "active" for the Active filter (not finished, not archived). */
export const ACTIVE_STATUSES: CaseStatus[] = ['OPEN', 'EVIDENCE_COLLECTION', 'INVESTIGATION_IN_PROGRESS', 'REVIEW_REQUIRED'];
export const COMPLETED_STATUSES: CaseStatus[] = ['REVIEW_COMPLETED', 'REPORT_AVAILABLE', 'CLOSED'];

/* events: what each recorded event type means, in words, and how it is coloured */
const EVENT: Record<string, [string, Tone]> = {
  'case.created': ['Investigation created', 'ink'],
  'case.updated': ['Investigation details updated', 'mute'],
  'case.archived': ['Investigation archived', 'mute'],
  'case.reopened': ['Investigation reopened', 'steel'],
  'case.status_changed': ['Status changed', 'steel'],
  'evidence.received': ['Evidence received', 'steel'],
  'evidence.hashed': ['SHA-256 computed on the server', 'steel'],
  'evidence.preserved': ['Original preserved, read-only', 'ok'],
  'evidence.metadata_extracted': ['Metadata extracted', 'mute'],
  'evidence.metadata_unavailable': ['Metadata extractor unavailable', 'gold'],
  'evidence.metadata_failed': ['Metadata extraction failed', 'alert'],
  'evidence.integrity_verified': ['Integrity verified: bytes match', 'ok'],
  'evidence.integrity_mismatch': ['Integrity check FAILED: bytes differ', 'alert'],
  'evidence.integrity_missing': ['Integrity check: original missing', 'alert'],
  'evidence.downloaded': ['Original downloaded', 'mute'],
};
export const eventLabel = (type: string) => EVENT[type]?.[0] ?? type;
export const eventTone = (type: string): Tone => EVENT[type]?.[1] ?? 'mute';

/** A one-line detail for an event, drawn only from its recorded payload. */
export function eventDetail(type: string, p: Record<string, unknown>): string | null {
  const s = (v: unknown) => (typeof v === 'string' ? v : null);
  switch (type) {
    case 'case.created': return [s(p.title), s(p.priority) && `priority ${String(p.priority).toLowerCase()}`].filter(Boolean).join(' · ');
    case 'case.updated': return p.changes && typeof p.changes === 'object' ? `Changed: ${Object.keys(p.changes as object).join(', ')}` : null;
    case 'case.archived': return s(p.reason) ? `Reason: ${p.reason}` : null;
    case 'case.reopened': return s(p.to_status) ? `Back to ${statusLabel[p.to_status as CaseStatus] ?? p.to_status}` : null;
    case 'case.status_changed': return s(p.to_status) ? `${statusLabel[p.to_status as CaseStatus] ?? p.to_status}${s(p.reason) ? ` · ${p.reason}` : ''}` : null;
    case 'evidence.received': return s(p.filename);
    case 'evidence.hashed': return s(p.sha256) ? `${String(p.sha256).slice(0, 16)}… · ${bytes(Number(p.size_bytes))}` : null;
    case 'evidence.preserved': return [s(p.media_type), s(p.mime_type)].filter(Boolean).join(' · ') || null;
    case 'evidence.metadata_extracted': case 'evidence.metadata_failed': case 'evidence.metadata_unavailable': return s(p.error) ?? s(p.extractor_version);
    case 'evidence.integrity_verified': case 'evidence.integrity_mismatch': case 'evidence.integrity_missing': return s(p.computed_sha256) ? `computed ${String(p.computed_sha256).slice(0, 16)}…` : null;
    default: return null;
  }
}

/* ── formatting ── */
export function bytes(n: number | null | undefined) {
  if (n == null || Number.isNaN(n)) return '—';
  if (n < 1024) return `${n} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let v = n / 1024, i = 0;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(v >= 100 ? 0 : v >= 10 ? 1 : 2)} ${units[i]}`;
}
export const utc = (iso: string | null | undefined) => iso ? `${iso.slice(0, 10)} ${iso.slice(11, 19)} UTC` : '—';
export function ago(iso: string | null | undefined, now = Date.now()) {
  if (!iso) return '—';
  const s = Math.round((now - new Date(iso).getTime()) / 1000);
  if (s < 45) return 'just now';
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86_400) return `${Math.round(s / 3600)} h ago`;
  if (s < 7 * 86_400) return `${Math.round(s / 86_400)} d ago`;
  return iso.slice(0, 10);
}
export function duration(sec: number | null | undefined) {
  if (sec == null || !Number.isFinite(sec)) return '—';
  const m = Math.floor(sec / 60), s = sec - m * 60;
  return `${String(m).padStart(2, '0')}:${s.toFixed(2).padStart(5, '0')}`;
}
