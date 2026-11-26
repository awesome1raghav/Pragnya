'use client';

/* The investigation workspace's tabs. Every value comes from the API: the case record, its evidence,
   its statistics and its append-only event history. Sections whose backend does not exist yet are
   shown as such, with the module that will provide them. */
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { ArrowRight, FileText, Film, GitBranch, Globe2, LoaderCircle, Network, Pencil, Plus, Save, Share2 } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import p from '@/styles/platform.module.css';
import { ApiError, CASE_CATEGORIES, CASE_PRIORITIES, api, type Case, type CaseCategory, type CasePriority, type InvestigationEvent } from '@/api';
import { useCase, useCaseEvidence, useCaseSummary, useModules } from '@/api/hooks';
import { invalidate, prime, useQuery } from '@/api/query';
import { Dot, Empty, ErrorState, Load, PageHead, SecHead, Unavailable } from '@/components/ui';
import { CaseAnalysisPage, ModuleResultsPage } from '@/modules/analysis/Analysis';
import { useWorkspace } from '@/layouts/MainLayout';
import { ANALYSIS_BRANCHES, ANALYSIS_LABEL, ANALYSIS_MODULE, paths, type AnalysisBranch } from '@/config/routes';
import { ago, bytes, categoryLabel, eventDetail, eventLabel, eventTone, moduleStatusLabel, moduleStatusTone, priorityLabel, toneColor, utc } from '@/utils/labels';
import EvidenceRows from '@/modules/evidence/EvidenceRows';
import Uploader from '@/modules/evidence/Uploader';
import { fieldErrors, parseTags } from './NewInvestigation';
import { useCaseId } from './CaseShell';

const useLoadedCase = () => useCase(useCaseId()).data as Case; // CaseShell renders tabs only once the case has loaded

/* ── /investigations/:caseId ── */
export function CaseOverview() {
  const c = useLoadedCase();
  const summary = useCaseSummary(c.case_id);
  const archived = c.status === 'ARCHIVED';
  return <div className={s.page}>
    <div className={p.grid2}>
      <div className={p.stack}>
        <Details c={c} archived={archived} />
        <Notes c={c} archived={archived} />
        <section className={s.panel} aria-label='Evidence overview'>
          <SecHead title='Evidence' count={c.evidence_count}>
            <span className={s.actions}>{!archived && <Link className={`${s.btn} ${s.sm} ${s.primary}`} href={paths.caseAddEvidence(c.case_id)}><Plus size={14} />Add evidence</Link>}<Link href={paths.caseEvidence(c.case_id)} className={s.secLink}>All <ArrowRight size={13} /></Link></span>
          </SecHead>
          <Load q={summary} rows={1}>{sm => <div className={p.statGrid}>
            {(['IMAGE', 'VIDEO', 'AUDIO'] as const).map(m => <div key={m} className={p.stat}><span>{m === 'IMAGE' ? 'Images' : m === 'VIDEO' ? 'Videos' : 'Audio'}</span><b>{sm.statistics.evidence_by_media_type[m]}</b></div>)}
            <div className={p.stat}><span>Stored</span><b>{bytes(sm.statistics.evidence_total_bytes)}</b></div>
          </div>}</Load>
          <RecentEvidence caseId={c.case_id} />
        </section>
      </div>
      <div className={p.stack}>
        <section className={s.panel} aria-label='Investigate this case in'>
          <SecHead title='Work on this investigation' />
          <nav className={p.ctxNav}>
            <Link href={paths.evidenceList(c.case_id)}><Film size={15} />Evidence</Link>
            <Link href={paths.sources(c.case_id)}><Globe2 size={15} />Sources <small>not built</small></Link>
            <Link href={paths.lineage(c.case_id)}><GitBranch size={15} />Lineage <small>not built</small></Link>
            <Link href={paths.intelligence(c.case_id)}><Network size={15} />Intelligence</Link>
            <Link href={paths.graph(c.case_id)}><Share2 size={15} />Evidence graph <small>not built</small></Link>
            <Link href={paths.reports(c.case_id)}><FileText size={15} />Reports <small>not built</small></Link>
          </nav>
        </section>
        <ModuleOverview caseId={c.case_id} />
        <section className={s.panel} aria-label='Recent activity'>
          <SecHead title='Recent activity'><Link href={paths.caseEvents(c.case_id)} className={s.secLink}>All events <ArrowRight size={13} /></Link></SecHead>
          <Load q={summary} rows={3}>{sm => <EventFeed events={sm.recent_events.slice(0, 6)} />}</Load>
        </section>
        <Unavailable title='Review and report' modules={['NEX-INV', 'NEX-RPT']} step='plan Step 7'>
          <p>Investigator decisions (accept, reject, inconclusive, needs more evidence) and versioned PDF/JSON reports are built after the analysis modules, because they review and report their findings.</p>
        </Unavailable>
      </div>
    </div>
  </div>;
}

