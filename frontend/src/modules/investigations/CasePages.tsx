'use client';

/* The case's own pages: overview, evidence, analysis (by media type), timeline, review and events.
   All of them read the shared store, so a decision taken on one shows on every other at once. */
import Link from 'next/link';
import Image from 'next/image';
import { useMemo } from 'react';
import { ArrowRight, Check, FileText, Plus, Share2, ShieldCheck } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import { useData } from '@/stores/workspace.store';
import type { Branch, Evidence, Finding } from '@/api';
import { BRANCHES, branchColor, branchLabel, findingStatusLabel, severityTone, statusLabel, statusTone, timeOf, toneColor } from '@/utils/labels';
import { Dot, FindingMark, PageHead, Thumb, focusPos, fmt, type Ctx } from '@/components/ui';
import { ANALYSIS, ANALYSIS_LABEL, paths, type AnalysisBranch } from '@/config/routes';

const useCase = (caseId: string) => {
  const { cases, evidence, findings, decisions, activity, audit } = useData();
  return useMemo(() => {
    const c = cases.find(x => x.id === caseId)!;
    const ev = evidence.filter(e => e.caseId === caseId);
    const ids = new Set(ev.map(e => e.id));
    const fs = findings.filter(f => ids.has(f.evidenceId));
    return { c, ev, fs, ds: decisions.filter(d => d.caseId === caseId), act: activity.filter(a => a.caseId === caseId), aud: audit.filter(a => a.text.includes(caseId) || ev.some(e => a.text.includes(e.id))) };
  }, [cases, evidence, findings, decisions, activity, audit, caseId]);
};
const evOf = (ev: Evidence[], f: Finding) => ev.find(e => e.id === f.evidenceId);

function FindingRow({ f, e, eager }: { f: Finding; e?: Evidence; eager?: boolean }) {
  return <li><Link className={s.fRow} href={`${paths.evidence(f.evidenceId)}?finding=${encodeURIComponent(f.id)}`}>
    {e && <Thumb media={e.media} sizes='96px' eager={eager} />}
    <span className={s.fRowMain}><FindingMark f={f} /><b>{f.title}</b><small>{f.detail}</small></span>
    <span className={s.fRowSide}><Dot tone={severityTone[f.severity]}>{branchLabel[f.branch]}</Dot><span className={s.mono}>{f.confidence.toFixed(2)}</span>{f.status !== 'open' && <span className={s.cap}>{findingStatusLabel[f.status]}</span>}</span>
  </Link></li>;
}

/* ── /investigations/:caseId ── */
export function CaseOverview({ caseId }: Ctx) {
  const { c, ev, fs, ds } = useCase(caseId);
  const open = fs.filter(f => f.status === 'open').sort((a, b) => b.confidence - a.confidence);
  return <div className={s.page}>
    <div className={s.overview}>
      <section className={s.ovLead}>
        <div className={s.ovMedia}><Image src={c.cover.still} alt={`Evidence still from ${c.name}`} fill preload sizes='(max-width: 900px) 100vw, 44vw' style={{ objectFit: 'cover', objectPosition: focusPos(c.cover) }} /></div>
        <div className={s.ovBody}>
          <p className={s.cap}>{c.summary}</p>
          <h1>{c.name}</h1>
          <p className={s.reason}>{c.reason}</p>
          <dl className={s.ovFacts}><div><dt>Analyst</dt><dd>{c.analyst}</dd></div><div><dt>Updated</dt><dd>{timeOf(c.updatedAt)}</dd></div><div><dt>Evidence</dt><dd>{ev.length} files</dd></div><div><dt>Legal hold</dt><dd>{c.legalHold ? 'Yes' : 'No'}</dd></div></dl>
          <div className={s.meterRow}>{BRANCHES.map(b => <span key={b}>{branchLabel[b]}<b>{c.readiness[b] == null ? '—' : `${c.readiness[b]}%`}</b><i><em style={{ transform: `scaleX(${(c.readiness[b] ?? 0) / 100})`, background: branchColor[b] }} /></i></span>)}</div>
          <div className={s.actions}>
            {ev[0] && <Link className={`${s.btn} ${s.primary}`} href={paths.evidence(ev[0].id)}>Open the workbench <ArrowRight size={15} /></Link>}
            <Link className={`${s.btn} ${s.ghost}`} href={paths.caseGraph(c.id)}><Share2 size={15} />Graph</Link>
            <Link className={`${s.btn} ${s.ghost}`} href={paths.caseReport(c.id)}><FileText size={15} />Report</Link>
          </div>
        </div>
      </section>
      <section className={s.ovSide}>
        <header className={s.secHead}><h2 className={s.title}>Waiting on a decision</h2><Link href={paths.caseReview(c.id)} className={s.secLink}>Review <ArrowRight size={13} /></Link></header>
        {ds.length ? <ul className={s.miniList}>{ds.map(d => <li key={d.id}><b>{d.title}</b><small>{d.rationale}</small></li>)}</ul> : <p className={s.cap}>Nothing is waiting.</p>}
      </section>
    </div>
    <section className={s.block}>
      <header className={s.secHead}><h2 className={s.title}>Open findings <span className={s.muted}>{open.length}</span></h2><Link href={paths.caseAnalysis(c.id)} className={s.secLink}>All analysis <ArrowRight size={13} /></Link></header>
      {open.length ? <ul className={s.fRows}>{open.slice(0, 4).map(f => <FindingRow key={f.id} f={f} e={evOf(ev, f)} />)}</ul> : <p className={s.cap}>No open findings.</p>}
    </section>
    <section className={s.block}>
      <header className={s.secHead}><h2 className={s.title}>Evidence <span className={s.muted}>{ev.length}</span></h2><Link href={paths.caseEvidence(c.id)} className={s.secLink}>All evidence <ArrowRight size={13} /></Link></header>
      <EvidenceGrid items={ev.slice(0, 6)} />
    </section>
  </div>;
}

