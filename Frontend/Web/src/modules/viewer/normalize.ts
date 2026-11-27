/* Universal Forensic Evidence Viewer: one finding shape for every module, built from the stored analysis
   (GET /evidence/{id}/analysis). An adapter only: nothing is inferred, scored or located here. A field the module did not
   record stays empty, and the viewer says it is unavailable. */
import type { Artifact, EvidenceAnalysis, Finding, FindingPayload } from '@/api';

export type Level = Finding['assertion'];
export type Location =
  | { kind: 'region'; x: number; y: number; w: number; h: number; frame: number | null }  // percent of the frame, as recorded
  | { kind: 'time'; start: number; end: number }                                          // seconds
  | { kind: 'none' };

export type Family = 'EXAMINATION' | 'RELATIONSHIP' | 'RECORD';
export const FAMILY_LABEL: Record<Family, string> = { EXAMINATION: 'Examination', RELATIONSHIP: 'Relationships', RECORD: 'Case record' };

export type ViewerFinding = {
  id: string; moduleId: string; moduleName: string; type: string; level: Level; family: Family;
  title: string; description: string | null; location: Location;
  method: string; score: number | null; scoreKind: string | null;
  threshold: { value: number; source: string | null; above: boolean | null } | null;
  measurement: Record<string, unknown>; limitations: string[]; artifacts: Artifact[];
  resultId: string; executionId: string | null; moduleVersion: string | null; toolVersions: Record<string, string>; createdAt: string;
};

const FAMILY: Record<string, Family> = {
  'NEX-MET': 'EXAMINATION', 'NEX-IMG': 'EXAMINATION', 'NEX-VID': 'EXAMINATION', 'NEX-AUD': 'EXAMINATION', 'NEX-PRV': 'EXAMINATION',
  'NEX-FPM': 'RELATIONSHIP', 'NEX-MOC': 'RELATIONSHIP', 'NEX-ALN': 'RELATIONSHIP', 'NEX-TRN': 'RELATIONSHIP', 'NEX-CMC': 'RELATIONSHIP',
  'NEX-EGC': 'RECORD', 'NEX-REC': 'RECORD',
};

function location(p: FindingPayload): Location {
  if (p.region) return { kind: 'region', x: p.region.x, y: p.region.y, w: p.region.w, h: p.region.h, frame: p.region.frame_seconds ?? null };
  if (p.time_range) return { kind: 'time', start: p.time_range.start_seconds, end: p.time_range.end_seconds };
  return { kind: 'none' };
}

export function normalize(a: EvidenceAnalysis): ViewerFinding[] {
  const artifacts = new Map(a.artifacts.map(x => [x.artifact_id, x]));
  const latest = new Map(a.modules.map(m => [m.module_id, m.latest]));
  return a.findings.map(f => {
    const p = f.payload as FindingPayload & { threshold?: unknown };
    const m = (p.measurement ?? {}) as Record<string, unknown>;
    const exec = latest.get(f.module_id);
    const ours = exec && exec.result_id === f.result_id ? exec : null;  // the execution that produced this result, when it is this evidence's own
    const thresholdValue = typeof m.threshold === 'number' ? m.threshold : null;
    return {
      id: f.finding_id, moduleId: f.module_id, moduleName: f.module_name, type: f.finding_type, level: f.assertion,
      family: FAMILY[f.module_id] ?? 'EXAMINATION', title: f.title, description: f.description, location: location(p),
      method: typeof m.detector === 'string' ? m.detector : `${f.module_name}${ours?.module_version ? ` (${ours.module_version})` : ''}`,
      score: f.score, scoreKind: f.score_kind,
      threshold: thresholdValue === null ? null : { value: thresholdValue, source: typeof m.threshold_source === 'string' ? m.threshold_source : null, above: typeof m.above_threshold === 'boolean' ? m.above_threshold : null },
      measurement: m, limitations: p.limitations ?? [],
      artifacts: (p.supporting_artifact_ids ?? []).map(id => artifacts.get(id)).filter((x): x is Artifact => !!x),
      resultId: f.result_id, executionId: ours?.execution_id ?? null, moduleVersion: ours?.module_version ?? null, toolVersions: ours?.tool_versions ?? {},
      createdAt: f.created_at,
    };
  });
}

export const LEVEL: Record<Level, { label: string; tone: 'steel' | 'gold' | 'mute'; meaning: string }> = {
  OBSERVATION: { label: 'Observation', tone: 'steel', meaning: 'Measured from the file. It describes the media; it does not judge it.' },
  INFERENCE: { label: 'Inference', tone: 'gold', meaning: "A method's reading of the evidence, with its own threshold and limits. Not a verdict." },
  INCONCLUSIVE: { label: 'Inconclusive', tone: 'mute', meaning: 'The method could not reach a reading on this evidence.' },
};

export const fmtTime = (t: number) => {
  const m = Math.floor(t / 60), sec = t - m * 60;
  return `${m}:${sec < 10 ? '0' : ''}${sec.toFixed(2)}`;
};

export const where = (l: Location) => l.kind === 'region' ? `x ${l.x.toFixed(0)}%, y ${l.y.toFixed(0)}%, ${l.w.toFixed(0)} × ${l.h.toFixed(0)}% of the frame${l.frame !== null ? ` at ${fmtTime(l.frame)}` : ''}`
  : l.kind === 'time' ? (l.end - l.start < 0.01 ? `at ${fmtTime(l.start)}` : `${fmtTime(l.start)} – ${fmtTime(l.end)}`) : null;

/** Flatten a measurement to readable rows; nested values stay JSON. */
export function measurementRows(m: Record<string, unknown>): [string, string][] {
  const skip = new Set(['timeline', 'summary']);
  return Object.entries(m).filter(([k]) => !skip.has(k)).map(([k, v]) => [k.replace(/_/g, ' '),
    typeof v === 'number' ? (Number.isInteger(v) ? String(v) : v.toPrecision(4)) : typeof v === 'string' ? v : typeof v === 'boolean' ? (v ? 'yes' : 'no') : v === null ? '—' : JSON.stringify(v)]);
}