function Details({ c, archived }: { c: Case; archived: boolean }) {
  const { notify } = useWorkspace();
  const [edit, setEdit] = useState(false);
  const [f, setF] = useState({ title: c.title, description: c.description ?? '', objectives: c.objectives ?? '', category: c.category, priority: c.priority, tags: c.tags.join(', ') });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<ApiError | null>(null);
  const fe = fieldErrors(err);
  const open = () => { setF({ title: c.title, description: c.description ?? '', objectives: c.objectives ?? '', category: c.category, priority: c.priority, tags: c.tags.join(', ') }); setErr(null); setEdit(true); };
  async function save() {
    setBusy(true); setErr(null);
    try {
      const updated = await api.cases.update(c.case_id, { title: f.title.trim(), description: f.description.trim() || null, objectives: f.objectives.trim() || null, category: f.category, priority: f.priority, tags: parseTags(f.tags) });
      prime(`case:${c.case_id}`, updated); invalidate('cases', `case:${c.case_id}`);
      notify(updated.revision > c.revision ? `Saved · revision ${updated.revision}` : 'Nothing changed');
      setEdit(false);
    } catch (e) { setErr(e instanceof ApiError ? e : new ApiError(0, 'CLIENT_ERROR', String(e))); }
    setBusy(false);
  }
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setF(v => ({ ...v, [k]: e.target.value }));

  if (edit) return <section className={s.panel} aria-label='Edit investigation details'>
    <SecHead title='Edit details' />
    <div className={p.formGrid}>
      <label className={`${s.field} ${p.formWide}`}><span>Title</span><input className={s.input} value={f.title} onChange={set('title')} maxLength={200} />{fe.title && <span className={p.fieldError}>{fe.title}</span>}</label>
      <label className={s.field}><span>Category</span><select className={s.input} value={f.category} onChange={e => setF(v => ({ ...v, category: e.target.value as CaseCategory }))}>{CASE_CATEGORIES.map(x => <option key={x} value={x}>{categoryLabel[x]}</option>)}</select></label>
      <label className={s.field}><span>Priority</span><select className={s.input} value={f.priority} onChange={e => setF(v => ({ ...v, priority: e.target.value as CasePriority }))}>{CASE_PRIORITIES.map(x => <option key={x} value={x}>{priorityLabel[x]}</option>)}</select></label>
      <label className={`${s.field} ${p.formWide}`}><span>Objectives</span><textarea className={`${s.input} ${p.textarea}`} value={f.objectives} onChange={set('objectives')} maxLength={5000} />{fe.objectives && <span className={p.fieldError}>{fe.objectives}</span>}</label>
      <label className={`${s.field} ${p.formWide}`}><span>Description</span><textarea className={`${s.input} ${p.textarea}`} value={f.description} onChange={set('description')} maxLength={10000} /></label>
      <label className={`${s.field} ${p.formWide}`}><span>Tags (comma-separated)</span><input className={s.input} value={f.tags} onChange={set('tags')} />{fe.tags && <span className={p.fieldError}>{fe.tags}</span>}</label>
    </div>
    {err && !Object.keys(fe).length && <ErrorState error={err} title='Not saved' />}
    <div className={p.formFoot}><button className={`${s.btn} ${s.primary}`} onClick={save} disabled={busy || !f.title.trim()}>{busy ? <LoaderCircle size={14} className={s.spin} /> : <Save size={14} />}Save</button><button className={`${s.btn} ${s.ghost}`} onClick={() => setEdit(false)}>Cancel</button></div>
  </section>;

  return <section className={s.panel} aria-label='Investigation details'>
    <SecHead title='Details'>{!archived && <button className={`${s.btn} ${s.sm} ${s.ghost}`} onClick={open}><Pencil size={14} />Edit</button>}</SecHead>
    <div><p className={s.cap}>Objectives</p><p className={p.notes} style={{ marginTop: 4 }}>{c.objectives || <span className={s.muted}>No objectives recorded yet.</span>}</p></div>
    {c.description && <div><p className={s.cap}>Description</p><p className={p.notes} style={{ marginTop: 4 }}>{c.description}</p></div>}
    <dl className={p.facts}>
      <div><dt>Category</dt><dd>{categoryLabel[c.category]}</dd></div>
      <div><dt>Priority</dt><dd>{priorityLabel[c.priority]}</dd></div>
      <div><dt>Created</dt><dd title={c.created_at}>{utc(c.created_at)}</dd></div>
      <div><dt>Created by</dt><dd>{c.created_by}</dd></div>
      <div><dt>Last activity</dt><dd title={c.last_activity_at}>{ago(c.last_activity_at)}</dd></div>
      <div><dt>Revision</dt><dd>{c.revision}</dd></div>
      {c.tags.length > 0 && <div style={{ gridColumn: '1 / -1' }}><dt>Tags</dt><dd className={p.chips}>{c.tags.map(t => <span key={t}>{t}</span>)}</dd></div>}
      {c.archived_at && <div><dt>Archived</dt><dd>{utc(c.archived_at)}</dd></div>}
    </dl>
  </section>;
}

