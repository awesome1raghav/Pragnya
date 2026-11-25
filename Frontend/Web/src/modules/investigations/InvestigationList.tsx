'use client';

/* /investigations and its filters (/active, /completed, /archived). One quiet row per case. */
import Link from 'next/link';
import { useMemo, useState } from 'react';
import { ChevronRight, Plus, Search } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import { useData } from '@/stores/workspace.store';
import type { Case } from '@/api';
import { statusLabel, statusTone, timeOf } from '@/utils/labels';
import { Dot, PageHead, Thumb } from '@/components/ui';
import { paths } from '@/config/routes';

export type CaseFilter = 'all' | 'active' | 'completed' | 'archived';
const MATCH: Record<CaseFilter, (c: Case) => boolean> = {
  all: () => true,
  active: c => c.status === 'flagged' || c.status === 'in_review' || c.status === 'active',
  completed: c => c.status === 'verified',
  archived: c => c.status === 'on_hold',
};
const TABS: [CaseFilter, string, string][] = [['all', 'All', paths.investigations()], ['active', 'Active', paths.investigations('active')], ['completed', 'Completed', paths.investigations('completed')], ['archived', 'Archived', paths.investigations('archived')]];

export default function InvestigationList({ filter = 'all' }: { filter?: CaseFilter }) {
  const { cases, evidence, findings } = useData();
  const [q, setQ] = useState('');
  const rows = useMemo(() => cases.filter(MATCH[filter]).filter(c => `${c.name} ${c.id} ${c.analyst}`.toLowerCase().includes(q.toLowerCase())).sort((a, b) => b.priority - a.priority), [cases, filter, q]);

  return <div className={s.page}>
    <PageHead title='Investigations' desc='Every case in this workspace, the most urgent first.'>
      <Link className={`${s.btn} ${s.primary}`} href={paths.newInvestigation()}><Plus size={15} />New investigation</Link>
    </PageHead>
    <div className={s.listBar}>
      <nav className={s.seg} aria-label='Filter investigations'>{TABS.map(([k, label, href]) => <Link key={k} href={href} aria-current={filter === k ? 'page' : undefined} aria-selected={filter === k} role='tab'>{label}<span className={s.count}>{cases.filter(MATCH[k]).length}</span></Link>)}</nav>
      <label className={`${s.cmdk} ${s.listSearch}`}><Search size={14} /><input value={q} onChange={e => setQ(e.target.value)} placeholder='Find a case, ID or analyst' aria-label='Find a case' /></label>
    </div>
    {rows.length ? <ul className={s.list}>{rows.map((c, i) => {
      const ev = evidence.filter(e => e.caseId === c.id);
      const open = findings.filter(f => ev.some(e => e.id === f.evidenceId) && f.status === 'open').length;
      return <li key={c.id}><Link className={s.listRow} href={paths.case(c.id)}>
        <Thumb media={c.cover} sizes='80px' eager={i < 6} />
        <span className={s.listMain}><b>{c.name}</b><small><span className={s.mono}>{c.id}</span> · {c.analyst} · {c.summary}</small></span>
        <Dot tone={statusTone[c.status]}>{statusLabel[c.status]}</Dot>
        <span className={s.listNum}><b>{ev.length}</b> files</span>
        <span className={s.listNum}><b>{open}</b> open</span>
        <time className={s.listTime}>{timeOf(c.updatedAt)}</time>
        <ChevronRight size={16} className={s.rowChev} />
      </Link></li>;
    })}</ul> : <div className={s.empty}><b>No investigations here</b><span>{q ? `Nothing matches “${q}”.` : 'Cases move here as their status changes.'}</span></div>}
  </div>;
}
