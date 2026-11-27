'use client';

/* The frame around every /investigations/:caseId page: identity and status on one quiet line, lifecycle actions, and
   the workspace's sections as a tab bar of its own that scrolls rather than overflowing. The case loads once here;
   every tab reads the same cached record. */
import Link from 'next/link';
import { useParams, usePathname, useRouter } from 'next/navigation';
import { useState, type ReactNode } from 'react';
import { Archive, LoaderCircle, RotateCcw } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import p from '@/styles/platform.module.css';
import cs from './case.module.css';
import { ApiError, api } from '@/api';
import { useCase } from '@/api/hooks';
import { invalidate, prime } from '@/api/query';
import { Dot, ErrorState, NotFoundState, Skeleton } from '@/components/ui';
import { useWorkspace } from '@/layouts/MainLayout';
import { paths } from '@/config/routes';
import { categoryLabel, priorityLabel, priorityTone, statusLabel, statusTone } from '@/utils/labels';

export const useCaseId = () => decodeURIComponent(useParams<{ caseId: string }>().caseId);

export default function CaseShell({ children }: { children: ReactNode }) {
  const caseId = useCaseId();
  const pathname = usePathname();
  const router = useRouter();
  const { notify } = useWorkspace();
  const q = useCase(caseId);
  const [confirm, setConfirm] = useState(false);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<ApiError | null>(null);

  if (q.status === 'error' && !q.data) return q.error?.notFound
    ? <NotFoundState what='investigation' back={{ href: paths.investigations(), label: 'All investigations' }} />
    : <div className={s.page}><ErrorState error={q.error!} onRetry={q.reload} /></div>;
  const c = q.data;

  const tabs: [string, string][] = [
    ['Overview', paths.case(caseId)], ['Evidence', paths.caseEvidence(caseId)], ['Analysis', paths.caseAnalysis(caseId)],
    ['Timeline', paths.caseTimeline(caseId)], ['Graph', paths.caseGraph(caseId)], ['Backtracking', paths.caseBacktracking(caseId)], ['Review', paths.caseReview(caseId)],
    ['Report', paths.caseReport(caseId)], ['Events', paths.caseEvents(caseId)],
  ];
  const current = [...tabs].reverse().find(([, href]) => pathname === href || (href !== paths.case(caseId) && pathname.startsWith(`${href}/`)))?.[1] ?? paths.case(caseId);

  async function lifecycle(action: 'archive' | 'reopen') {
    setBusy(true); setErr(null);
    try {
      const updated = action === 'archive' ? await api.cases.archive(caseId, reason.trim()) : await api.cases.reopen(caseId);
      prime(`case:${caseId}`, updated);
      invalidate('cases', `case:${caseId}`);
      notify(action === 'archive' ? `Archived ${updated.case_number}` : `Reopened ${updated.case_number}`);
      setConfirm(false); setReason('');
    } catch (e) { setErr(e instanceof ApiError ? e : new ApiError(0, 'CLIENT_ERROR', String(e))); }
    setBusy(false);
  }

  return <div className={s.caseFrame}>
    <header className={cs.head}>
      <div className={cs.identity}>
        <div className={cs.title}>
          {c ? <><b>{c.title}</b><span className={cs.meta}><span className={s.mono}>{c.case_number}</span><Dot tone={statusTone[c.status]}>{statusLabel[c.status]}</Dot>
            {(c.priority === 'HIGH' || c.priority === 'CRITICAL') && <Dot tone={priorityTone[c.priority]}>{priorityLabel[c.priority]} priority</Dot>}<span className={cs.quiet}>{categoryLabel[c.category]}</span></span></>
            : <><Skeleton h={18} w={280} /><Skeleton h={12} w={200} style={{ marginTop: 8 }} /></>}
        </div>
        {c && <div className={cs.actions}>
          {c.status === 'ARCHIVED'
            ? <button className={`${s.btn} ${s.sm}`} onClick={() => lifecycle('reopen')} disabled={busy}>{busy ? <LoaderCircle size={14} className={s.spin} /> : <RotateCcw size={14} />}Reopen</button>
            : <button className={`${s.btn} ${s.sm} ${s.ghost}`} onClick={() => setConfirm(v => !v)} aria-expanded={confirm}><Archive size={14} />Archive</button>}
          <select className={`${s.input} ${cs.select}`} value={current} onChange={e => router.push(e.target.value)} aria-label='Investigation section'>{tabs.map(([label, href]) => <option key={href} value={href}>{label}</option>)}</select>
        </div>}
      </div>
      <nav className={cs.tabs} aria-label='Investigation sections'>{tabs.map(([label, href]) => <Link key={href} href={href} aria-current={current === href ? 'page' : undefined}>{label}{label === 'Evidence' && c ? <i>{c.evidence_count}</i> : null}</Link>)}</nav>
    </header>
    {confirm && c && c.status !== 'ARCHIVED' && <div className={s.page} style={{ paddingTop: 16, paddingBottom: 0 }}>
      <div className={s.panel} role='dialog' aria-label='Archive this investigation'>
        <p className={s.title}>Archive {c.case_number}?</p>
        <p className={s.cap}>Archived investigations are read-only until reopened. Nothing is deleted; evidence and its custody record stay preserved.</p>
        <label className={s.field}><span>Reason (optional, recorded in the case history)</span><input className={s.input} value={reason} maxLength={500} onChange={e => setReason(e.target.value)} placeholder='e.g. duplicate report' /></label>
        {err && <ErrorState error={err} title='Not archived' />}
        <div className={p.formFoot}><button className={`${s.btn} ${s.primary}`} onClick={() => lifecycle('archive')} disabled={busy}>{busy && <LoaderCircle size={14} className={s.spin} />}Archive investigation</button><button className={`${s.btn} ${s.ghost}`} onClick={() => setConfirm(false)}>Cancel</button></div>
      </div>
    </div>}
    {err && !confirm && <div className={s.page} style={{ paddingTop: 16, paddingBottom: 0 }}><ErrorState error={err} /></div>}
    {c ? children : <div className={s.page}><Skeleton h={240} r={16} /></div>}
  </div>;
}