function Notes({ c, archived }: { c: Case; archived: boolean }) {
  const { notify } = useWorkspace();
  const [draft, setDraft] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<ApiError | null>(null);
  async function save() {
    setBusy(true); setErr(null);
    try {
      const updated = await api.cases.update(c.case_id, { notes: draft!.trim() || null });
      prime(`case:${c.case_id}`, updated); invalidate(`case:${c.case_id}`);
      notify('Notes saved'); setDraft(null);
    } catch (e) { setErr(e instanceof ApiError ? e : new ApiError(0, 'CLIENT_ERROR', String(e))); }
    setBusy(false);
  }
  return <section className={s.panel} aria-label='Investigator notes'>
    <SecHead title='Investigator notes'>{draft === null && !archived && <button className={`${s.btn} ${s.sm} ${s.ghost}`} onClick={() => setDraft(c.notes ?? '')}><Pencil size={14} />Edit</button>}</SecHead>
    {draft === null ? <p className={p.notes}>{c.notes || <span className={s.muted}>No notes yet.</span>}</p> : <>
      <textarea className={`${s.input} ${p.textarea}`} value={draft} onChange={e => setDraft(e.target.value)} maxLength={20000} aria-label='Investigator notes' style={{ minHeight: 140 }} autoFocus />
      {err && <ErrorState error={err} title='Notes not saved' />}
      <div className={p.formFoot}><button className={`${s.btn} ${s.primary}`} onClick={save} disabled={busy}>{busy ? <LoaderCircle size={14} className={s.spin} /> : <Save size={14} />}Save notes</button><button className={`${s.btn} ${s.ghost}`} onClick={() => setDraft(null)}>Cancel</button><p>Each save is recorded in the case history.</p></div>
    </>}
  </section>;
}

