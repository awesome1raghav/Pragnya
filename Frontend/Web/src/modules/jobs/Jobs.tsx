'use client';

/* Shared views of the Job Service and T-MIR: job rows with cancel and retry, the worker notice, and the
   run plan (every planned module and scope, with its state and the reason it did or did not run).
   Everything shown comes from the Job and Run APIs; progress is the count of finished plan entries. */
import Link from 'next/link';
import { useState } from 'react';
import { ChevronDown, RotateCcw, Square, TriangleAlert } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import p from '@/styles/platform.module.css';
import { api, ApiError, type Job, type PlanEntry } from '@/api';
import { useWorkers } from '@/api/hooks';
import { invalidate, useQuery } from '@/api/query';
import { useLive } from '@/api/live';
import { Dot, ErrorState } from '@/components/ui';
import { useWorkspace } from '@/layouts/MainLayout';
import { paths } from '@/config/routes';
import { ago, execStateLabel, execStateTone, explain, jobStateLabel, jobStateTone, jobTypeLabel, ms } from '@/utils/labels';

const ACTIVE = new Set(['QUEUED', 'RUNNING']);
const RETRYABLE = new Set(['FAILED', 'PARTIALLY_COMPLETED', 'CANCELLED']);

export const jobLink = (j: Job) => (j.evidence_id ? paths.evidence(j.evidence_id, 'analysis') : paths.caseAnalysis(j.case_id));

export function JobActions({ job }: { job: Job }) {
  const { notify } = useWorkspace();
  const [busy, setBusy] = useState(false);
  const act = async (kind: 'cancel' | 'retry') => {
    setBusy(true);
    try {
      const r = kind === 'cancel' ? await api.jobs.cancel(job.job_id) : await api.jobs.retry(job.job_id);
      notify(kind === 'cancel' ? (r.state === 'CANCELLED' ? `${job.job_number} cancelled` : `${job.job_number} stops before its next module`) : `Queued ${r.job_number}; completed work is reused`);
      invalidate('jobs', `run:${job.job_id}`, ...(job.evidence_id ? [`ev:${job.evidence_id}`] : []));
    } catch (e) {
      notify(e instanceof ApiError ? e.message : 'The request failed', 'alert');
    } finally { setBusy(false); }
  };
  if (ACTIVE.has(job.state) && !job.cancel_requested) return <button className={`${s.btn} ${s.sm}`} disabled={busy} onClick={() => act('cancel')} aria-label={`Cancel ${job.job_number}`}><Square size={12} />Cancel</button>;
  if (RETRYABLE.has(job.state)) return <button className={`${s.btn} ${s.sm}`} disabled={busy} onClick={() => act('retry')} aria-label={`Retry ${job.job_number}`}><RotateCcw size={13} />Retry</button>;
  return null;
}

function progressText(j: Job) {
  const pr = j.progress;
  if (!pr) return j.state === 'QUEUED' ? (j.attempt ? `waiting to retry (attempt ${j.attempt + 1} of ${j.max_attempts})` : 'waiting for a worker') : null;
  const done = `${pr.finished} of ${pr.planned} modules finished`;
  return j.state === 'RUNNING' && pr.current ? `${done} · running ${pr.current}` : done;
}

export function JobRow({ job }: { job: Job }) {
  const subject = job.evidence_number ?? job.case_number ?? '';
  const pr = job.progress;
  return <li className={p.jobRow}>
    <div>
      <b><Link href={jobLink(job)} style={{ textDecoration: 'none' }}><span className={s.mono}>{job.job_number}</span></Link> · {jobTypeLabel[job.job_type]}{subject ? ` · ${subject}` : ''}</b>
      <small><Dot tone={jobStateTone[job.state]}>{jobStateLabel[job.state]}{job.cancel_requested && ACTIVE.has(job.state) ? ' · cancelling' : ''}</Dot>{' '}{progressText(job) ? `· ${progressText(job)}` : ''} · {ago(job.finished_at ?? job.started_at ?? job.created_at)}</small>
      {job.error && <small style={{ color: 'var(--alert)' }}>{job.error.code}: {job.error.message}</small>}
    </div>
    <div className={p.jobActs}><JobActions job={job} /></div>
    {job.state === 'RUNNING' && pr && <span className={p.jobBar} role='progressbar' aria-valuemin={0} aria-valuemax={pr.planned} aria-valuenow={pr.finished} aria-label={`${job.job_number} progress`}><i style={{ width: `${(100 * pr.finished) / Math.max(pr.planned, 1)}%` }} /></span>}
  </li>;
}

