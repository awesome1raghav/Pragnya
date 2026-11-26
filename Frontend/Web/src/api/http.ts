/* The single HTTP transport. Every request goes through `request`, which unwraps the API's
   { success, data, meta } envelope and turns every failure into an ApiError the UI can show honestly. */
import { API_BASE } from './config';
import type { ErrorBody } from './types';

export class ApiError extends Error {
  constructor(
    public status: number,          // HTTP status; 0 when the API could not be reached at all
    public code: string,            // API error code (CASE_NOT_FOUND …) or NETWORK_UNREACHABLE / BAD_RESPONSE
    message: string,
    public details: unknown = null,
    public requestId: string | null = null,
  ) { super(message); }
  get unreachable() { return this.status === 0; }
  get notFound() { return this.status === 404 || (this.status === 422 && this.code === 'VALIDATION_ERROR' && isPathError(this.details)); }
}

/* a malformed ID in the path (FastAPI answers 422) means "nothing at this address" to a person */
const isPathError = (d: unknown) => Array.isArray(d) && d.some(x => Array.isArray((x as { location?: unknown[] }).location) && (x as { location: unknown[] }).location[0] === 'path');

export const url = (path: string) => `${API_BASE}${path}`;

export function query(params: Record<string, string | number | boolean | string[] | undefined | null>) {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '') continue;
    if (Array.isArray(v)) v.forEach(x => q.append(k, x)); else q.set(k, String(v));
  }
  const s = q.toString();
  return s ? `?${s}` : '';
}

async function toError(res: Response): Promise<ApiError> {
  const requestId = res.headers.get('X-Request-ID');
  try {
    const body = await res.json() as { error?: ErrorBody };
    if (body?.error) return new ApiError(res.status, body.error.code, body.error.message, body.error.details, requestId);
  } catch { /* not JSON */ }
  return new ApiError(res.status, 'BAD_RESPONSE', `The API answered ${res.status} ${res.statusText}`.trim(), null, requestId);
}

/** Fetch and return the whole JSON body (envelope included). */
export async function requestRaw<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url(path), {
      ...init,
      headers: { Accept: 'application/json', ...(init.body && typeof init.body === 'string' ? { 'Content-Type': 'application/json' } : {}), ...init.headers },
    });
  } catch {
    throw new ApiError(0, 'NETWORK_UNREACHABLE', `The NEXTRON API at ${API_BASE} could not be reached.`);
  }
  if (!res.ok) throw await toError(res);
  return res.json() as Promise<T>;
}

/** Fetch and return only `data` from the success envelope. */
export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  return (await requestRaw<{ data: T }>(path, init)).data;
}

/** Multipart upload with real byte progress (fetch cannot report upload progress, XHR can). */
export function upload<T>(path: string, form: FormData, onProgress?: (fraction: number) => void, signal?: AbortSignal): Promise<T> {
  return new Promise((resolve, reject) => {
    const x = new XMLHttpRequest();
    x.open('POST', url(path));
    x.setRequestHeader('Accept', 'application/json');
    x.upload.onprogress = e => { if (e.lengthComputable) onProgress?.(e.loaded / e.total); };
    x.onload = () => {
      let body: { data?: T; error?: ErrorBody } | null = null;
      try { body = JSON.parse(x.responseText); } catch { /* not JSON */ }
      const rid = x.getResponseHeader('X-Request-ID');
      if (x.status >= 200 && x.status < 300 && body?.data) resolve(body.data);
      else if (body?.error) reject(new ApiError(x.status, body.error.code, body.error.message, body.error.details, rid));
      else reject(new ApiError(x.status, 'BAD_RESPONSE', `The API answered ${x.status}`, null, rid));
    };
    x.onerror = () => reject(new ApiError(0, 'NETWORK_UNREACHABLE', `The NEXTRON API at ${API_BASE} could not be reached.`));
    x.onabort = () => reject(new ApiError(0, 'ABORTED', 'The upload was cancelled.'));
    signal?.addEventListener('abort', () => x.abort());
    x.send(form);
  });
}
