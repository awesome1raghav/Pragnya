'use client';

/* The command center. It answers, in this order: what needs me, what is running, which investigations to continue,
   what changed, and what the methods inferred. Every item comes from stored records (/attention,
   /investigation-progress, jobs, events, findings); nothing here is estimated. System detail lives on /system. */
import Link from 'next/link';
import { useState } from 'react';
import { motion } from 'framer-motion';
import { AlertTriangle, ArrowRight, CheckCircle2, ChevronDown, FileAudio, FileVideo, Gavel, Image as ImageIcon, Plus, Search, XOctagon } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import p from '@/styles/platform.module.css';
import d from './dashboard.module.css';
import { api, type AttentionItem, type Case, type InvestigationEvent, type Paginated } from '@/api';
import { useQuery, type QueryResult } from '@/api/query';
import { useAttention, useCaseStatistics, useCases, useEvidenceStatistics, useJobs, useProgress } from '@/api/hooks';
import { Empty, ErrorState, Load, PageHead, SecHead, Skeleton } from '@/components/ui';
import { JobList, WorkerNotice } from '@/modules/jobs/Jobs';
import { StageTrack } from '@/modules/investigations/Stages';
import { useWorkspace } from '@/layouts/MainLayout';
import { useSystemState } from '@/layouts/SystemStatus';
import { paths } from '@/config/routes';
import { useHideTestRecords } from '@/state/testRecords';
import { ago, eventDetail, eventLabel, eventTone, toneColor } from '@/utils/labels';
import { useQueries } from './useQueries';

export default function Dashboard() {
  const { openPalette } = useWorkspace();
  const [hideTests, setHideTests] = useHideTestRecords();
  const stats = useCaseStatistics();
  const evStats = useEvidenceStatistics();
  const recent = useCases({ sort_by: 'last_activity_at', sort_order: 'desc', page_size: 4, hide_test_records: hideTests });
  const all = useCases({ page_size: 1 });
  const shown = useCases({ page_size: 1, hide_test_records: true });
  const hidden = hideTests && all.data && shown.data ? all.data.pagination.total_items - shown.data.pagination.total_items : 0;
  const st = stats.data, ev = evStats.data;

  return <div className={s.page}>
    <PageHead title='Dashboard' desc={st && ev ? <>{investigations(hideTests ? shown.data?.pagination.total_items : st.active_cases)} · <Link href={paths.evidenceList()} className={d.inline}>{ev.total_evidence} evidence items</Link> ({ev.by_media_type.IMAGE} images, {ev.by_media_type.VIDEO} video, {ev.by_media_type.AUDIO} audio)</> : 'Reading the current state…'}>
      <button className={`${s.btn} ${s.ghost}`} onClick={openPalette}><Search size={15} />Search</button>
      <Link className={`${s.btn} ${s.primary}`} href={paths.newInvestigation()}><Plus size={15} />New investigation</Link>
    </PageHead>
    {hidden > 0 && <p className={d.notice} role='note'>{hidden} automated test records are hidden from these lists. <button onClick={() => setHideTests(false)}>Show them</button></p>}
    {!hideTests && <p className={d.notice} role='note'>Showing automated test records too. <button onClick={() => setHideTests(true)}>Hide them</button></p>}
    {stats.error && !st ? <ErrorState error={stats.error} onRetry={stats.reload} /> : <>
      <div className={d.top}>
        <Attention hide={hideTests} />
        <div className={p.stack}><Running /><Readiness /></div>
      </div>
      <Continue q={recent} />
      <div className={p.grid2} style={{ marginTop: 28 }}>
        <Activity caseIds={recent.data?.data.map(c => c.case_id)} failed={!!recent.error && !recent.data} />
        <RecentFindings />
      </div>
    </>}
  </div>;
}

const investigations = (n: number | undefined) => n === undefined ? '…' : `${n} open investigation${n === 1 ? '' : 's'}`;

/* ── what needs me ── */
const attentionIcon = { RUN_FAILED: XOctagon, ALERT: AlertTriangle, WARNING: AlertTriangle, AWAITING_REVIEW: Gavel } as const;
const attentionTone = { RUN_FAILED: 'alert', ALERT: 'alert', WARNING: 'gold', AWAITING_REVIEW: 'gold' } as const;

