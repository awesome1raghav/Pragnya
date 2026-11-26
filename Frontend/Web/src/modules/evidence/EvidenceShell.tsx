'use client';

/* The frame around /evidence/:evidenceId pages: identity, integrity at a glance, and the tools as tabs.
   The evidence loads once; its investigation becomes the active context for global navigation. */
import Link from 'next/link';
import { useParams, usePathname, useRouter } from 'next/navigation';
import type { ReactNode } from 'react';
import { Download } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import p from '@/styles/platform.module.css';
import { api, type Evidence } from '@/api';
import { useCase, useEvidence, useIntegrity } from '@/api/hooks';
import { Dot, ErrorState, NotFoundState, Skeleton } from '@/components/ui';
import { paths, type EvidenceTool } from '@/config/routes';
import { useRecordCase } from '@/state/CaseContext';
import { bytes, mediaLabel } from '@/utils/labels';

export const useEvidenceId = () => decodeURIComponent(useParams<{ evidenceId: string }>().evidenceId);
export const useLoadedEvidence = () => useEvidence(useEvidenceId()).data as Evidence; // the shell renders tools only once loaded

const TOOLS: [EvidenceTool, string][] = [['overview', 'Overview'], ['preview', 'Preview'], ['metadata', 'Metadata'], ['integrity', 'Integrity'], ['timeline', 'Custody timeline'], ['analysis', 'Analysis']];

export default function EvidenceShell({ children }: { children: ReactNode }) {
  const id = useEvidenceId();
  const pathname = usePathname();
  const router = useRouter();
  const q = useEvidence(id);
  const ev = q.data;
  const c = useCase(ev?.case_id ?? null);
  const integrity = useIntegrity(ev ? id : null);
  useRecordCase(ev?.case_id);

  if (q.status === 'error' && !ev) return q.error?.notFound
    ? <NotFoundState what='evidence' back={{ href: '/evidence', label: 'All evidence' }} />
    : <div className={s.page}><ErrorState error={q.error!} onRetry={q.reload} /></div>;

  const seg = pathname.split('/')[3] as EvidenceTool | undefined;
  const current = seg && TOOLS.some(([t]) => t === seg) ? seg : 'overview';
  const last = integrity.data?.last_verification;

  return <div className={s.caseFrame}>
    <header className={s.caseHead}>
      <div className={s.caseTitle}>
        {ev ? <><b style={{ overflowWrap: 'anywhere' }}>{ev.filename}</b><span className={p.headMeta}>
          <span className={s.mono}>{ev.evidence_number}</span>
          <span>{mediaLabel[ev.media_type]} · {ev.mime_type} · {bytes(ev.file_size)}</span>
          <Dot tone='ok'>Preserved</Dot>
          {last ? <Dot tone={last.result === 'MATCH' ? 'ok' : 'alert'}>{last.result === 'MATCH' ? 'Last check: bytes match' : last.result === 'MISMATCH' ? 'Last check: BYTES DIFFER' : 'Last check: ORIGINAL MISSING'}</Dot> : integrity.data ? <Dot tone='mute'>Not re-verified since preservation</Dot> : null}
          {c.data && <Link href={paths.case(c.data.case_id)}>{c.data.case_number} · {c.data.title}</Link>}
        </span></> : <><Skeleton h={18} w={280} /><Skeleton h={12} w={220} style={{ marginTop: 8 }} /></>}
      </div>
      {ev && <div className={p.headActions}><a className={`${s.btn} ${s.sm} ${s.ghost}`} href={api.evidence.downloadUrl(ev.evidence_id)} download><Download size={14} />Download original</a></div>}
      <nav className={s.caseTabs} aria-label='Evidence tools'>{TOOLS.map(([t, label]) => <Link key={t} href={paths.evidence(id, t)} aria-current={current === t ? 'page' : undefined}>{label}</Link>)}</nav>
      <select className={`${s.input} ${s.caseSelect}`} value={current} onChange={e => router.push(paths.evidence(id, e.target.value as EvidenceTool))} aria-label='Evidence tool'>{TOOLS.map(([t, label]) => <option key={t} value={t}>{label}</option>)}</select>
    </header>
    {ev ? children : <div className={s.page}><Skeleton h={320} r={16} /></div>}
  </div>;
}
