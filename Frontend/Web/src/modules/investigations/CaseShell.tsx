'use client';

/* The frame around every /investigations/:caseId page: the case's name and status, and its sections as tabs
   (a select on phones, so no section hides in a sideways strip). */
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import type { ReactNode } from 'react';
import s from '@/styles/workspace.module.css';
import { useData } from '@/stores/workspace.store';
import { statusLabel, statusTone } from '@/utils/labels';
import { Dot } from '@/components/ui';
import { paths } from '@/config/routes';

export default function CaseShell({ caseId, children }: { caseId: string; children: ReactNode }) {
  const { cases, findings, evidence, decisions } = useData();
  const pathname = usePathname();
  const router = useRouter();
  const c = cases.find(x => x.id === caseId);
  if (!c) return <>{children}</>;
  const ev = evidence.filter(e => e.caseId === c.id);
  const open = findings.filter(f => ev.some(e => e.id === f.evidenceId) && f.status === 'open').length;
  const waiting = decisions.filter(d => d.caseId === c.id).length;
  const tabs: [string, string, number?][] = [
    ['Overview', paths.case(c.id)], ['Evidence', paths.caseEvidence(c.id), ev.length], ['Analysis', paths.caseAnalysis(c.id), open],
    ['Timeline', paths.caseTimeline(c.id)], ['Graph', paths.caseGraph(c.id)], ['Review', paths.caseReview(c.id), waiting],
    ['Report', paths.caseReport(c.id)], ['Events', paths.caseEvents(c.id)],
  ];
  const current = [...tabs].reverse().find(([, href]) => pathname === href || (href !== paths.case(c.id) && pathname.startsWith(`${href}/`)))?.[1] ?? paths.case(c.id);

  return <div className={s.caseFrame}>
    <header className={s.caseHead}>
      <div className={s.caseTitle}><b>{c.name}</b><span><Dot tone={statusTone[c.status]}>{statusLabel[c.status]}</Dot><span className={s.mono}>{c.id}</span></span></div>
      <nav className={s.caseTabs} aria-label='Case sections'>{tabs.map(([label, href, n]) => <Link key={href} href={href} aria-current={current === href ? 'page' : undefined}>{label}{n ? <i>{n}</i> : null}</Link>)}</nav>
      <select className={`${s.input} ${s.caseSelect}`} value={current} onChange={e => router.push(e.target.value)} aria-label='Case section'>{tabs.map(([label, href, n]) => <option key={href} value={href}>{label}{n ? ` (${n})` : ''}</option>)}</select>
    </header>
    {children}
  </div>;
}