export function EvidenceGrid({ items }: { items: Evidence[] }) {
  const { findings } = useData();
  return <ul className={s.evGrid}>{items.map((e, i) => {
    const n = findings.filter(f => f.evidenceId === e.id).length;
    return <li key={e.id}><Link className={s.evCard} href={paths.evidence(e.id)}>
      <Thumb media={e.media} sizes='(max-width: 640px) 50vw, 280px' eager={i < 8} />
      <span><b>{e.fileName}</b><small><Dot tone={statusTone[e.status]}>{statusLabel[e.status]}</Dot><span>{e.kind === 'video' ? fmt(e.durationSec) : e.kind}</span>{n > 0 && <span>{n} finding{n === 1 ? '' : 's'}</span>}</small></span>
    </Link></li>;
  })}</ul>;
}

/* ── /investigations/:caseId/evidence ── */
export function CaseEvidence({ caseId }: Ctx) {
  const { c, ev } = useCase(caseId);
  return <div className={s.page}>
    <PageHead title='Evidence' desc={`Every file in ${c.name}, as preserved at intake. Open one to examine it.`}>
      <Link className={`${s.btn} ${s.primary}`} href={paths.caseAddEvidence(c.id)}><Plus size={15} />Add evidence</Link>
    </PageHead>
    <EvidenceGrid items={ev} />
  </div>;
}

/* ── /investigations/:caseId/analysis[/image|video|audio|provenance] ── */
export function CaseAnalysis({ caseId, branch }: Ctx & { branch?: AnalysisBranch }) {
  const { c, ev, fs } = useCase(caseId);
  const b: Branch | undefined = branch ? ANALYSIS[branch] : undefined;
  const list = fs.filter(f => !b || f.branch === b).sort((x, y) => y.confidence - x.confidence);
  return <div className={s.page}>
    <PageHead title={branch ? `${ANALYSIS_LABEL[branch]} analysis` : 'Analysis'} desc={branch ? `${branchLabel[b!]} findings in ${c.name}, strongest first.` : `What each branch found in ${c.name}, strongest first.`} />
    <nav className={`${s.seg} ${s.subTabs}`} aria-label='Analysis by media type'>
      <Link href={paths.caseAnalysis(c.id)} aria-selected={!branch}>All<span className={s.count}>{fs.length}</span></Link>
      {(Object.keys(ANALYSIS) as AnalysisBranch[]).map(k => <Link key={k} href={paths.caseAnalysis(c.id, k)} aria-selected={branch === k}>{ANALYSIS_LABEL[k]}<span className={s.count}>{fs.filter(f => f.branch === ANALYSIS[k]).length}</span></Link>)}
    </nav>
    {list.length ? <ul className={s.fRows}>{list.map((f, i) => <FindingRow key={f.id} f={f} e={evOf(ev, f)} eager={i < 3} />)}</ul>
      : <div className={s.empty}><ShieldCheck size={24} /><b>Nothing found</b><span>This branch reported no anomalies for the files in this case.</span></div>}
  </div>;
}

