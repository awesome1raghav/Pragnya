'use client';

/* /investigations and its filters (/active, /completed, /archived). Filtering, search, sorting and paging are done by
   the API, so the list covers every stored case, not one loaded page. Two views: a readable list for scanning and a
   visual board where the investigation's own newest image helps recognition. Each entry names its next action, from
   /investigation-progress. Search, filters, page, view and scroll position survive a visit to an investigation. */
import Link from 'next/link';
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { ChevronRight, FileAudio, FileVideo, Image as ImageIcon, LayoutGrid, List, Plus, Search } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import p from '@/styles/platform.module.css';
import v from './list.module.css';
import { api, CASE_PRIORITIES, type Case, type CasePriority, type CaseQuery, type CaseSortKey, type CaseStatus, type Progress } from '@/api';
import { useCaseStatistics, useCases, useProgress } from '@/api/hooks';
import { Dot, Empty, Load, PageHead, Pager } from '@/components/ui';
import { StageTrack } from './Stages';
import { paths, type CaseFilter } from '@/config/routes';
import { useHideTestRecords } from '@/state/testRecords';
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
const STATE_KEY = 'nx-cases-list';
type Saved = { text: string; priority: CasePriority | ''; sort: number; page: number; view: 'list' | 'board'; scroll: number };

const restore = (): Partial<Saved> => { try { return JSON.parse(sessionStorage.getItem(STATE_KEY) ?? '{}') as Partial<Saved>; } catch { return {}; } };

export default function InvestigationList({ filter = 'all' }: { filter?: CaseFilter }) {
  const saved = useRef(restore());
  const [text, setText] = useState(saved.current.text ?? '');
  const [search, setSearch] = useState((saved.current.text ?? '').trim());
  const [priority, setPriority] = useState<CasePriority | ''>(saved.current.priority ?? '');
  const [sort, setSort] = useState(saved.current.sort ?? 0);
  const [page, setPage] = useState(saved.current.page ?? 1);
  const [view, setView] = useState<'list' | 'board'>(() => { try { return localStorage.getItem('nx-cases-view') === 'board' ? 'board' : 'list'; } catch { return 'list'; } });
  const [hideTests, setHideTests] = useHideTestRecords();
  const first = useRef(true);
  useEffect(() => { const t = setTimeout(() => { setSearch(text.trim()); if (!first.current) setPage(1); }, 250); return () => clearTimeout(t); }, [text]);
  useEffect(() => { if (first.current) { first.current = false; return; } setPage(1); }, [filter, priority, sort, hideTests]);
  useEffect(() => { try { localStorage.setItem('nx-cases-view', view); } catch { /* ignore */ } }, [view]);
  // remember where the operator was, including the scroll position, for the way back from an investigation
  useEffect(() => {
    const save = () => { try { sessionStorage.setItem(STATE_KEY, JSON.stringify({ text, priority, sort, page, view, scroll: window.scrollY } satisfies Saved)); } catch { /* ignore */ } };
    save(); window.addEventListener('scroll', save, { passive: true });
    return () => { save(); window.removeEventListener('scroll', save); };
  }, [text, priority, sort, page, view]);

  const q: CaseQuery = { status: FILTER[filter], search: search || undefined, priority: priority ? [priority] : undefined, sort_by: SORTS[sort][0], sort_order: SORTS[sort][1], page, page_size: PAGE_SIZE, hide_test_records: hideTests };
  const cases = useCases(q);
  const unfiltered = useCases({ ...q, hide_test_records: false, page: 1, page_size: 1 });
  const hidden = hideTests && cases.data && unfiltered.data ? unfiltered.data.pagination.total_items - cases.data.pagination.total_items : 0;
  const ids = cases.data?.data.map(c => c.case_id) ?? [];
  const progress = useProgress(ids);
  const by = new Map(progress.data?.map(x => [x.case_id, x]));
  const stats = useCaseStatistics();
  const count = (f: CaseFilter) => {
    const st = stats.data; if (!st || hideTests) return null;  // the overall statistics include test records
    if (f === 'all') return st.total_cases - st.by_status.ARCHIVED;
    return FILTER[f]!.reduce((n, x) => n + st.by_status[x], 0);
  };
  useLayoutEffect(() => {  // back from an investigation: return to the same place once the same page has loaded
    if (cases.data && saved.current.scroll) { window.scrollTo({ top: saved.current.scroll }); saved.current.scroll = 0; }
  }, [cases.data]);

  return <div className={s.page}>
    <PageHead title='Investigations' desc='Find an investigation, see where it stands, and continue where it needs you.'>
      <Link className={`${s.btn} ${s.primary}`} href={paths.newInvestigation()}><Plus size={15} />New investigation</Link>
    </PageHead>
    <div className={s.listBar}>
      <nav className={s.seg} aria-label='Filter investigations'>{TABS.map(([k, label, href]) => <Link key={k} href={href} aria-current={filter === k ? 'page' : undefined} aria-selected={filter === k}>{label}{count(k) !== null && <span className={s.count}>{count(k)}</span>}</Link>)}</nav>
      <div className={v.tools}>
        <label className={`${s.cmdk} ${s.listSearch}`}><Search size={14} /><input value={text} onChange={e => setText(e.target.value)} placeholder='Title, description or CASE-0001' aria-label='Search investigations' /></label>
        <select className={s.input} style={{ width: 'auto' }} value={priority} onChange={e => setPriority(e.target.value as CasePriority | '')} aria-label='Filter by priority'><option value=''>Any priority</option>{CASE_PRIORITIES.map(x => <option key={x} value={x}>{priorityLabel[x]}</option>)}</select>
        <select className={s.input} style={{ width: 'auto' }} value={sort} onChange={e => setSort(Number(e.target.value))} aria-label='Sort'>{SORTS.map(([, , label], i) => <option key={label} value={i}>{label}</option>)}</select>
        <div className={s.seg} role='group' aria-label='View'>
          <button aria-pressed={view === 'list'} onClick={() => setView('list')} aria-label='List view'><List size={15} /></button>
          <button aria-pressed={view === 'board'} onClick={() => setView('board')} aria-label='Board view'><LayoutGrid size={15} /></button>
        </div>
      </div>
    </div>
    {hidden > 0 && <p className={v.notice} role='note'>{hidden} automated test record{hidden === 1 ? '' : 's'} hidden. <button onClick={() => setHideTests(false)}>Show them</button></p>}
    {!hideTests && <p className={v.notice} role='note'>Showing automated test records ([E2E], [Bench], [Drill], [Test], [Smoke]). <button onClick={() => setHideTests(true)}>Hide them</button></p>}
    <Load q={cases} rows={6}>{res => res.data.length ? <>
      {view === 'list' ? <ul className={v.list}>{res.data.map((c, i) => <Row key={c.case_id} c={c} x={by.get(c.case_id)} i={i} />)}</ul>
        : <div className={v.board}>{res.data.map((c, i) => <Tile key={c.case_id} c={c} x={by.get(c.case_id)} i={i} />)}</div>}
      <Pager page={res.pagination.page} pages={res.pagination.total_pages} total={res.pagination.total_items} onPage={n => { setPage(n); window.scrollTo({ top: 0 }); }} />
    </> : <Empty title={search || priority ? 'No investigation matches' : filter === 'all' ? 'No investigations yet' : 'Nothing here'} action={filter === 'all' && !search && !priority ? <Link className={`${s.btn} ${s.primary}`} href={paths.newInvestigation()}><Plus size={15} />New investigation</Link> : undefined}>
      {search ? `Nothing matches “${search}”.` : filter === 'archived' ? 'Archived investigations appear here.' : hidden ? 'Only automated test records are here; show them above.' : 'Investigations appear here as they are created and progress.'}
    </Empty>}</Load>
  </div>;
}

