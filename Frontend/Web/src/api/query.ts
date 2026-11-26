'use client';

/* A small server-state cache: one entry per key, shared by every component that asks for it.
   - Data stays on screen while a refresh runs; a failed refresh marks it stale rather than blanking it.
   - After a write, call invalidate('cases') (a key prefix) so every view of that data refetches.
   - The REST API is the authority; nothing here invents or keeps data the server did not return. */
import { useCallback, useEffect, useSyncExternalStore } from 'react';
import { ApiError } from './http';

type Status = 'loading' | 'ready' | 'error';
type Entry = { status: Status; data?: unknown; error?: ApiError; updatedAt?: number; inflight?: Promise<void>; fetcher?: () => Promise<unknown> };
const cache = new Map<string, Entry>();
const listeners = new Map<string, Set<() => void>>();
const EMPTY: Entry = { status: 'loading' };

const emit = (key: string) => listeners.get(key)?.forEach(l => l());
const asApiError = (e: unknown) => e instanceof ApiError ? e : new ApiError(0, 'CLIENT_ERROR', e instanceof Error ? e.message : String(e));

function load(key: string, fetcher: () => Promise<unknown>) {
  const prev = cache.get(key);
  if (prev?.inflight) return prev.inflight;
  const inflight = fetcher().then(
    data => { cache.set(key, { status: 'ready', data, updatedAt: Date.now(), fetcher }); },
    err => { const p = cache.get(key); cache.set(key, { ...p, status: p?.data !== undefined ? 'ready' : 'error', error: asApiError(err), fetcher, inflight: undefined }); },
  ).finally(() => { const p = cache.get(key); if (p) p.inflight = undefined; emit(key); });
  cache.set(key, { ...(prev ?? EMPTY), fetcher, inflight });
  emit(key);
  return inflight;
}

export type QueryResult<T> = {
  data: T | undefined;
  error: ApiError | undefined;
  status: Status;
  /** data is shown but the latest refresh failed */
  stale: boolean;
  refreshing: boolean;
  reload: () => Promise<void>;
};

export function useQuery<T>(key: string | null, fetcher: () => Promise<T>, opts: { refreshMs?: number } = {}): QueryResult<T> {
  const subscribe = useCallback((cb: () => void) => {
    if (!key) return () => {};
    let set = listeners.get(key); if (!set) listeners.set(key, set = new Set());
    set.add(cb); return () => { set!.delete(cb); };
  }, [key]);
  const entry = useSyncExternalStore(subscribe, () => (key ? cache.get(key) : undefined) ?? EMPTY, () => EMPTY);

  useEffect(() => {
    if (!key) return;
    const cur = cache.get(key);
    if (!cur || (cur.status !== 'ready' && !cur.inflight) || cur.fetcher === undefined) load(key, fetcher);
    else if (cur.updatedAt && Date.now() - cur.updatedAt > 5_000) load(key, fetcher); // revalidate on remount
    if (!opts.refreshMs) return;
    const t = setInterval(() => load(key, fetcher), opts.refreshMs);
    return () => clearInterval(t);
  }, [key, opts.refreshMs]); // eslint-disable-line react-hooks/exhaustive-deps

  const reload = useCallback(() => key ? load(key, fetcher) : Promise.resolve(), [key]); // eslint-disable-line react-hooks/exhaustive-deps
  return {
    data: entry.data as T | undefined,
    error: entry.error,
    status: key ? entry.status : 'loading',
    stale: entry.status === 'ready' && !!entry.error,
    refreshing: !!entry.inflight,
    reload,
  };
}

/** Refetch every cached key that starts with `prefix` (those with a mounted view refetch now). */
export function invalidate(...prefixes: string[]) {
  for (const [key, entry] of cache) {
    if (!prefixes.some(p => key === p || key.startsWith(`${p}:`))) continue;
    if (listeners.get(key)?.size && entry.fetcher) load(key, entry.fetcher);
    else cache.delete(key);
  }
}

/** Refetch everything: after the live stream could not account for what changed (e.g. the event history restarted). */
export function invalidateAll() {
  for (const [key, entry] of cache) {
    if (listeners.get(key)?.size && entry.fetcher) load(key, entry.fetcher);
    else cache.delete(key);
  }
}

/** Put a known-fresh value in the cache (e.g. the record a successful write returned). */
export function prime<T>(key: string, data: T) {
  const prev = cache.get(key);
  cache.set(key, { status: 'ready', data, updatedAt: Date.now(), fetcher: prev?.fetcher });
  emit(key);
}
