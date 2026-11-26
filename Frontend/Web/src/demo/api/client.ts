/* HTTP adapter: maps the contract onto the REST routes documented in Documentation/Backend API Specification.md.
   Backend: implement those routes and start the frontend with NEXT_PUBLIC_NEXTRON_API set. */
import type { NextronApi } from './contract';
import { endpoints as ep } from './endpoints';

export class ApiError extends Error { constructor(public status: number, message: string) { super(message); } }

export function httpApi(base: string, getToken?: () => string | null): NextronApi {
  const root = base.replace(/\/$/, '');
  async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
    const token = getToken?.();
    const res = await fetch(`${root}${path}`, {
      ...init,
      headers: { Accept: 'application/json', ...(init.body && !(init.body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init.headers },
    });
    if (!res.ok) throw new ApiError(res.status, (await res.text().catch(() => '')) || res.statusText);
    return res.status === 204 ? (undefined as T) : res.json();
  }
  const q = (o: Record<string, string | undefined>) => { const s = new URLSearchParams(Object.entries(o).filter(([, v]) => v) as [string, string][]).toString(); return s ? `?${s}` : ''; };

  return {
    listCases: () => call(ep.cases()),
    listEvidence: caseId => call(`${ep.evidence()}${q({ caseId })}`),
    listFindings: f => call(`${ep.findings()}${q({ caseId: f?.caseId, evidenceId: f?.evidenceId })}`),
    updateFinding: (id, status) => call(ep.finding(id), { method: 'PATCH', body: JSON.stringify({ status }) }),
    getGraph: () => call(ep.graph()),
    getAssessment: caseId => call(ep.assessment(caseId)),
    listDecisions: () => call(ep.decisions()),
    decide: (id, action) => call(ep.decision(id), { method: 'POST', body: JSON.stringify({ action }) }),
    listActivity: () => call(ep.activity()),
    listAudit: () => call(ep.audit()),
    listModels: () => call(ep.models()),
    // multipart upload with progress (fetch has no upload progress, so XHR)
    uploadEvidence: ({ caseId, file, sha256 }, onProgress) => new Promise((resolve, reject) => {
      const fd = new FormData(); fd.append('caseId', caseId); fd.append('sha256', sha256); fd.append('file', file);
      const x = new XMLHttpRequest(); x.open('POST', `${root}${ep.evidence()}`);
      const token = getToken?.(); if (token) x.setRequestHeader('Authorization', `Bearer ${token}`);
      x.upload.onprogress = e => e.lengthComputable && onProgress?.(e.loaded / e.total);
      x.onload = () => x.status < 300 ? resolve(JSON.parse(x.responseText)) : reject(new ApiError(x.status, x.responseText));
      x.onerror = () => reject(new ApiError(0, 'Network error'));
      x.send(fd);
    }),
    startAnalysis: evidenceId => call(ep.analysis(), { method: 'POST', body: JSON.stringify({ evidenceId }) }),
    getAnalysis: jobId => call(ep.analysisJob(jobId)),
  };
}