/* ── /investigations/:caseId/timeline: what happened, in order ── */
export function CaseTimeline({ caseId }: Ctx) {
  const { c, ev, fs, act } = useCase(caseId);
  const items = [
    ...ev.map(e => ({ at: e.capturedAt, kind: 'capture', title: `${e.fileName} captured`, meta: `${e.source} · ${e.kind}`, href: paths.evidence(e.id), tone: 'steel' as const })),
    ...act.map(a => ({ at: a.at, kind: a.kind, title: a.text, meta: a.actor, href: undefined as string | undefined, tone: (a.kind === 'finding' ? 'alert' : a.kind === 'integrity' ? 'ok' : 'mute') as 'alert' | 'ok' | 'mute' })),
  ].sort((a, b) => a.at.localeCompare(b.at));
  const ranged = fs.filter(f => f.startSec != null && f.endSec != null && f.endSec > f.startSec);
  return <div className={s.page}>
    <PageHead title='Timeline' desc={`How ${c.name} unfolded: when each file was captured, and what the investigation did since.`} />
    <div className={s.tlPage}>
      <ol className={s.chron}>{items.map((it, i) => <li key={i} style={{ ['--c' as string]: toneColor[it.tone] }}>
        <time>{it.at.slice(0, 10)}<span>{it.at.slice(11, 16)} UTC</span></time>
        <div>{it.href ? <Link href={it.href}><b>{it.title}</b></Link> : <b>{it.title}</b>}<small>{it.meta}</small></div>
      </li>)}</ol>
      <aside className={s.quiet}>
        <p className={s.title}>Inside the files</p>
        <p className={s.cap} style={{ margin: '6px 0 12px' }}>Intervals the branches flagged, by offset into each file.</p>
        {ranged.length ? <ul className={s.miniList}>{ranged.map(f => <li key={f.id}><Link href={`${paths.evidence(f.evidenceId, 'timeline')}?finding=${encodeURIComponent(f.id)}`}><FindingMark f={f} /><b>{f.title}</b><small>{evOf(ev, f)?.fileName}</small></Link></li>)}</ul> : <p className={s.cap}>No time-bound findings.</p>}
      </aside>
    </div>
  </div>;
}

/* ── /investigations/:caseId/review: decide on what is open ── */
export function CaseReview({ caseId, notify }: Ctx) {
  const { setFindingStatus } = useData();
  const { c, ev, fs, ds } = useCase(caseId);
  const pending = fs.filter(f => f.status === 'open' || f.status === 'second_review');
  return <div className={s.page}>
    <PageHead title='Review' desc={`Findings in ${c.name} that still need an investigator’s decision. Inspect the frame before you decide.`} />
    {pending.length ? <ul className={s.reviewList}>{pending.map((f, i) => <li key={f.id}>
      <Link href={`${paths.evidence(f.evidenceId)}?finding=${encodeURIComponent(f.id)}`} className={s.reviewMedia} aria-label={`Inspect ${f.title}`}>{evOf(ev, f) && <Thumb media={evOf(ev, f)!.media} sizes='160px' eager={i < 5} />}</Link>
      <div className={s.reviewMain}><FindingMark f={f} /><b>{f.title}</b><p>{f.detail}</p><small>{branchLabel[f.branch]} · confidence {f.confidence.toFixed(2)} · most likely {f.explanations[0]?.label.toLowerCase()} ({Math.round((f.explanations[0]?.likelihood ?? 0) * 100)}%){f.status === 'second_review' ? ' · in second review' : ''}</small></div>
      <div className={s.actions}>
        <Link className={`${s.btn} ${s.primary}`} href={`${paths.evidence(f.evidenceId)}?finding=${encodeURIComponent(f.id)}`}>Inspect <ArrowRight size={14} /></Link>
        <button className={`${s.btn} ${s.ghost}`} onClick={() => { setFindingStatus(f.id, 'accepted'); notify(`Accepted · ${f.title}`); }}><Check size={14} />Accept</button>
        {f.status !== 'second_review' && <button className={`${s.btn} ${s.ghost}`} onClick={() => { setFindingStatus(f.id, 'second_review'); notify(`Sent for second review · ${f.title}`); }}>Second review</button>}
        <button className={`${s.btn} ${s.ghost}`} onClick={() => { setFindingStatus(f.id, 'rejected'); notify(`Rejected · ${f.title}`); }}>Reject</button>
      </div>
    </li>)}</ul> : <div className={s.empty}><ShieldCheck size={24} /><b>Everything is decided</b><span>New findings for this case land here first.</span></div>}
    {ds.length > 0 && <section className={s.block}><header className={s.secHead}><h2 className={s.title}>Other decisions</h2></header><ul className={s.miniList}>{ds.filter(d => !d.findingId).map(d => <li key={d.id}><b>{d.title}</b><small>{d.rationale}</small></li>)}</ul></section>}
  </div>;
}

/* ── /investigations/:caseId/events ── */
export function CaseEvents({ caseId }: Ctx) {
  const { c, act, aud } = useCase(caseId);
  const rows = [...act.map(a => ({ at: a.at, text: a.text, who: a.actor, kind: 'Activity', ok: true })), ...aud.map(a => ({ at: a.at, text: a.text, who: a.actor, kind: 'Audit', ok: a.verified }))].sort((a, b) => b.at.localeCompare(a.at));
  return <div className={s.page}>
    <PageHead title='Events' desc={`Everything recorded against ${c.name}: activity in the workspace and signed audit entries.`} />
    {rows.length ? <section className={s.ledger}>{rows.map((r, i) => <div key={i} className={s.eventWrap}><div className={s.event}><i style={{ background: r.ok ? 'var(--ok)' : 'var(--alert)' }} /><span className={s.eventMain}><b>{r.text}</b><small>{r.at.slice(0, 16).replace('T', ' ')} UTC · {r.kind} · {r.who}</small></span><span className={s.cap}>{r.kind}</span></div></div>)}</section>
      : <div className={s.empty}><b>No events yet</b></div>}
  </div>;
}
