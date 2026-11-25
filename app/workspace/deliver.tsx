'use client';

import { useMemo, useState } from 'react';
import { Check, Download, Eye, GripVertical, ShieldCheck } from 'lucide-react';
import s from './workspace.module.css';
import { useData } from './store';
import type { AuditEvent } from './api';
import { branchLabel, severityTone, toneColor } from './data';
import { Dot, PageHead, Thumb, fmt, type Ctx } from './ui';

/* ── Report studio: built from the active investigation ── */
const SECTIONS = [['Cover', 'Title and case details'], ['Key assessment', 'The one-paragraph answer'], ['Materials reviewed', 'Every source, hashed'], ['Findings', 'Results and observations'], ['Limitations', 'What the evidence cannot say'], ['Chain of custody', 'Who handled what']];
const LANG = { high: 'a high degree of confidence', moderate: 'moderate confidence', low: 'insufficient evidence to conclude' } as const;

export function Report({ caseId, notify }: Ctx) {
  const { cases, evidence, findings } = useData();
  const c = cases.find(x => x.id === caseId)!;
  const ev = evidence.filter(e => e.caseId === caseId);
  const fs = findings.filter(f => ev.some(e => e.id === f.evidenceId) && f.status !== 'rejected');
  const [sec, setSec] = useState(3);
  const [lang, setLang] = useState<keyof typeof LANG>(fs.some(f => f.severity === 'high') ? 'moderate' : 'high');
  const [cite, setCite] = useState<Set<string>>(new Set(ev.slice(0, 3).map(e => e.id)));
  const [incl, setIncl] = useState<Set<string>>(new Set(fs.map(f => f.id)));
  const verdict = fs.some(f => f.severity === 'high' && incl.has(f.id)) ? 'the video was manipulated in the regions and intervals listed below' : 'the material is consistent with its stated source';
  const cited = useMemo(() => ev.filter(e => cite.has(e.id)), [ev, cite]);
  const toggle = (set: (fn: (v: Set<string>) => Set<string>) => void, id: string) => set(v => { const n = new Set(v); if (n.has(id)) n.delete(id); else n.add(id); return n; });

  return <div className={s.page}>
    <PageHead title='Report studio' desc={`${c.name}. Every claim cites its source and states its confidence.`}>
      <button className={`${s.btn} ${s.ghost}`} onClick={() => notify('Draft saved')}>Save draft</button>
      <button className={`${s.btn} ${s.ghost}`} onClick={() => notify('Preview opened')}><Eye size={15} />Preview</button>
      <button className={`${s.btn} ${s.primary}`} onClick={() => notify('Approval requested from S. Moran')}>Request approval</button>
    </PageHead>
    <div className={s.reportGrid}>
      <div className={s.paperWrap}><article className={s.paper}>
        <header>NEXTRON<span>Digital forensics report</span></header>
        <h1>Forensic analysis report</h1><h2>{c.name}</h2>
        <div className={s.paperMeta}><span>Case {c.id}</span><span>Analyst {c.analyst}</span><span>Draft</span></div>
        <div className={s.keyBox}><b>KEY ASSESSMENT</b><p>The evidence supports, with <em>{LANG[lang]}</em>, that {verdict}.</p></div>
        <h3>Findings</h3>
        <ul className={s.paperList}>{fs.filter(f => incl.has(f.id)).map(f => <li key={f.id}><b>{f.id}</b><span><strong style={{ fontWeight: 600 }}>{f.title}.</strong> {f.detail} <em style={{ fontStyle: 'normal', color: '#5a5248' }}>({branchLabel[f.branch]}, confidence {f.confidence.toFixed(2)}{f.startSec != null && f.endSec != null && f.endSec > f.startSec ? `, ${fmt(f.startSec)}–${fmt(f.endSec)}` : ''})</em></span></li>)}{!incl.size && <li><b>—</b><span>No findings included.</span></li>}</ul>
        <h3>Materials reviewed</h3>
        <ul className={s.paperList}>{cited.map(e => <li key={e.id}><b>{e.id}</b><span>{e.fileName} · {e.source} · SHA-256 <span style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>{e.sha256.slice(0, 20)}…</span></span></li>)}</ul>
        {cited.length > 0 && <><h3>Exhibits</h3>
          <div className={s.exhibits}>{cited.slice(0, 2).map(e => <figure key={e.id}><Thumb media={e.media} sizes='320px' /><figcaption>{e.id} · {e.capturedAt.slice(0, 16).replace('T', ' ')}</figcaption></figure>)}</div></>}
        <h3>Limitations</h3>
        <p>Benchmarks for this system are not yet published. A missing analysis branch is treated as missing evidence, never as support for authenticity.</p>
      </article></div>
      <div className={s.side}>
        <section className={s.panel} style={{ padding: 10 }}>
          <p className={s.title} style={{ padding: '8px 12px' }}>Structure</p>
          {SECTIONS.map(([t, d], i) => <button key={t} className={s.section} aria-pressed={sec === i} onClick={() => setSec(i)}><GripVertical size={14} /><span><b>{t}</b><small>{d}</small></span>{i === 4 ? <Dot tone='gold'>Draft</Dot> : <Check size={14} />}</button>)}
        </section>
        <section className={s.panel}>
          <p className={s.title}>Include</p>
          {fs.map(f => <label key={f.id} className={s.check}><input type='checkbox' checked={incl.has(f.id)} onChange={() => toggle(setIncl, f.id)} /><span style={{ color: toneColor[severityTone[f.severity]], fontFamily: 'var(--mono)', fontSize: 12 }}>{f.id}</span>{f.title}</label>)}
          <p className={s.title} style={{ marginTop: 8 }}>Cite</p>
          {ev.map(e => <label key={e.id} className={s.check}><input type='checkbox' checked={cite.has(e.id)} onChange={() => toggle(setCite, e.id)} />{e.fileName}</label>)}
          <label className={s.field} style={{ marginTop: 8 }}><span>Confidence language</span><select className={s.input} value={lang} onChange={e => setLang(e.target.value as keyof typeof LANG)}><option value='high'>High degree of confidence</option><option value='moderate'>Moderate confidence</option><option value='low'>Insufficient evidence</option></select></label>
          <button className={s.btn} onClick={() => notify('Report exported as PDF')}><Download size={15} />Export PDF</button>
        </section>
      </div>
    </div>
  </div>;
}

