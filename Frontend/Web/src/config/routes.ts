/* Every page address in one place. Screens build links with these helpers, never with string literals.
   Global pages accept an investigation context as ?case=<case_id> (plan decision D-19). */
const e = encodeURIComponent;
const withCase = (base: string, caseId?: string | null) => (caseId ? `${base}?case=${e(caseId)}` : base);

export type CaseFilter = 'all' | 'active' | 'completed' | 'archived';
export const ANALYSIS_BRANCHES = ['image', 'video', 'audio', 'provenance'] as const;
export type AnalysisBranch = (typeof ANALYSIS_BRANCHES)[number];
export const ANALYSIS_MODULE: Record<AnalysisBranch, string> = { image: 'NEX-IMG', video: 'NEX-VID', audio: 'NEX-AUD', provenance: 'NEX-PRV' };
export const ANALYSIS_LABEL: Record<AnalysisBranch, string> = { image: 'Image', video: 'Video', audio: 'Audio', provenance: 'Provenance' };

export const EVIDENCE_TOOLS = ['overview', 'preview', 'metadata', 'integrity', 'timeline', 'analysis'] as const;
export type EvidenceTool = (typeof EVIDENCE_TOOLS)[number];

export const paths = {
  about: () => '/about',
  dashboard: () => '/dashboard',
  investigations: (filter?: Exclude<CaseFilter, 'all'>) => (filter ? `/investigations/${filter}` : '/investigations'),
  newInvestigation: () => '/investigations/new',
  case: (id: string) => `/investigations/${e(id)}`,
  caseEvidence: (id: string) => `/investigations/${e(id)}/evidence`,
  caseAddEvidence: (id: string) => `/investigations/${e(id)}/evidence/add`,
  caseAnalysis: (id: string, branch?: AnalysisBranch) => `/investigations/${e(id)}/analysis${branch ? `/${branch}` : ''}`,
  caseTimeline: (id: string) => `/investigations/${e(id)}/timeline`,
  caseGraph: (id: string) => `/investigations/${e(id)}/graph`,
  caseReview: (id: string) => `/investigations/${e(id)}/review`,
  caseReport: (id: string) => `/investigations/${e(id)}/report`,
  caseEvents: (id: string) => `/investigations/${e(id)}/events`,
  evidenceList: (caseId?: string | null) => withCase('/evidence', caseId),
  evidence: (id: string, tool: EvidenceTool = 'overview') => `/evidence/${e(id)}${tool === 'overview' ? '' : `/${tool}`}`,
  sources: (caseId?: string | null) => withCase('/sources', caseId),
  lineage: (caseId?: string | null) => withCase('/lineage', caseId),
  intelligence: (caseId?: string | null) => withCase('/intelligence', caseId),
  graph: (caseId?: string | null) => withCase('/graph', caseId),
  reports: (caseId?: string | null) => withCase('/reports', caseId),
  report: (id: string) => `/reports/${e(id)}`,
  notifications: () => '/notifications',
  system: () => '/system',
  systemHealth: () => '/system/health',
  systemLogs: () => '/system/logs',
  settings: () => '/settings',
};