const notable = (c: Case) => c.priority === 'HIGH' || c.priority === 'CRITICAL';

function Row({ c, x, i }: { c: Case; x?: Progress; i: number }) {
  return <motion.li initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: Math.min(i, 10) * 0.015, duration: .16 }}>
    <Link className={v.row} href={paths.case(c.case_id)}>
      <span className={v.main}>
        <b>{c.title}</b>
        <small><span className={s.mono}>{c.case_number}</span> · {c.evidence_count} evidence · active {ago(c.last_activity_at)}{c.description ? ` · ${c.description}` : ''}</small>
      </span>
      <span className={v.state}>
        <Dot tone={statusTone[c.status]}>{statusLabel[c.status]}</Dot>
        {notable(c) && <Dot tone={priorityTone[c.priority]}>{priorityLabel[c.priority]} priority</Dot>}
      </span>
      <span className={v.next} data-stage={x?.stage}>{x ? x.next_action : ''}</span>
      <ChevronRight size={16} className={s.rowChev} />
    </Link>
  </motion.li>;
}

function Tile({ c, x, i }: { c: Case; x?: Progress; i: number }) {
  return <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i, 12) * 0.025, duration: .22, ease: [.22, 1, .36, 1] }}>
    <Link className={v.tile} href={paths.case(c.case_id)} aria-label={`${c.case_number} ${c.title}`}>
      <div className={v.media}>{x?.image_evidence_id
        // the investigation's newest preserved image, as stored
        // eslint-disable-next-line @next/next/no-img-element
        ? <img src={api.evidence.previewUrl(x.image_evidence_id)} alt='' loading='lazy' />
        : <span aria-hidden='true'>{x?.by_media.VIDEO ? <FileVideo size={22} /> : x?.by_media.AUDIO ? <FileAudio size={22} /> : <ImageIcon size={22} />}</span>}
      </div>
      <div className={v.tileBody}>
        <small className={s.mono}>{c.case_number} · {ago(c.last_activity_at)}</small>
        <b>{c.title}</b>
        <span className={v.tileState}><Dot tone={statusTone[c.status]}>{statusLabel[c.status]}</Dot>{notable(c) && <Dot tone={priorityTone[c.priority]}>{priorityLabel[c.priority]}</Dot>}</span>
        {x && <StageTrack progress={x} compact />}
      </div>
    </Link>
  </motion.div>;
}
