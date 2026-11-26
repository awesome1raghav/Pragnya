'use client';

/* /investigations and its filters (/active, /completed, /archived). Filtering, search, sorting and
   paging are done by the API, so the list covers every stored case, not just one loaded page. */
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { ChevronRight, Plus, Search } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import p from '@/styles/platform.module.css';
import { CASE_PRIORITIES, type CasePriority, type CaseQuery, type CaseSortKey, type CaseStatus } from '@/api';
import { useCaseStatistics, useCases } from '@/api/hooks';
import { Dot, Empty, Load, PageHead, Pager } from '@/components/ui';
import { paths, type CaseFilter } from '@/config/routes';
import { ACTIVE_STATUSES, COMPLETED_STATUSES, ago, priorityLabel, priorityTone, statusLabel, statusTone } from '@/utils/labels';

const FILTER: Record<CaseFilter, CaseStatus[] | undefined> = {
  all: undefined, // the API leaves archived cases out unless asked
  active: ACTIVE_STATUSES,
  completed: COMPLETED_STATUSES,
  archived: ['ARCHIVED'],
};
const TABS: [CaseFilter, string, string][] = [['all', 'All', paths.investigations()], ['active', 'Active', paths.investigations('active')], ['completed', 'Completed', paths.investigations('completed')], ['archived', 'Archived', paths.investigations('archived')]];
const SORTS: [CaseSortKey, 'asc' | 'desc', string][] = [['last_activity_at', 'desc', 'Last activity'], ['created_at', 'desc', 'Newest first'], ['created_at', 'asc', 'Oldest first'], ['priority', 'desc', 'Priority'], ['title', 'asc', 'Title A–Z'], ['case_number', 'desc', 'Case number']];
const PAGE_SIZE = 20;

export default function InvestigationList({ filter = 'all' }: { filter?: CaseFilter }) {
  const [text, setText] = useState('');
  const [search, setSearch] = useState('');
  const [priority, setPriority] = useState<CasePriority | ''>('');
  const [sort, setSort] = useState(0);
  const [page, setPage] = useState(1);
  useEffect(() => { const t = setTimeout(() => { setSearch(text.trim()); setPage(1); }, 250); return () => clearTimeout(t); }, [text]);
  useEffect(() => { setPage(1); }, [filter, priority, sort]);

  const q: CaseQuery = { status: FILTER[filter], search: search || undefined, priority: priority ? [priority] : undefined, sort_by: SORTS[sort][0], sort_order: SORTS[sort][1], page, page_size: PAGE_SIZE };
  const cases = useCases(q);
  const stats = useCaseStatistics();
  const count = (f: CaseFilter) => {
    const st = stats.data; if (!st) return null;
    if (f === 'all') return st.total_cases - st.by_status.ARCHIVED;
    return FILTER[f]!.reduce((n, x) => n + st.by_status[x], 0);
  };

  return <div className={s.page}>
    <PageHead title='Investigations' desc='Every investigation case. Open one to work on its evidence, timeline and review.'>
      <Link className={`${s.btn} ${s.primary}`} href={paths.newInvestigation()}><Plus size={15} />New investigation</Link>
    </PageHead>
    <div className={s.listBar}>
      <nav className={s.seg} aria-label='Filter investigations'>{TABS.map(([k, label, href]) => <Link key={k} href={href} aria-current={filter === k ? 'page' : undefined} aria-selected={filter === k}>{label}{count(k) !== null && <span className={s.count}>{count(k)}</span>}</Link>)}</nav>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        <label className={`${s.cmdk} ${s.listSearch}`}><Search size={14} /><input value={text} onChange={e => setText(e.target.value)} placeholder='Title, description or CASE-0001' aria-label='Search investigations' /></label>
        <select className={s.input} style={{ width: 'auto' }} value={priority} onChange={e => setPriority(e.target.value as CasePriority | '')} aria-label='Filter by priority'><option value=''>Any priority</option>{CASE_PRIORITIES.map(x => <option key={x} value={x}>{priorityLabel[x]}</option>)}</select>
        <select className={s.input} style={{ width: 'auto' }} value={sort} onChange={e => setSort(Number(e.target.value))} aria-label='Sort'>{SORTS.map(([, , label], i) => <option key={label} value={i}>{label}</option>)}</select>
      </div>
    </div>
    <Load q={cases} rows={6}>{res => res.data.length ? <>
      <div className={`${p.caseRow} ${p.listHead}`} aria-hidden='true'><span>Case</span><span>Title</span><span>Status</span><span>Priority</span><span>Evidence</span><span>Last activity</span><span /></div>
      <ul className={s.list}>{res.data.map(c => <li key={c.case_id}><Link className={p.caseRow} href={paths.case(c.case_id)}>
        <b>{c.case_number}</b>
        <span className={p.rowMain}><b>{c.title}</b><small>{c.description || 'No description'} · created {c.created_at.slice(0, 10)}</small></span>
        <Dot tone={statusTone[c.status]}>{statusLabel[c.status]}</Dot>
        <Dot tone={priorityTone[c.priority]}>{priorityLabel[c.priority]}</Dot>
        <span className={p.rowNum}><b>{c.evidence_count}</b> files</span>
        <time className={p.rowTime} dateTime={c.last_activity_at} title={c.last_activity_at}>{ago(c.last_activity_at)}</time>
        <ChevronRight size={16} className={s.rowChev} />
      </Link></li>)}</ul>
      <Pager page={res.pagination.page} pages={res.pagination.total_pages} total={res.pagination.total_items} onPage={setPage} />
    </> : <Empty title={search || priority ? 'No investigation matches' : filter === 'all' ? 'No investigations yet' : 'Nothing here'} action={filter === 'all' && !search && !priority ? <Link className={`${s.btn} ${s.primary}`} href={paths.newInvestigation()}><Plus size={15} />New investigation</Link> : undefined}>
      {search ? `Nothing matches “${search}”.` : filter === 'archived' ? 'Archived investigations appear here.' : 'Investigations appear here as they are created and progress.'}
    </Empty>}</Load>
  </div>;
}
