/* Every page address in one place. Screens build links with these helpers, never with string literals,
   so the sitemap can change here without hunting through components. Anything not listed here is a 404. */
import type { Tool } from '@/demo/utils/labels';

const e = encodeURIComponent;

export const paths = {
  home: () => '/',
  dashboard: () => '/dashboard',
  investigations: (filter?: 'active' | 'completed' | 'archived') => filter ? `/investigations/${filter}` : '/investigations',
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
  evidenceList: () => '/evidence',
  // the evidence workbench: one address per tool
  evidence: (id: string, tool: Tool = 'viewer') => `/evidence/${e(id)}${TOOL_SEGMENT[tool]}`,
  evidenceIntegrity: (id: string) => `/evidence/${e(id)}/integrity`,
  graph: () => '/graph',
  reports: () => '/reports',
  report: (id: string) => `/reports/${e(id)}`,
  reportPreview: (id: string) => `/reports/${e(id)}/preview`,
  notifications: () => '/notifications',
  system: () => '/system',
  systemHealth: () => '/system/health',
  systemLogs: () => '/system/logs',
  settings: () => '/settings',
};

export const TOOL_SEGMENT: Record<Tool, string> = { viewer: '', frames: '/analysis', timeline: '/timeline', metadata: '/metadata' };
export const toolFromSegment = (seg: string | undefined): Tool => seg === 'analysis' ? 'frames' : seg === 'timeline' ? 'timeline' : seg === 'metadata' ? 'metadata' : 'viewer';

/* the analysis pages are named by media type, which maps onto the contract's evidence branches */
export const ANALYSIS = { image: 'spatial', video: 'temporal', audio: 'audio_visual', provenance: 'provenance' } as const;
export type AnalysisBranch = keyof typeof ANALYSIS;
export const ANALYSIS_LABEL: Record<AnalysisBranch, string> = { image: 'Image', video: 'Video', audio: 'Audio', provenance: 'Provenance' };