function Attention({ hide }: { hide: boolean }) {
  const q = useAttention(hide);
  return <section className={`${s.panel} ${d.attention}`} aria-label='Needs your attention'>
    <SecHead title='Needs your attention' count={q.data?.length} />
    <Load q={q} rows={3}>{items => items.length ? <ul className={d.attnList}>{items.map((a, i) => <AttentionRow key={`${a.kind}-${a.at}-${i}`} a={a} i={i} />)}</ul>
      : <div className={d.clear}><CheckCircle2 size={22} /><div><b>Nothing needs you right now</b><small>No failed runs, no unread alerts, and every analysed investigation with inferences has a conclusion.</small></div></div>}</Load>
  </section>;
}

function AttentionRow({ a, i }: { a: AttentionItem; i: number }) {
  const Icon = attentionIcon[a.kind];
  const body = <><Icon size={16} style={{ color: toneColor[attentionTone[a.kind]] }} aria-hidden='true' /><span><b>{a.title}</b>{a.detail && <small>{a.detail}</small>}</span><time>{ago(a.at)}</time></>;
  return <motion.li initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i, 6) * 0.03, duration: .2 }}>
    {a.link ? <Link href={a.link} className={d.attnRow}>{body}<ArrowRight size={14} className={d.go} /></Link> : <div className={d.attnRow}>{body}</div>}
  </motion.li>;
}

/* ── what is running ── */
function Running() {
  const active = useJobs({ active: true, page_size: 4 });
  return <section className={s.panel} aria-label='Analysis jobs'>
    <SecHead title='Running now' count={active.data?.pagination.total_items} />
    <WorkerNotice quietWhenAlive />
    <Load q={active} rows={1}>{r => r.data.length ? <JobList jobs={r.data} /> : <p className={s.cap}>No analysis is queued or running. Finished runs are in each investigation’s Analysis tab.</p>}</Load>
  </section>;
}

function Readiness() {
  const st = useSystemState();
  return <Link href={paths.system()} className={d.ready} data-tone={st.tone} aria-label={`System: ${st.label}. ${st.detail}`}>
    <i aria-hidden='true' /><span><b>{st.label}</b><small>{st.tone === 'ok' ? 'API, database and evidence storage' : st.detail}</small></span><ArrowRight size={14} />
  </Link>;
}

/* ── which investigations to continue ── */
function Continue({ q }: { q: QueryResult<Paginated<Case>> }) {
  const ids = q.data?.data.map(c => c.case_id) ?? [];
  const progress = useProgress(ids);
  const by = new Map(progress.data?.map(x => [x.case_id, x]));
  return <section aria-label='Continue investigating' className={d.continue}>
    <SecHead title='Continue investigating'><Link href={paths.investigations()} className={s.secLink}>All investigations <ArrowRight size={13} /></Link></SecHead>
    <Load q={q} rows={2}>{page => page.data.length ? <div className={d.cards}>{page.data.map((c, i) => {
      const x = by.get(c.case_id);
      return <motion.div key={c.case_id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05, duration: .28, ease: [.22, 1, .36, 1] }}>
        <Link href={paths.case(c.case_id)} className={d.card} aria-label={`${c.case_number} ${c.title}`}>
          <div className={d.media}>{x?.image_evidence_id
            // the newest preserved image of this investigation, as stored
            // eslint-disable-next-line @next/next/no-img-element
            ? <img src={api.evidence.previewUrl(x.image_evidence_id)} alt='' loading='lazy' />
            : <span className={d.glyphs} aria-hidden='true'>{x?.by_media.VIDEO ? <FileVideo size={22} /> : null}{x?.by_media.AUDIO ? <FileAudio size={22} /> : null}{!x?.by_media.VIDEO && !x?.by_media.AUDIO ? <ImageIcon size={22} /> : null}</span>}
          </div>
          <div className={d.cardBody}>
            <small className={s.mono}>{c.case_number} · {ago(c.last_activity_at)}</small>
            <b>{c.title}</b>
            {x ? <StageTrack progress={x} compact /> : <Skeleton h={30} />}
          </div>
        </Link>
      </motion.div>;
    })}</div> : <Empty title='No investigations yet' action={<Link className={`${s.btn} ${s.primary}`} href={paths.newInvestigation()}><Plus size={15} />Create the first one</Link>}>Create an investigation, then add the media you need to examine. NEXTRON preserves it, hashes it and analyses it.</Empty>}</Load>
  </section>;
}