function RecentEvidence({ caseId }: { caseId: string }) {
  const q = useCaseEvidence(caseId);
  return <Load q={q} rows={2}>{page => page.data.length ? <EvidenceRows items={page.data.slice(0, 5)} /> : <p className={s.cap}>No evidence yet. Add the original files you need to examine.</p>}</Load>;
}

function ModuleOverview({ caseId }: { caseId: string }) {
  const q = useModules();
  return <section className={s.panel} aria-label='Module execution overview'>
    <SecHead title='Investigation modules'><Link href={paths.intelligence(caseId)} className={s.secLink}>Intelligence <ArrowRight size={13} /></Link></SecHead>
    <Load q={q} rows={2}>{cat => {
      const by = (st: string) => cat.modules.filter(m => m.status === st);
      return <>
        <p className={s.cap}>Per-investigation execution status arrives with T-MIR (plan Step 3). Today:</p>
        <ul className={s.miniList}>{(['IMPLEMENTED', 'PARTIAL', 'NOT_IMPLEMENTED'] as const).map(st => <li key={st}><Dot tone={moduleStatusTone[st]}>{moduleStatusLabel[st]}</Dot><small>{by(st).map(m => m.module_id).join(' · ') || 'none'}</small></li>)}</ul>
      </>;
    }}</Load>
  </section>;
}

export function EventFeed({ events }: { events: InvestigationEvent[] }) {
  if (!events.length) return <p className={s.cap}>Nothing recorded yet.</p>;
  return <ol className={s.feed} style={{ padding: '4px 0' }}>{events.map(e => <li key={e.event_id} style={{ color: toneColor[eventTone(e.event_type)] }}>
    <time title={e.occurred_at}>{ago(e.occurred_at)}</time>
    <p>{e.evidence_id ? <Link href={paths.evidence(e.evidence_id, 'timeline')}>{eventLabel(e.event_type)}</Link> : eventLabel(e.event_type)}<small>{eventDetail(e.event_type, e.payload) ?? e.actor}</small></p>
  </li>)}</ol>;
}

/* ── /investigations/:caseId/evidence ── */
export function CaseEvidence() {
  const c = useLoadedCase();
  const q = useCaseEvidence(c.case_id);
  return <div className={s.page}>
    <PageHead title='Evidence' desc={`Every file preserved in ${c.case_number}, newest first. Open one to examine it.`}>
      {c.status !== 'ARCHIVED' && <Link className={`${s.btn} ${s.primary}`} href={paths.caseAddEvidence(c.case_id)}><Plus size={15} />Add evidence</Link>}
    </PageHead>
    <Load q={q} rows={4}>{page => page.data.length ? <EvidenceRows items={page.data} /> : <Empty title='No evidence yet' action={c.status !== 'ARCHIVED' ? <Link className={`${s.btn} ${s.primary}`} href={paths.caseAddEvidence(c.case_id)}><Plus size={15} />Add evidence</Link> : undefined}>Upload the original image, video or audio files.</Empty>}</Load>
  </div>;
}

/* ── /investigations/:caseId/evidence/add ── */
export function CaseAddEvidence() {
  const c = useLoadedCase();
  const [done, setDone] = useState(0);
  if (c.status === 'ARCHIVED') return <div className={s.page}><Empty title='This investigation is archived'>Reopen it before adding evidence.</Empty></div>;
  return <div className={s.page}>
    <PageHead title='Add evidence' desc={<>Files are preserved in <b>{c.case_number} · {c.title}</b>. Each one is hashed on the server and stored read-only before anything else happens to it.</>}>
      {done > 0 && <Link className={`${s.btn} ${s.primary}`} href={paths.caseEvidence(c.case_id)}>View evidence <ArrowRight size={15} /></Link>}
    </PageHead>
    <Uploader caseId={c.case_id} onDone={r => setDone(n => n + r.length)} />
  </div>;
}

