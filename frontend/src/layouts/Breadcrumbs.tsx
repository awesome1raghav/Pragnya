'use client';

/* Breadcrumbs read the address, so they always describe the page you are on and every step is a real link. */
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ChevronRight } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import { useData } from '@/stores/workspace.store';
import { ANALYSIS_LABEL, paths, toolFromSegment, type AnalysisBranch } from '@/config/routes';

const TOOL = { viewer: 'Viewer', frames: 'Examine', timeline: 'Timeline', metadata: 'Metadata' } as const;
const CASE_TAB: Record<string, string> = { evidence: 'Evidence', add: 'Add evidence', analysis: 'Analysis', timeline: 'Timeline', graph: 'Evidence graph', review: 'Review', report: 'Report', events: 'Events' };
const TOP: Record<string, [string, string]> = {
  dashboard: ['Dashboard', paths.dashboard()], investigations: ['Investigations', paths.investigations()], evidence: ['Evidence', paths.evidenceList()],
  graph: ['Evidence graph', paths.graph()], reports: ['Reports', paths.reports()], notifications: ['Notifications', paths.notifications()],
  system: ['System', paths.system()], settings: ['Settings', paths.settings()],
};
const SUB: Record<string, string> = { new: 'New investigation', active: 'Active', completed: 'Completed', archived: 'Archived', health: 'Health', logs: 'Logs', preview: 'Preview' };

export default function Breadcrumbs() {
  const pathname = usePathname();
  const { cases, evidence } = useData();
  const seg = pathname.split('/').filter(Boolean).map(decodeURIComponent);
  const crumbs: { label: React.ReactNode; href?: string }[] = [];
  const caseCrumb = (id: string) => { const c = cases.find(x => x.id === id); crumbs.push({ label: c?.name ?? id, href: paths.case(id) }); };

  if (seg[0] === 'evidence' && seg[1]) {
    const ev = evidence.find(e => e.id === seg[1]);
    crumbs.push({ label: 'Investigations', href: paths.investigations() });
    if (ev) caseCrumb(ev.caseId);
    crumbs.push({ label: <span className={s.mono}>{ev?.fileName ?? seg[1]}</span>, href: paths.evidence(seg[1]) });
    crumbs.push({ label: seg[2] === 'integrity' ? 'Integrity' : TOOL[toolFromSegment(seg[2])] });
  } else if (seg[0] === 'investigations' && seg[1] && !SUB[seg[1]]) {
    crumbs.push({ label: 'Investigations', href: paths.investigations() });
    caseCrumb(seg[1]);
    const tab = seg[2] === 'evidence' && seg[3] === 'add' ? 'add' : seg[2];
    crumbs.push({ label: tab ? (seg[2] === 'analysis' && seg[3] ? `${ANALYSIS_LABEL[seg[3] as AnalysisBranch] ?? seg[3]} analysis` : CASE_TAB[tab] ?? tab) : 'Overview' });
  } else if (seg[0] === 'reports' && seg[1]) {
    crumbs.push({ label: 'Reports', href: paths.reports() });
    crumbs.push({ label: cases.find(x => x.id === seg[1])?.name ?? seg[1], href: paths.report(seg[1]) });
    if (seg[2]) crumbs.push({ label: SUB[seg[2]] ?? seg[2] });
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