/* ── what changed: one group per investigation, newest first, the individual events one click away ── */
function Activity({ caseIds, failed }: { caseIds?: string[]; failed: boolean }) {
  const results = useQueries(caseIds?.map(id => ({ key: `case:${id}:summary`, fn: () => api.cases.summary(id) })) ?? []);
  const loading = !caseIds || results.some(r => r.status === 'loading' && !r.data);
  const groups = results.flatMap(r => r.data ? [{ c: r.data.case, events: r.data.recent_events.slice().sort((a, b) => b.sequence - a.sequence) }] : [])
    .filter(g => g.events.length).sort((a, b) => b.events[0].sequence - a.events[0].sequence);
  return <section className={s.panel} aria-label='Recent activity'>
    <SecHead title='What changed' />
    {failed ? <p className={s.cap}>Activity could not be loaded.</p> : loading ? <Skeleton h={140} r={12} /> : groups.length
      ? <ol className={d.groups}>{groups.map(g => <ActivityGroup key={g.c.case_id} caseId={g.c.case_id} number={g.c.case_number} title={g.c.title} events={g.events} />)}</ol>
      : <p className={s.cap}>No recorded activity yet.</p>}
  </section>;
}

function ActivityGroup({ caseId, number, title, events }: { caseId: string; number: string; title: string; events: InvestigationEvent[] }) {
  const [open, setOpen] = useState(false);
  const kinds = [...new Set(events.map(e => eventLabel(e.event_type)))];
  return <li className={d.group} style={{ ['--c' as string]: toneColor[eventTone(events[0].event_type)] }}>
    <button className={d.groupHead} onClick={() => setOpen(v => !v)} aria-expanded={open}>
      <span><b>{number}</b> <span className={s.muted}>{title}</span><small>{events.length} change{events.length === 1 ? '' : 's'}: {kinds.slice(0, 3).join(', ')}{kinds.length > 3 ? '…' : ''}</small></span>
      <time>{ago(events[0].occurred_at)}</time><ChevronDown size={14} style={{ transform: open ? 'rotate(180deg)' : undefined, transition: 'transform .2s' }} aria-hidden='true' />
    </button>
    {open && <motion.ol initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} transition={{ duration: .2 }} className={d.groupEvents}>
      {events.map(e => <li key={e.event_id}><Link href={e.evidence_id ? paths.evidence(e.evidence_id, 'timeline') : paths.caseEvents(caseId)}>{eventLabel(e.event_type)}</Link>
        <small>{eventDetail(e.event_type, e.payload) ?? e.actor} · {ago(e.occurred_at)}</small></li>)}
    </motion.ol>}
  </li>;
}

/* Inferences first: they are what an investigator reviews. Each is a method's reading, never a verdict. */
function RecentFindings() {
  const q = useQuery('findings:recent', () => api.findings.recent(5, 'INFERENCE'));
  return <section className={s.panel} aria-label='Recent inferences'>
    <SecHead title='Recent inferences'><span className={s.cap}>across investigations</span></SecHead>
    <Load q={q} rows={4}>{fs => fs.length ? <ul className={s.miniList}>{fs.map(f => <li key={f.finding_id}>
      <Link href={f.evidence[0] ? paths.evidence(f.evidence[0].evidence_id, 'analysis') : paths.caseAnalysis(f.case_id)}><b>{f.title}</b></Link>
      <small>{f.module_id} · {f.case_number}{f.evidence[0]?.evidence_number ? ` · ${f.evidence[0].evidence_number}` : ''} · {ago(f.created_at)}</small>
    </li>)}</ul> : <Empty title='No inferences yet'>Methods that read evidence beyond measuring it (detectors, consistency checks) report here.</Empty>}</Load>
    <p className={s.cap}>Scores are each method's own measure, not probabilities. Record your decision on an investigation's Review tab.</p>
  </section>;
}
