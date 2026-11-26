'use client';

import { useEffect, useMemo, useState } from 'react';
import Image from 'next/image';
import { AnimatePresence, motion } from 'framer-motion';
import { ArrowRight, Check, ChevronDown, MoreHorizontal, Share2, ShieldCheck, Upload, AlertTriangle, FileWarning, FileCheck2 } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import { useData } from '@/demo/stores/workspace.store';
import type { Decision, DecisionAction } from '@/demo/api';
import { CREDITS } from '@/demo/api/fixtures';
import { BRANCHES, branchColor, branchLabel, severityTone, statusLabel, statusTone, timeOf, toneColor, type Tone } from '@/demo/utils/labels';
import { aspect, coverBox, Dot, FindingMark, focusPos, PageHead, Thumb, useAspect, usePreview, type Ctx } from '@/demo/components/ui';

const ease = [.22, 1, .36, 1] as const;
const verb: Record<Decision['kind'], [DecisionAction, string, string]> = { accept_finding: ['accept', 'Accept', 'Accepted'], resolve_conflict: ['resolve', 'Resolve', 'Resolved'], approve_report: ['approve', 'Approve', 'Approved'] };
const kindLabel: Record<Decision['kind'], string> = { accept_finding: 'Finding', resolve_conflict: 'Conflict', approve_report: 'Report' };
const sevRank = { high: 0, medium: 1, low: 2, info: 3 } as const;

