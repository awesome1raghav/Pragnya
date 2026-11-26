'use client';

/* Breadcrumbs read the address, so they always describe the page you are on and every step is a real link.
   Case titles and evidence filenames come from the same cached API reads the pages use. */
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ChevronRight } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import { useCase, useEvidence } from '@/api/hooks';
import { ANALYSIS_LABEL, paths, type AnalysisBranch } from '@/config/routes';

const CASE_TAB: Record<string, string> = { evidence: 'Evidence', add: 'Add evidence', analysis: 'Analysis', timeline: 'Timeline', graph: 'Evidence graph', review: 'Review', report: 'Report', events: 'Events' };
const EV_TAB: Record<string, string> = { preview: 'Preview', metadata: 'Metadata', integrity: 'Integrity', timeline: 'Custody timeline', analysis: 'Analysis' };
const TOP: Record<string, [string, string]> = {
  dashboard: ['Dashboard', paths.dashboard()], investigations: ['Investigations', paths.investigations()], evidence: ['Evidence', '/evidence'],
  sources: ['Sources', '/sources'], lineage: ['Lineage', '/lineage'], intelligence: ['Intelligence', '/intelligence'], graph: ['Evidence graph', '/graph'],
  reports: ['Reports', '/reports'], notifications: ['Notifications', paths.notifications()], system: ['System', paths.system()], settings: ['Settings', paths.settings()],
};
const SUB: Record<string, string> = { new: 'New investigation', active: 'Active', completed: 'Completed', archived: 'Archived', health: 'Health', logs: 'Logs', preview: 'Preview' };

export default function Breadcrumbs() {
  const seg = usePathname().split('/').filter(Boolean).map(decodeURIComponent);
  const caseId = seg[0] === 'investigations' && seg[1] && !SUB[seg[1]] ? seg[1] : null;
  const evidenceId = seg[0] === 'evidence' && seg[1] ? seg[1] : null;
  const c = useCase(caseId);
  const ev = useEvidence(evidenceId);
  const evCase = useCase(ev.data?.case_id ?? null);
  const crumbs: { label: React.ReactNode; href?: string }[] = [];

  if (evidenceId) {
    crumbs.push({ label: 'Evidence', href: '/evidence' });
    if (ev.data) crumbs.push({ label: evCase.data?.case_number ?? 'Investigation', href: paths.case(ev.data.case_id) });
    crumbs.push({ label: <span className={s.mono}>{ev.data?.evidence_number ?? '…'}</span>, href: paths.evidence(evidenceId) });
    if (seg[2]) crumbs.push({ label: EV_TAB[seg[2]] ?? seg[2] });
  } else if (caseId) {
    crumbs.push({ label: 'Investigations', href: paths.investigations() });
    crumbs.push({ label: c.data ? `${c.data.case_number} · ${c.data.title}` : '…', href: paths.case(caseId) });
    const tab = seg[2] === 'evidence' && seg[3] === 'add' ? 'add' : seg[2];
    crumbs.push({ label: tab ? (seg[2] === 'analysis' && seg[3] ? `${ANALYSIS_LABEL[seg[3] as AnalysisBranch] ?? seg[3]} analysis` : CASE_TAB[tab] ?? tab) : 'Overview' });
  } else {
    const t = TOP[seg[0]];
    if (t) crumbs.push({ label: t[0], href: t[1] });
    if (seg[1]) crumbs.push({ label: SUB[seg[1]] ?? seg[1] });
  }

  return <nav className={s.crumbs} aria-label='Breadcrumb'>{crumbs.map((cr, i) => {
    const last = i === crumbs.length - 1;
    return <span key={i}>{i > 0 && <ChevronRight size={14} />}{cr.href && !last
      ? <Link className={s.crumb} href={cr.href}><span className={s.crumbText}>{cr.label}</span></Link>
      : <span className={s.crumb} aria-current={last ? 'page' : undefined}><span className={s.crumbText}>{cr.label}</span></span>}</span>;
  })}</nav>;
}