export const JobList = ({ jobs }: { jobs: Job[] }) => <ul className={p.jobList}>{jobs.map(j => <JobRow key={j.job_id} job={j} />)}</ul>;

/** Says plainly when no worker is running, since queued work then waits. */
export function WorkerNotice({ quietWhenAlive }: { quietWhenAlive?: boolean }) {
  const w = useWorkers();
  const live = useLive();
  if (w.error) return <ErrorState error={w.error} onRetry={w.reload} title='Worker status could not be read' />;
  if (!w.data) return null;
  if (w.data.alive === 0) return <p className={p.warnLine} role='status'><TriangleAlert size={15} /><span>No worker is running, so queued jobs wait. Start one from the repository root: <code className={s.mono}>.venv\Scripts\python.exe -m Backend.App.Workers.Worker</code></span></p>;
  if (quietWhenAlive) return null;
  return <p className={s.cap}>{w.data.alive} worker{w.data.alive === 1 ? '' : 's'} running · <span className={p.liveChip} data-state={live.state}><i />{live.state === 'live' ? 'live updates on' : live.state === 'connecting' ? 'connecting to live updates' : 'live updates reconnecting'}</span></p>;
}

/* ── run plan ── */
export function PlanTable({ plan, scopeLabel }: { plan: PlanEntry[]; scopeLabel?: (e: PlanEntry) => string }) {
  return <div className={p.planWrap}><table className={p.planTable}>
    <thead><tr><th>Module</th><th>Scope</th><th>State</th><th>Why / detail</th><th /></tr></thead>
    <tbody>{plan.map(e => <PlanRow key={e.key} e={e} scope={scopeLabel ? scopeLabel(e) : e.scope_kind.toLowerCase()} />)}</tbody>
  </table></div>;
}

function PlanRow({ e, scope }: { e: PlanEntry; scope: string }) {
  const [open, setOpen] = useState(false);
  const why = explain(e.reason, e.detail);
  const extra = e.limitations.filter(l => !(e.detail ?? '').includes(l));  // skips already explain themselves in the detail
  return <>
    <tr data-dim={e.state === 'SKIPPED' || e.state === 'UNAVAILABLE'}>
      <td><b className={s.mono} style={{ fontSize: 12 }}>{e.module_id}</b><small>{e.module_name}</small></td>
      <td data-nowrap>{scope}</td>
      <td><Dot tone={execStateTone[e.state]}>{execStateLabel[e.state]}</Dot>{e.interrupted_attempts.length > 0 && <small>{e.interrupted_attempts.length} interrupted attempt{e.interrupted_attempts.length > 1 ? 's' : ''} retried</small>}</td>
      <td>{why || '—'}{extra.length > 0 && <small>Limitations: {extra.join('; ')}</small>}</td>
      <td>{e.result_id && <button className={`${s.btn} ${s.sm}`} onClick={() => setOpen(v => !v)} aria-expanded={open} aria-label={`Result of ${e.module_id}`}><ChevronDown size={13} style={{ transform: open ? 'rotate(180deg)' : undefined }} />Result</button>}</td>
    </tr>
    {open && e.result_id && <tr><td colSpan={5}><ResultEnvelope id={e.result_id} /></td></tr>}
  </>;
}

function ResultEnvelope({ id }: { id: string }) {
  const q = useQuery(`result:${id}`, () => api.analysis.result(id));
  if (q.error) return <ErrorState error={q.error} onRetry={q.reload} />;
  if (!q.data) return <p className={s.cap}>Loading the result envelope…</p>;
  const env = q.data.envelope as { execution_time_ms?: number; tool_versions?: Record<string, string> };
  return <div style={{ display: 'grid', gap: 8 }}>
    <p className={s.cap}>{q.data.module_name} result · schema {q.data.schema_version} · {ms(env.execution_time_ms)}{env.tool_versions ? ` · ${Object.entries(env.tool_versions).map(([k, v]) => `${k} ${v}`).join(', ')}` : ''}</p>
    <pre className={p.json}>{JSON.stringify(q.data.envelope, null, 2)}</pre>
  </div>;
}

