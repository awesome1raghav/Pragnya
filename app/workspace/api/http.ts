/* HTTP adapter: maps the contract onto the REST routes documented in docs/BACKEND_API.md.
   Backend: implement those routes and start the frontend with NEXT_PUBLIC_NEXTRON_API set. */
import type { NextronApi } from './contract';

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
    listCases: () => call('/cases'),
    listEvidence: caseId => call(`/evidence${q({ caseId })}`),
    listFindings: f => call(`/findings${q({ caseId: f?.caseId, evidenceId: f?.evidenceId })}`),
    updateFinding: (id, status) => call(`/findings/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify({ status }) }),
    getGraph: () => call('/graph'),
    getAssessment: caseId => call(`/cases/${encodeURIComponent(caseId)}/assessment`),
    listDecisions: () => call('/decisions'),
    decide: (id, action) => call(`/decisions/${encodeURIComponent(id)}`, { method: 'POST', body: JSON.stringify({ action }) }),
    listActivity: () => call('/activity'),
    listAudit: () => call('/audit'),
    listModels: () => call('/models'),
    // multipart upload with progress (fetch has no upload progress, so XHR)
    uploadEvidence: ({ caseId, file, sha256 }, onProgress) => new Promise((resolve, reject) => {
      const fd = new FormData(); fd.append('caseId', caseId); fd.append('sha256', sha256); fd.append('file', file);
      const x = new XMLHttpRequest(); x.open('POST', `${root}/evidence`);
      const token = getToken?.(); if (token) x.setRequestHeader('Authorization', `Bearer ${token}`);
      x.upload.onprogress = e => e.lengthComputable && onProgress?.(e.loaded / e.total);
      x.onload = () => x.status < 300 ? resolve(JSON.parse(x.responseText)) : reject(new ApiError(x.status, x.responseText));
      x.onerror = () => reject(new ApiError(0, 'Network error'));
      x.send(fd);
    }),
    startAnalysis: evidenceId => call('/analysis', { method: 'POST', body: JSON.stringify({ evidenceId }) }),
    getAnalysis: jobId => call(`/analysis/${encodeURIComponent(jobId)}`),
  };
}
