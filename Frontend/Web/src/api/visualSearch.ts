import { ApiError, requestRaw } from './http';

export type VisualSearchMode = 'local' | 'web';
export type VisualSearchStatus = {
  local: { configured: boolean; model_ready: boolean; reachable: boolean; indexed_in_postgres: number; points_in_qdrant: number | null };
  web: { configured: boolean; provider: 'serpapi_google_lens' };
  max_bytes: number;
};
export type VisualSearchMatch = {
  image_url?: string;
  page_url?: string;
  title?: string;
  match_type: string;
  score: number | null;
  score_kind: string | null;
  evidence_id?: string;
  thumbnail_token?: string;
};
export type VisualSearchResult = {
  provider: string;
  scope: 'case' | 'web';
  query_sha256: string;
  matches: VisualSearchMatch[];
  limitations: string[];
};
export type Crop = [number, number, number, number];
type SearchInput = ({ file: File; url?: never } | { url: string; file?: never }) & {
  mode: VisualSearchMode;
  top_k?: number;
  allow_external?: boolean;
  crop?: Crop;
};

async function data<T>(path: string, init: RequestInit): Promise<T> {
  const response = await requestRaw<{ success?: boolean; data: T }>(path, {
    ...init, credentials: 'omit', referrerPolicy: 'no-referrer', redirect: 'error',
  });
  if (response.success === false || !response.data) throw new ApiError(502, 'BAD_RESPONSE', 'Visual search returned an invalid response.');
  return response.data;
}

export const visualSearch = {
  status: (signal?: AbortSignal) => data<VisualSearchStatus>('/visual-search/status', { signal, cache: 'no-store' }),
  search: (caseId: string, input: SearchInput, signal?: AbortSignal) => {
    const form = new FormData();
    if (input.file) form.append('file', input.file, input.file.name);
    else form.append('url', input.url);
    form.append('mode', input.mode);
    form.append('top_k', String(input.top_k ?? 10));
    form.append('allow_external', String(input.mode === 'web' && input.allow_external === true));
    if (input.crop) form.append('crop', JSON.stringify(input.crop));
    return data<VisualSearchResult>(`/cases/${encodeURIComponent(caseId)}/visual-search`, { method: 'POST', body: form, signal });
  },
};

/** Result links must be absolute HTTP(S), with no embedded credentials. */
export function safeHttpUrl(value?: string): string | null {
  if (!value) return null;
  try {
    const u = new URL(value);
    return ['http:', 'https:'].includes(u.protocol) && !u.username && !u.password ? u.href : null;
  } catch { return null; }
}