/* ── Governance and audit ── */
const KIND_LABEL: Record<AuditEvent['kind'], string> = { evidence_access: 'Evidence access', analysis: 'Analysis', model_change: 'Model change', access_control: 'Access control', export: 'Export', retention: 'Retention' };
const KINDS = Object.keys(KIND_LABEL) as AuditEvent['kind'][];

export function Audit({ notify }: Ctx) {
  const { audit, models } = useData();
  const [on, setOn] = useState<Set<string>>(new Set(KINDS));
  const rows = audit.filter(e => on.has(e.kind));
  return <div className={s.page}>
    <PageHead title='Governance and audit' desc='An append-only, signed record of who touched which evidence and when, and which models may produce findings.'>
      <button className={`${s.btn} ${s.ghost}`} onClick={() => notify('Audit log exported')}><Download size={15} />Export log</button>
    </PageHead>
    <div className={s.audit}>
      <section className={s.panel}>
        <p className={s.title}>Event types</p>
        {KINDS.map(k => <label key={k} className={s.check}><input type='checkbox' checked={on.has(k)} onChange={() => setOn(v => { const n = new Set(v); if (n.has(k)) n.delete(k); else n.add(k); return n; })} />{KIND_LABEL[k]}<b className={s.muted}>{audit.filter(e => e.kind === k).length}</b></label>)}
      </section>
      <section className={s.panel} style={{ padding: 10 }}>
        <p className={s.title} style={{ padding: '8px 10px' }}>Ledger <span className={s.muted} style={{ fontWeight: 400 }}>{rows.length} events</span></p>
        {rows.length ? rows.map(e => <div key={e.seq} className={s.event}><i style={{ background: e.verified ? 'var(--ok)' : 'var(--alert)' }} /><div><b>{e.text}</b><small>{e.at.slice(0, 16).replace('T', ' ')} UTC · {KIND_LABEL[e.kind]}</small></div><span className={s.muted}>{e.actor}</span><Dot tone={e.verified ? 'ok' : 'alert'}>{e.verified ? 'Verified' : 'Revoked'}</Dot></div>)
          : <p className={s.cap} style={{ padding: 18 }}>No events for these filters.</p>}
      </section>
      <div className={s.side}>
        <section className={s.panel}><p className={s.title}>Approved models</p>
          <dl className={s.kv}>{models.map(m => <div key={m.name}><dt className={s.mono}>{m.name} {m.version}</dt><dd><Dot tone={m.status === 'deployed' ? 'ok' : 'steel'}>{m.status === 'deployed' ? 'Deployed' : m.status === 'approved' ? 'Approved' : 'Retired'}</Dot></dd></div>)}</dl>
        </section>
        <section className={s.panel}><p className={s.title}>Retention</p>
          <dl className={s.kv}><div><dt>Policy</dt><dd>RP-03 · 7 years</dd></div><div><dt>Legal hold</dt><dd><Dot tone='gold'>Active</Dot></dd></div></dl>
        </section>
      </div>
    </div>
    <div className={s.health}><ShieldCheck size={26} />{[['Chain of custody', 'Intact'], ['Signatures', `${Math.round(audit.filter(e => e.verified).length / Math.max(1, audit.length) * 100)}% verified`], ['Hash checks', 'Consistent'], ['Tamper events', 'None']].map(([k, v]) => <div key={k}><span className={s.cap}>{k}</span><b>{v}</b></div>)}</div>
  </div>;
}