/* ── /investigations/:caseId/timeline ── */
export function CaseTimeline() {
  const c = useLoadedCase();
  const q = useQuery(`case:${c.case_id}:events:all`, async () => {
    const all: InvestigationEvent[] = [];
    let after = 0;
    for (let i = 0; i < 20; i++) { const page = await api.cases.events(c.case_id, after, 200); all.push(...page.data); if (!page.cursor.has_more || page.cursor.next_after === null) break; after = page.cursor.next_after; }
    return all;
  });
  return <div className={s.page}>
    <PageHead title='Timeline' desc={`What has happened in ${c.case_number}, in order, from its recorded history. Times are when NEXTRON recorded each event.`} />
    <div className={s.tlPage}>
      <Load q={q} rows={6}>{events => events.length ? <ol className={s.chron}>{events.map(e => <li key={e.event_id} style={{ ['--c' as string]: toneColor[eventTone(e.event_type)] }}>
        <time>{e.occurred_at.slice(0, 10)}<span>{e.occurred_at.slice(11, 19)} UTC</span></time>
        <div>{e.evidence_id ? <Link href={paths.evidence(e.evidence_id, 'timeline')}><b>{eventLabel(e.event_type)}</b></Link> : <b>{eventLabel(e.event_type)}</b>}<small>{eventDetail(e.event_type, e.payload) ?? ''} · {e.actor}</small></div>
      </li>)}</ol> : <Empty title='Nothing recorded yet' />}</Load>
      <aside>
        <Unavailable title='Event reconstruction' modules={['NEX-REC', 'NEX-EGC']} step='plan Step 7'>
          <p>This timeline is the investigation’s own record. Reconstructing the media’s history (publication, capture and edit times from sources and analysis) is NEX-REC’s job and is not built yet.</p>
        </Unavailable>
      </aside>
    </div>
  </div>;
}

/* ── /investigations/:caseId/events ── */
export function CaseEvents() {
  const c = useLoadedCase();
  const [pages, setPages] = useState<InvestigationEvent[][]>([]);
  const [cursor, setCursor] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<ApiError | null>(null);
  const [kind, setKind] = useState<'all' | 'case' | 'evidence'>('all');
  async function more() {
    if (cursor === null) return;
    setBusy(true); setErr(null);
    try { const page = await api.cases.events(c.case_id, cursor, 50); setPages(p0 => [...p0, page.data]); setCursor(page.cursor.has_more ? page.cursor.next_after : null); }
    catch (e) { setErr(e instanceof ApiError ? e : new ApiError(0, 'CLIENT_ERROR', String(e))); }
    setBusy(false);
  }
  useEffect(() => { // first page replaces (safe when effects run twice in development)
    let live = true;
    setBusy(true); setErr(null);
    api.cases.events(c.case_id, 0, 50).then(
      page => { if (live) { setPages([page.data]); setCursor(page.cursor.has_more ? page.cursor.next_after : null); } },
      e => { if (live) setErr(e instanceof ApiError ? e : new ApiError(0, 'CLIENT_ERROR', String(e))); },
    ).finally(() => { if (live) setBusy(false); });
    return () => { live = false; };
  }, [c.case_id]);
  const loaded = pages.flat();
  const shown = loaded.filter(e => kind === 'all' || (kind === 'case' ? !e.evidence_id : !!e.evidence_id));
  return <div className={s.page}>
    <PageHead title='Events' desc={`The append-only record of ${c.case_number}: lifecycle changes and the chain of custody of its evidence. Entries cannot be edited or deleted.`} />
    <div className={s.listBar}><div className={s.seg} role='tablist' aria-label='Event type'>{(['all', 'case', 'evidence'] as const).map(k => <button key={k} role='tab' aria-selected={kind === k} onClick={() => setKind(k)}>{k === 'all' ? 'All' : k === 'case' ? 'Investigation' : 'Evidence custody'}</button>)}</div></div>
    {err && <ErrorState error={err} onRetry={cursor !== null ? more : undefined} />}
    {shown.length ? <section className={s.ledger}>{shown.map(e => <div key={e.event_id} className={s.eventWrap}><div className={s.event}>
      <i style={{ background: toneColor[eventTone(e.event_type)] }} />
      <span className={s.eventMain}><b>{eventLabel(e.event_type)}</b><small>#{e.sequence} · {utc(e.occurred_at)} · {e.actor}{eventDetail(e.event_type, e.payload) ? ` · ${eventDetail(e.event_type, e.payload)}` : ''}</small></span>
      {e.evidence_id ? <Link className={s.cap} href={paths.evidence(e.evidence_id, 'timeline')}>Evidence</Link> : <span className={s.cap}>Case</span>}
    </div></div>)}</section> : !busy && !err && <Empty title='No events of this kind' />}
    <div className={p.pager}><span>{loaded.length} loaded</span>{cursor !== null && <button className={`${s.btn} ${s.sm}`} onClick={more} disabled={busy}>{busy ? 'Loading…' : 'Load more'}</button>}</div>
  </div>;
}

