'use client';

/* Live events (WebSocket /ws/events). One connection per browser tab, opened by the workspace shell.
   - It starts at "now" and remembers the last sequence it processed; after a drop it reconnects with
     ?after=<that sequence>, so the server replays what was missed before streaming live again.
   - Each event invalidates the cached reads it affects; the REST API stays the source of what is shown.
   - Connection state is exposed honestly (connecting / live / reconnecting), never assumed. */
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { API_BASE } from './config';
import { invalidate, invalidateAll } from './query';
import type { LiveEvent, LiveMessage } from './types';

export type LiveState = 'connecting' | 'live' | 'reconnecting';
type Listener = (e: LiveEvent) => void;
type Ctx = { state: LiveState; lastSequence: number | null; subscribe: (fn: Listener) => () => void };
const LiveCtx = createContext<Ctx>({ state: 'connecting', lastSequence: null, subscribe: () => () => {} });
export const useLive = () => useContext(LiveCtx);

/** Calls `fn` for each live event while the component is mounted. */
export function useLiveEvents(fn: Listener) {
  const { subscribe } = useLive();
  const ref = useRef(fn);
  ref.current = fn;
  useEffect(() => subscribe(e => ref.current(e)), [subscribe]);
}

const wsBase = () => API_BASE.replace(/^http/, 'ws');

function affectedKeys(e: LiveEvent): string[] {
  const p = e.payload as { evidence_id?: string | null };
  const keys = new Set<string>();
  const [domain] = e.event_type.split('.');
  if (domain === 'case') { keys.add('cases'); if (e.case_id) keys.add(`case:${e.case_id}`); }
  if (domain === 'evidence') {
    keys.add('evidence'); keys.add('cases');
    if (e.case_id) keys.add(`case:${e.case_id}`);
    keys.add(`ev:${e.aggregate_id}`);
  }
  if (domain === 'job' || domain === 'analysis') {
    keys.add('jobs');
    if (e.job_id) keys.add(`run:${e.job_id}`);
    if (p.evidence_id) keys.add(`ev:${p.evidence_id}`);  // analysis, metadata
    if (e.case_id) keys.add(`case:${e.case_id}`);
  }
  if (domain === 'source') { keys.add('sources'); keys.add('evidence'); if (e.case_id) keys.add(`case:${e.case_id}`); }
  if (e.module_id === 'NEX-MOC' || e.module_id === 'NEX-FPM') { if (e.case_id) keys.add(`case:${e.case_id}:lineage`); }
  if ((domain === 'review' || domain === 'report' || domain === 'graph') && e.case_id) keys.add(`case:${e.case_id}`);  // reviews, reports, graph, reconstruction
  if (e.event_type.startsWith('analysis.module.')) keys.add('findings');  // the dashboard's recent inferences
  if (['job', 'analysis', 'review', 'report', 'evidence', 'notification'].includes(domain)) { keys.add('cases:progress'); keys.add('cases:attention'); }
  if (domain === 'preferences') keys.add('preferences');  // changed in another tab or window
  if (domain === 'notification' || domain === 'report' || domain === 'source') keys.add('notifications');  // read elsewhere; new kinds
  if (e.event_type.startsWith('job.') && !e.event_type.endsWith('.started')) keys.add('notifications');
  return [...keys];
}

export function LiveEventsProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<LiveState>('connecting');
  const [lastSequence, setLast] = useState<number | null>(null);
  const listeners = useRef(new Set<Listener>());
  const [subscribe] = useState(() => (fn: Listener) => { listeners.current.add(fn); return () => { listeners.current.delete(fn); }; });

  useEffect(() => {
    let socket: WebSocket | null = null;
    let last: number | null = null;
    let attempt = 0;
    let closed = false;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let pending = new Set<string>();
    let flush: ReturnType<typeof setTimeout> | undefined;

    const schedule = (keys: string[]) => {  // coalesce bursts (a run emits an event per module)
      keys.forEach(k => pending.add(k));
      if (flush) return;
      flush = setTimeout(() => { const ks = [...pending]; pending = new Set(); flush = undefined; invalidate(...ks); }, 150);
    };

    const connect = () => {
      const url = `${wsBase()}/ws/events${last !== null ? `?after=${last}` : ''}`;
      try { socket = new WebSocket(url); } catch { reconnect(); return; }
      socket.onmessage = msg => {
        let m: LiveMessage;
        try { m = JSON.parse(msg.data as string) as LiveMessage; } catch { return; }
        if (m.type === 'replay_complete') {
          attempt = 0; setState('live');
          if (last === null) { last = m.latest; setLast(last); }
          else if (m.latest < last) { last = m.latest; setLast(last); invalidateAll(); }  // the event history restarted: refetch everything
          return;
        }
        if (m.type !== 'event') return;
        if (last === null || m.sequence > last) { last = m.sequence; setLast(last); }
        schedule(affectedKeys(m));
        listeners.current.forEach(l => l(m));
      };
      socket.onclose = () => { socket = null; if (!closed) reconnect(); };
      socket.onerror = () => { socket?.close(); };
    };
    const reconnect = () => {
      setState('reconnecting');
      const delay = Math.min(30_000, 1000 * 2 ** Math.min(attempt++, 5));
      retry = setTimeout(connect, delay);
    };
    // retry at once when the browser comes back online or the tab is shown again, instead of waiting out the backoff
    const now = () => { if (closed || socket) return; clearTimeout(retry); attempt = 0; connect(); };
    const onVisible = () => { if (document.visibilityState === 'visible') now(); };
    window.addEventListener('online', now);
    document.addEventListener('visibilitychange', onVisible);

    connect();
    return () => {
      closed = true; clearTimeout(retry); clearTimeout(flush);
      window.removeEventListener('online', now); document.removeEventListener('visibilitychange', onVisible);
      // closing a socket that is still connecting logs a browser warning (React dev mode mounts effects twice)
      if (socket?.readyState === WebSocket.CONNECTING) { const s = socket; s.onopen = () => s.close(); s.onmessage = null; s.onclose = null; }
      else socket?.close();
    };
  }, []);

  return <LiveCtx.Provider value={{ state, lastSequence, subscribe }}>{children}</LiveCtx.Provider>;
}
