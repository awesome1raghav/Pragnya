/* ─────────────────────────────────────────────────────────────────────────────
   NEXTRON API CONTRACT  ·  the single source of truth between frontend, backend and ML

   Every workspace screen reads and writes ONLY through `NextronApi` below.
   The frontend ships with a mock implementation (./mock.ts) that returns demo data in exactly
   these shapes. To go live, the backend implements the HTTP routes in Documentation/Backend API Specification.md and
   the app is started with NEXT_PUBLIC_NEXTRON_API=https://your-api — no UI changes needed.

   Conventions (apply everywhere):
   - IDs are opaque strings. Times are ISO-8601 UTC strings ("2025-01-21T18:02:14Z").
   - Durations and offsets into media are SECONDS as numbers (23.7), never frame counts.
   - Confidence and likelihood are 0..1. Readiness and outcome ranges are 0..100 percent.
   - Regions are PERCENT OF THE STILL IMAGE ({ x, y, w, h } in 0..100, origin top-left), so they
     stay correct at any display size. ML: convert pixel boxes with x = px / width * 100.
   - Enum values are snake_case; the UI owns all human labels and colours.
   ───────────────────────────────────────────────────────────────────────────── */

export type Branch = 'spatial' | 'temporal' | 'audio_visual' | 'provenance';
export type CaseStatus = 'flagged' | 'in_review' | 'active' | 'on_hold' | 'verified';
export type Severity = 'high' | 'medium' | 'low' | 'info';
export type FindingStatus = 'open' | 'accepted' | 'rejected' | 'second_review';

/** Images the UI shows for one piece of media. All URLs must be directly loadable by the browser
 *  (signed URLs are fine). `still` and `overlay` must share the same pixel dimensions. */
export interface Media {
  still: string;          // representative frame, ~1280 px wide (JPEG/WebP)
  thumb: string;          // same frame, ~480 px wide
  overlay?: string;       // ML analysis layer for the still (error-level / heat map), same size as `still`
  width: number;          // pixel size of `still`
  height: number;
  focus?: { x: number; y: number }; // 0..1, where to keep in view when the UI has to crop (e.g. a face)
}

export interface Case {
  id: string;
  name: string;
  summary: string;
  status: CaseStatus;
  priority: number;                          // 0..100, higher = more urgent; the command centre focuses the highest
  reason: string;                            // one sentence: why this case needs attention now
  analyst: string;
  updatedAt: string;
  legalHold: boolean;
  cover: Media;
  readiness: Record<Branch, number | null>;  // 0..100 per branch; null = branch not applicable (e.g. no audio)
}

export interface MetadataField {
  key: string;            // "Encoder"
  value: string;          // "Lavf 60.3.100 (FFmpeg)"
  conflict?: boolean;     // true when it contradicts the capture record
  note?: string;          // why it conflicts, shown on hover
}

export interface Evidence {
  id: string;
  caseId: string;
  fileName: string;
  kind: 'video' | 'image' | 'audio';
  status: CaseStatus;
  durationSec: number;    // 0 for stills
  source: string;         // "City camera, Kerr St"
  capturedAt: string;
  sha256: string;         // of the original bytes, hex
  sizeBytes: number;
  width: number;
  height: number;
  codec: string;
  media: Media;
  metadata: MetadataField[];
}

export interface Finding {
  id: string;
  evidenceId: string;
  branch: Branch;
  severity: Severity;
  status: FindingStatus;
  title: string;          // short, plain: "Blending seam along the left jaw"
  detail: string;         // one or two sentences an investigator can read aloud
  confidence: number;     // 0..1, calibrated
  startSec: number | null;  // null = applies to the whole file or to a still
  endSec: number | null;
  region: { x: number; y: number; w: number; h: number } | null; // percent of the still, see conventions
  explanations: { label: string; likelihood: number }[];       // competing causes, most likely first
  model: { name: string; version: string };
}

export type NodeKind = 'case' | 'media' | 'finding' | 'metadata' | 'source';
export type EdgeKind = 'contains' | 'pattern' | 'timestamp' | 'metadata' | 'derived';
export interface GraphNode { id: string; kind: NodeKind; label: string; detail: string; refId?: string; cluster?: string; severity?: Severity; status?: CaseStatus; thumb?: string }
export interface GraphEdge { from: string; to: string; kind: EdgeKind; label?: string }
export interface Graph { nodes: GraphNode[]; edges: GraphEdge[] }

export interface Assessment {
  caseId: string;
  outcomes: { label: string; low: number; high: number }[]; // plausible ranges, 0..100; first = leading
  note: string;
}

export interface Decision {
  id: string;
  kind: 'accept_finding' | 'resolve_conflict' | 'approve_report';
  title: string;
  caseId: string;
  findingId?: string;
  severity: Severity;
  rationale: string;      // "Spatial 0.91 · agrees with temporal break"
}
export type DecisionAction = 'accept' | 'resolve' | 'approve' | 'escalate' | 'dismiss';

export interface ActivityItem { id: string; at: string; text: string; caseId: string; actor: string; kind: 'finding' | 'status' | 'integrity' | 'analysis' }

export interface AuditEvent { seq: number; at: string; kind: 'evidence_access' | 'analysis' | 'model_change' | 'access_control' | 'export' | 'retention'; actor: string; text: string; signature: string; verified: boolean }
export interface ModelInfo { name: string; version: string; status: 'deployed' | 'approved' | 'retired' }

/** A deepfake analysis run. Poll GET /analysis/:id until state is done or failed. */
export interface AnalysisJob {
  id: string;
  evidenceId: string;
  state: 'queued' | 'running' | 'done' | 'failed';
  progress: number;       // 0..1 overall
  stages: { key: string; label: string; state: 'waiting' | 'running' | 'done' | 'failed' }[];
  findings?: Finding[];   // present when state = done
  error?: string;         // present when state = failed
}

export interface NextronApi {
  listCases(): Promise<Case[]>;
  listEvidence(caseId?: string): Promise<Evidence[]>;
  listFindings(filter?: { caseId?: string; evidenceId?: string }): Promise<Finding[]>;
  updateFinding(id: string, status: FindingStatus): Promise<Finding>;
  getGraph(): Promise<Graph>;
  getAssessment(caseId: string): Promise<Assessment>;
  listDecisions(): Promise<Decision[]>;
  decide(id: string, action: DecisionAction): Promise<void>;
  listActivity(): Promise<ActivityItem[]>;
  listAudit(): Promise<AuditEvent[]>;
  listModels(): Promise<ModelInfo[]>;
  /** Upload an original. The browser has already hashed it; the server must recompute and reject on mismatch. */
  uploadEvidence(input: { caseId: string; file: File; sha256: string }, onProgress?: (p: number) => void): Promise<Evidence>;
  startAnalysis(evidenceId: string): Promise<AnalysisJob>;
  getAnalysis(jobId: string): Promise<AnalysisJob>;
}