export default function Command({ go, notify }: Ctx) {
  const { cases, evidence, findings, decisions, activity, decide, restoreDecision } = useData();
  const ranked = useMemo(() => [...cases].sort((a, b) => b.priority - a.priority), [cases]);
  const [focusId, setFocusId] = useState(ranked[0]?.id);
  const [open, setOpen] = useState<string | null>(null);
  const [all, setAll] = useState(false);
  const [menu, setMenu] = useState<string | null>(null);
  const { bind, node: previewNode } = usePreview();
  const [media, mediaAr] = useAspect<HTMLDivElement>();
  useEffect(() => { const close = () => setMenu(null); window.addEventListener('pointerdown', close); return () => window.removeEventListener('pointerdown', close); }, []);

  const f = cases.find(c => c.id === focusId) ?? ranked[0];
  const fTop = findings.filter(x => x.region && evidence.some(e => e.caseId === f.id && e.id === x.evidenceId)).sort((a, b) => b.confidence - a.confidence)[0];
  const next = ranked[(ranked.findIndex(c => c.id === f.id) + 1) % ranked.length];
  const queue = [...decisions].sort((a, b) => sevRank[a.severity] - sevRank[b.severity]);
  const shown = all ? queue : queue.slice(0, 3);

  const act = (d: Decision, action: DecisionAction, label: string) => { decide(d.id, action); setMenu(null); notify(`${label}: ${d.title}`, () => restoreDecision(d)); };
  // look before you decide: the first action always opens the evidence behind the decision
  const inspect = (d: Decision) => {
    setMenu(null);
    const x = findings.find(y => y.id === d.findingId);
    if (x) return go('investigate', { evidence: x.evidenceId, finding: x.id });
    if (d.kind === 'approve_report') return go('report', { caseId: d.caseId });
    const e = evidence.find(y => y.caseId === d.caseId && y.metadata.some(m => m.conflict));
    go('investigate', e ? { evidence: e.id, tool: 'metadata' } : { caseId: d.caseId });
  };
  const highs = findings.filter(x => x.severity === 'high' && x.status === 'open').length;
  const conflicts = evidence.filter(e => e.metadata.some(m => m.conflict)).length;

  return <div className={`${s.page} ${s.cmdPage}`}>
    <PageHead title='Dashboard' desc={<span className={s.greet}>
      <button className={s.pill} onClick={() => document.getElementById('decisions')?.scrollIntoView({ behavior: 'smooth', block: 'center' })}><AlertTriangle size={14} style={{ color: 'var(--alert)' }} /><b>{decisions.length}</b> decisions<span className={s.hideSm}> waiting</span></button>
      <button className={s.pill} onClick={() => { const x = findings.find(y => y.severity === 'high' && y.status === 'open'); if (x) go('investigate', { evidence: x.evidenceId, finding: x.id }); }}><b>{highs}</b> high<span className={s.hideSm}>-severity</span> findings</button>
      <button className={s.pill} onClick={() => { const e = evidence.find(y => y.metadata.some(m => m.conflict)); if (e) go('investigate', { evidence: e.id, tool: 'metadata' }); }}><FileWarning size={14} style={{ color: 'var(--steel)' }} /><b>{conflicts}</b> <span className={s.hideSm}>metadata </span>conflicts</button>
    </span>}>
      <button className={`${s.btn} ${s.hideSm}`} onClick={() => go('intake')}><Upload size={15} />Scan evidence</button>
    </PageHead>

    <div className={s.bento}>
      {/* one focal point: the most urgent investigation and what blocks it */}
      <section className={`${s.tile} ${s.focus}`} aria-label='Priority investigation'>
        <div ref={media} className={s.focusMedia}>
          <AnimatePresence mode='popLayout' initial={false}>
            <motion.div key={f.id} style={{ position: 'absolute', inset: 0 }} initial={{ opacity: 0, scale: 1.03 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }} transition={{ duration: .4, ease }}>
              <Image src={f.cover.still} alt={`Evidence still from ${f.name}`} fill preload sizes='(max-width: 760px) 100vw, 34vw' style={{ objectFit: 'cover', objectPosition: focusPos(f.cover) }} />
              {fTop?.region && (() => { const m = evidence.find(e => e.id === fTop.evidenceId)!.media; const b = coverBox(fTop.region, aspect(m), mediaAr, m.focus?.x ?? .5, m.focus?.y ?? .5); return <motion.div className={s.region} data-tone={severityTone[fTop.severity]} style={{ left: `${b.x}%`, top: `${b.y}%`, width: `${b.w}%`, height: `${b.h}%` }} initial={{ opacity: 0, scale: 1.15 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: .25, duration: .45, ease }}><span>{fTop.id} · {fTop.confidence.toFixed(2)}</span></motion.div>; })()}
            </motion.div>
          </AnimatePresence>
        </div>
        <motion.div key={f.id} className={s.focusBody} initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: .3, ease }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}><Dot tone={statusTone[f.status]}>{statusLabel[f.status]}</Dot><span className={`${s.mono} ${s.muted}`}>{f.id}</span>{f.legalHold && <span className={s.cap}>Legal hold</span>}</div>
          <div><h2>{f.name}</h2><p className={s.reason} style={{ marginTop: 10 }}>{f.reason}</p></div>
          <details className={s.meter}>
            <summary>{(() => { const w = BRANCHES.filter(b => f.readiness[b] != null).sort((a, b) => f.readiness[a]! - f.readiness[b]!)[0]; return w ? <span><b style={{ color: branchColor[w] }}>{branchLabel[w]}</b> needs the most work · {f.readiness[w]}% ready</span> : <span>Readiness not reported</span>; })()}<ChevronDown size={15} /></summary>
            <div className={s.meterRow}>{BRANCHES.map(b => <span key={b}>{branchLabel[b]}<b>{f.readiness[b] == null ? '—' : `${f.readiness[b]}%`}</b><i><em style={{ transform: `scaleX(${(f.readiness[b] ?? 0) / 100})`, background: branchColor[b] }} /></i></span>)}</div>
          </details>
          <div className={s.actions}>
            <button className={`${s.btn} ${s.primary}`} style={{ height: 40, padding: '0 18px' }} onClick={() => go('investigate', { caseId: f.id, finding: fTop?.id })}>Resume investigation <ArrowRight size={15} /></button>
            <button className={`${s.btn} ${s.ghost} ${s.hideSm}`} style={{ height: 40 }} onClick={() => go('graph', { caseId: f.id })}><Share2 size={15} />Evidence graph</button>
          </div>
          {next && next.id !== f.id && <p className={s.next}>Up next <button onClick={() => setFocusId(next.id)} {...bind(next.cover, next.name, <span className={s.mono}>{next.id}</span>)}><Thumb media={next.cover} sizes='22px' />{next.name}<ArrowRight size={13} /></button></p>}
        </motion.div>
      </section>

      {/* decisions: three at a time, one clear action each */}
      <section id='decisions' className={`${s.tile} ${s.decisions}`} aria-label='Decisions waiting'>
        <header className={s.tileHead}><h2 className={s.title}>Needs your decision</h2><span className={s.cap}>{queue.length} open</span></header>
        {queue.length ? <motion.ul className={s.decList} layout>
          <AnimatePresence initial={false}>{shown.map(d => <motion.li key={d.id} layout className={s.decision} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, x: 24, transition: { duration: .18 } }} transition={{ duration: .22, ease }}>
            <div style={{ minWidth: 0 }}>{(() => { const x = findings.find(y => y.id === d.findingId); return x ? <FindingMark f={x} /> : null; })()}<h3>{d.title}</h3><p><Dot tone={severityTone[d.severity] as Tone}>{kindLabel[d.kind]}</Dot><span className={s.mono}>{d.caseId}</span></p></div>
            <footer>
              <button className={`${s.btn} ${s.sm} ${s.primary}`} onClick={() => inspect(d)}>{d.kind === 'approve_report' ? 'Review report' : 'Inspect'}<ArrowRight size={13} /></button>
              <span className={s.more} onPointerDown={e => e.stopPropagation()}>
                <button className={s.iconBtn} style={{ width: 30, height: 30 }} onClick={() => setMenu(menu === d.id ? null : d.id)} aria-label={`More actions for ${d.title}`} aria-expanded={menu === d.id}><MoreHorizontal size={16} /></button>
                <AnimatePresence>{menu === d.id && <motion.div className={s.menu} role='menu' initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: .14 }}>
                  <button role='menuitem' onClick={() => act(d, 'escalate', 'Escalated')}>Escalate</button>
                  <button role='menuitem' onClick={() => act(d, 'dismiss', 'Dismissed')}>Dismiss</button>
                  <hr />
                  <button role='menuitem' className={s.menuQuiet} onClick={() => act(d, verb[d.kind][0], verb[d.kind][2])}><Check size={13} />{verb[d.kind][1]} without inspecting</button>
                </motion.div>}</AnimatePresence>
              </span>
            </footer>
          </motion.li>)}</AnimatePresence>
        </motion.ul> : <div className={s.allClear}><ShieldCheck size={28} /><b style={{ color: 'var(--ink)' }}>Nothing waiting</b><span>New findings land here first.</span></div>}
        {queue.length > 3 && <button className={`${s.btn} ${s.ghost} ${s.sm}`} style={{ margin: '0 24px 20px', alignSelf: 'flex-start' }} onClick={() => setAll(v => !v)}>{all ? 'Show fewer' : `Show all ${queue.length}`}</button>}
      </section>

      {/* investigations: quiet rows, detail on demand */}
      <section className={`${s.tile} ${s.cases}`} aria-label='Investigations'>
        <header className={s.tileHead}><h2 className={s.title}>Investigations</h2><span className={s.cap}>{cases.length} cases</span></header>
        <ul className={s.rows}>{ranked.map(c => {
          const ev = evidence.filter(e => e.caseId === c.id);
          const isOpen = open === c.id;
          return <li key={c.id} className={`${s.row} ${isOpen ? s.rowOpen : ''}`}>
            <button className={s.rowMain} onClick={() => setOpen(isOpen ? null : c.id)} onDoubleClick={() => go('case', { caseId: c.id })} aria-expanded={isOpen} {...bind(c.cover, c.name, <span className={s.mono}>{timeOf(c.updatedAt)}</span>)}>
              <Thumb media={c.cover} sizes='72px' />
              <span className={s.rowName}><b>{c.name}</b><small><span className={s.mono}>{c.id}</span> · {c.analyst}</small><span className={s.rowStatusSm}><Dot tone={statusTone[c.status]}>{statusLabel[c.status]}</Dot></span></span>
              <Dot tone={statusTone[c.status]}>{statusLabel[c.status]}</Dot>
              <span className={s.rowTime}>{timeOf(c.updatedAt)}</span>
              <ChevronDown size={16} className={s.rowChev} />
            </button>
            <AnimatePresence initial={false}>{isOpen && <motion.div className={s.rowMore} initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: .24, ease }}>
              <div className={s.rowMoreIn}>
                <div>
                  <p>{c.summary}. {c.reason}</p>
                  <div className={s.strip}>{ev.map(e => <button key={e.id} style={{ border: 0, padding: 0, background: 'none', borderRadius: 8 }} onClick={() => go('investigate', { evidence: e.id })} {...bind(e.media, e.fileName, <span className={s.mono}>{e.id}</span>)} aria-label={`Open ${e.fileName}`}><Thumb media={e.media} sizes='64px' style={{ boxShadow: `inset 0 0 0 1.5px ${toneColor[statusTone[e.status]]}55` }} /></button>)}</div>
                </div>
                <div className={s.actions}>
                  <button className={`${s.btn} ${s.sm} ${s.ghost}`} onClick={() => go('report', { caseId: c.id })}><FileCheck2 size={14} />Report</button>
                  <button className={`${s.btn} ${s.sm} ${s.primary}`} onClick={() => go('case', { caseId: c.id })}>Open <ArrowRight size={13} /></button>
                </div>
              </div>
            </motion.div>}</AnimatePresence>
          </li>;
        })}</ul>
      </section>

      <section className={`${s.tile} ${s.activity}`} aria-label='Activity'>
        <header className={s.tileHead}><h2 className={s.title}>Activity</h2><span className={s.cap}>Signed</span></header>
        <ol className={s.feed}>{activity.slice(0, 4).map(a => <li key={a.id} style={{ color: toneColor[({ finding: 'alert', status: 'steel', integrity: 'ok', analysis: 'mute' } as const)[a.kind]] }}><time>{timeOf(a.at)}</time><p>{a.text}<small><span className={s.mono}>{a.caseId}</span> · {a.actor}</small></p></li>)}</ol>
      </section>

      <p className={s.credits}>{CREDITS}</p>
    </div>
    {previewNode}
  </div>;
}
