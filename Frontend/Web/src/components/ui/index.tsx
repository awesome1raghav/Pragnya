'use client';

/* Shared UI primitives. Every data view uses the same states: loading, error (with the API's own
   code and request ID), empty, and "not available yet" for capabilities the backend does not have. */
import Link from 'next/link';
import { useState, type ReactNode } from 'react';
import { Check, Clock3, Copy, RotateCcw, ServerOff, TriangleAlert } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import p from '@/styles/platform.module.css';
import { API_BASE, type ApiError } from '@/api';
import type { QueryResult } from '@/api/query';
import { paths } from '@/config/routes';
import type { Tone } from '@/utils/labels';

export const Dot = ({ tone = 'mute', children }: { tone?: Tone; children: ReactNode }) => <span className={s.dot} data-tone={tone}>{children}</span>;

export const PageHead = ({ title, desc, children, eyebrow }: { title: ReactNode; desc?: ReactNode; children?: ReactNode; eyebrow?: ReactNode }) =>
  <header className={s.pageHead}><div>{eyebrow && <p className={p.eyebrow}>{eyebrow}</p>}<h1>{title}</h1>{desc && <p>{desc}</p>}</div>{children && <div className={s.actions}>{children}</div>}</header>;

export const Skeleton = ({ h = 16, w = '100%', r = 8, style }: { h?: number; w?: number | string; r?: number; style?: React.CSSProperties }) =>
  <i className={s.skel} style={{ height: h, width: w, borderRadius: r, ...style }} aria-hidden='true' />;

export const LoadingBlock = ({ rows = 4, label = 'Loading' }: { rows?: number; label?: string }) =>
  <div className={p.loading} aria-busy='true' aria-label={label}>{Array.from({ length: rows }, (_, i) => <Skeleton key={i} h={44} r={12} />)}</div>;

export function ErrorState({ error, onRetry, title }: { error: ApiError; onRetry?: () => void; title?: string }) {
  const down = error.unreachable;
  return <div className={p.errorBox} role='alert'>
    {down ? <ServerOff size={20} /> : <TriangleAlert size={20} />}
    <div>
      <b>{title ?? (down ? 'The NEXTRON API is unreachable' : 'This could not be loaded')}</b>
      <p>{down ? <>No response from <span className={s.mono}>{API_BASE}</span>. Nothing on this page is shown from cache or demo data.</> : error.message}</p>
      <small className={s.mono}>{error.code}{error.status ? ` · HTTP ${error.status}` : ''}{error.requestId ? ` · request ${error.requestId}` : ''}</small>
    </div>
    {onRetry && <button className={`${s.btn} ${s.sm}`} onClick={onRetry}><RotateCcw size={14} />Retry</button>}
  </div>;
}

export const Empty = ({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) =>
  <div className={s.empty}><b>{title}</b>{children && <span>{children}</span>}{action}</div>;

export const NotFoundState = ({ what, back }: { what: string; back: { href: string; label: string } }) =>
  <div className={s.state}><b style={{ color: 'var(--ink)', fontSize: 18 }}>No {what} at this address</b><span>It does not exist, or the ID in the address is malformed.</span><Link className={s.btn} href={back.href}>{back.label}</Link></div>;

/** Data view: renders loading / error / not-found states around `children(data)`. */
export function Load<T>({ q, children, rows, notFound }: { q: QueryResult<T>; children: (data: T) => ReactNode; rows?: number; notFound?: ReactNode }) {
  if (q.data !== undefined) return <>{q.stale && q.error && <StaleNote error={q.error} onRetry={q.reload} />}{children(q.data)}</>;
  if (q.status === 'error' && q.error) return q.error.notFound && notFound ? <>{notFound}</> : <ErrorState error={q.error} onRetry={q.reload} />;
  return <LoadingBlock rows={rows} />;
}

export const StaleNote = ({ error, onRetry }: { error: ApiError; onRetry: () => void }) =>
  <p className={p.stale} role='status'><Clock3 size={14} />Showing the last data received; refreshing failed ({error.unreachable ? 'API unreachable' : error.code}).<button onClick={onRetry}>Retry</button></p>;

/** A capability whose backend does not exist yet: says so, names the module(s) and the plan step. */
export function Unavailable({ title, modules, step, children }: { title: string; modules: string[]; step: string; children?: ReactNode }) {
  return <section className={p.notice} aria-label={`${title}: not available yet`}>
    <p className={p.noticeTag}>Not available yet · {step}</p>
    <h2>{title}</h2>
    {children && <div className={p.noticeBody}>{children}</div>}
    <p className={p.noticeModules}>{modules.map(m => <span key={m} className={s.mono}>{m}</span>)}<Link href={paths.intelligence()} className={p.noticeLink}>Module status</Link></p>
  </section>;
}

export function Hash({ value, label = 'SHA-256' }: { value: string; label?: string }) {
  const [done, setDone] = useState(false);
  const copy = async () => { try { await navigator.clipboard.writeText(value); setDone(true); setTimeout(() => setDone(false), 1400); } catch { /* clipboard blocked */ } };
  return <div className={p.hashRow}><code className={s.hash} aria-label={label}>{value}</code><button className={s.iconBtn} onClick={copy} aria-label={`Copy ${label}`} title={`Copy ${label}`}>{done ? <Check size={15} /> : <Copy size={15} />}</button></div>;
}

export function Pager({ page, pages, total, onPage }: { page: number; pages: number; total: number; onPage: (page: number) => void }) {
  if (pages <= 1) return <p className={p.pager}>{total} in total</p>;
  return <nav className={p.pager} aria-label='Pages'>
    <span>Page {page} of {pages} · {total} in total</span>
    <div><button className={`${s.btn} ${s.sm}`} disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</button><button className={`${s.btn} ${s.sm}`} disabled={page >= pages} onClick={() => onPage(page + 1)}>Next</button></div>
  </nav>;
}

export const SecHead =({ title, count, children }: { title: ReactNode; count?: number; children?: ReactNode }) =>
  <header className={s.secHead}><h2 className={s.title}>{title}{count !== undefined && <span className={s.muted}> {count}</span>}</h2>{children}</header>;
