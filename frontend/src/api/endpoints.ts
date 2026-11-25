/* The backend's REST routes, relative to NEXT_PUBLIC_NEXTRON_API (docs/BACKEND_API.md describes each one).
   The HTTP client builds every request from this table. */
const e = encodeURIComponent;

export const endpoints = {
  cases: () => '/cases',
  assessment: (caseId: string) => `/cases/${e(caseId)}/assessment`,
  evidence: () => '/evidence',
  findings: () => '/findings',
  finding: (id: string) => `/findings/${e(id)}`,
  graph: () => '/graph',
  decisions: () => '/decisions',
  decision: (id: string) => `/decisions/${e(id)}`,
  activity: () => '/activity',
  audit: () => '/audit',
  models: () => '/models',
  analysis: () => '/analysis',
  analysisJob: (id: string) => `/analysis/${e(id)}`,
};