/* ── tabs whose backend is not built yet ── */
const PENDING: Record<'analysis' | 'graph' | 'review' | 'report', { title: string; modules: string[]; step: string; body: string }> = {
  analysis: { title: 'Forensic analysis', modules: ['T-MIR'], step: 'plan Step 3', body: 'Runs and module results for this investigation.' },
  graph: { title: 'Evidence graph', modules: ['NEX-EGC'], step: 'plan Step 7', body: 'The graph is built from stored evidence, source records, lineage relationships, transformations and correlations. None of those modules exist yet, so there is no graph to draw; sample nodes are not shown.' },
  review: { title: 'Review and decisions', modules: ['NEX-INV'], step: 'plan Step 7', body: 'Investigators will accept, reject, mark inconclusive or request more evidence on each machine finding, with the decision kept separate from the finding. There are no findings to review until analysis exists.' },
  report: { title: 'Reports', modules: ['NEX-RPT'], step: 'plan Step 7', body: 'Versioned PDF and JSON reports, built from a frozen snapshot of evidence hashes, findings and reviews, arrive after review exists.' },
};

export function CasePending({ kind, branch }: { kind: keyof typeof PENDING; branch?: AnalysisBranch }) {
  const c = useLoadedCase();
  const d = PENDING[kind];
  return <div className={s.page}>
    <PageHead title={branch ? `${ANALYSIS_LABEL[branch]} analysis` : d.title} desc={branch ? `${c.case_number} · ${ANALYSIS_MODULE[branch]} results for each evidence item. Scores are each method's own measurement, not probabilities.` : `${c.case_number} · ${c.title}`} />
    {kind === 'analysis' && <nav className={`${s.seg} ${s.subTabs}`} aria-label='Analysis by media type' style={{ marginBottom: 20 }}>
      <Link href={paths.caseAnalysis(c.case_id)} aria-selected={!branch}>All</Link>
      {ANALYSIS_BRANCHES.map(b => <Link key={b} href={paths.caseAnalysis(c.case_id, b)} aria-selected={branch === b}>{ANALYSIS_LABEL[b]}</Link>)}
    </nav>}
    {kind === 'analysis' && !branch ? <CaseAnalysisPage caseId={c.case_id} archived={c.status === 'ARCHIVED'} />
      : kind === 'analysis' && branch ? <ModuleResultsPage caseId={c.case_id} moduleId={ANALYSIS_MODULE[branch]} />
      : <Unavailable title={branch ? `${ANALYSIS_LABEL[branch]} forensics (${ANALYSIS_MODULE[branch]})` : d.title} modules={branch ? [ANALYSIS_MODULE[branch]] : d.modules} step={d.step}><p>{d.body}</p></Unavailable>}
  </div>;
}
