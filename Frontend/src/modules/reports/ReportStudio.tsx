'use client';

import { useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, Check, ChevronDown, Download, FilePenLine, GripVertical, Eye } from 'lucide-react';
import { paths } from '@/config/routes';
import s from '@/styles/workspace.module.css';
import { useData } from '@/stores/workspace.store';
import { branchLabel } from '@/utils/labels';
import { Dot, FindingMark, PageHead, Thumb, fmt, type Ctx } from '@/components/ui';

/* ── Report studio: built from the active investigation ──
   Wide screens show the editor beside the paper. Phones and tablets switch between Edit and Preview, so editing
   starts on the first screen. Picking a section scrolls the paper to it and outlines it for a moment. */
const SECTIONS = [['cover', 'Cover', 'Title and case details'], ['key', 'Key assessment', 'The one-paragraph answer'], ['findings', 'Findings', 'Results and observations'], ['materials', 'Materials reviewed', 'Every source, hashed'], ['limits', 'Limitations', 'What the evidence cannot say'], ['custody', 'Chain of custody', 'Who handled what']] as const;
const LANG = { high: 'a high degree of confidence', moderate: 'moderate confidence', low: 'insufficient evidence to conclude' } as const;

export function Report({ caseId, notify, previewOnly = false }: Ctx & { previewOnly?: boolean }) {
  const { cases, evidence, findings } = useData();
  const c = cases.find(x => x.id === caseId)!;
  const ev = evidence.filter(e => e.caseId === caseId);
  const fs = findings.filter(f => ev.some(e => e.id === f.evidenceId) && f.status !== 'rejected');
  const [sec, setSec] = useState(2);
  const [mode, setMode] = useState<'edit' | 'preview'>('edit');
  const [flash, setFlash] = useState<string | null>(null);
  const [lang, setLang] = useState<keyof typeof LANG>(fs.some(f => f.severity === 'high') ? 'moderate' : 'high');
  const [cite, setCite] = useState<Set<string>>(new Set(ev.slice(0, 3).map(e => e.id)));
  const [incl, setIncl] = useState<Set<string>>(new Set(fs.map(f => f.id)));
  const paper = useRef<HTMLElement>(null);
  const verdict = fs.some(f => f.severity === 'high' && incl.has(f.id)) ? 'the video was manipulated in the regions and intervals listed below' : 'the material is consistent with its stated source';
  const cited = useMemo(() => ev.filter(e => cite.has(e.id)), [ev, cite]);
  const toggle = (set: (fn: (v: Set<string>) => Set<string>) => void, id: string) => set(v => { const n = new Set(v); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const jump = (i: number) => {
    setSec(i);
    const id = SECTIONS[i][0];
    if (matchMedia('(max-width: 1024px)').matches) setMode('preview');
    requestAnimationFrame(() => requestAnimationFrame(() => {
      paper.current?.querySelector(`[data-sec="${id}"]`)?.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'center' });
      setFlash(id); setTimeout(() => setFlash(null), 1400);
    }));
  };
  const at = (id: string) => ({ 'data-sec': id, className: flash === id ? s.secFlash : undefined });
  const paperNode = <article ref={paper} className={s.paper}>
        <div {...at('cover')}>
          <header>NEXTRON<span>Digital forensics report</span></header>
          <h1>Forensic analysis report</h1><h2>{c.name}</h2>
          <div className={s.paperMeta}><span>Case {c.id}</span><span>Analyst {c.analyst}</span><span>Draft</span></div>
        </div>
        <div {...at('key')}><div className={s.keyBox}><b>KEY ASSESSMENT</b><p>The evidence supports, with <em>{LANG[lang]}</em>, that {verdict}.</p></div></div>
        <section {...at('findings')}><h3>Findings</h3>
          <ul className={s.paperList}>{fs.filter(f => incl.has(f.id)).map(f => <li key={f.id}><b><i className={s.paperMark} data-sev={f.severity} aria-hidden='true' />{f.id}</b><span><strong style={{ fontWeight: 600 }}>{f.title}.</strong> {f.detail} <em style={{ fontStyle: 'normal', color: '#5a5248' }}>({branchLabel[f.branch]}, confidence {f.confidence.toFixed(2)}{f.startSec != null && f.endSec != null && f.endSec > f.startSec ? `, ${fmt(f.startSec)}–${fmt(f.endSec)}` : ''})</em></span></li>)}{!incl.size && <li><b>—</b><span>No findings included.</span></li>}</ul>
        </section>
        <section {...at('materials')}><h3>Materials reviewed</h3>
          <ul className={s.paperList}>{cited.map(e => <li key={e.id}><b>{e.id}</b><span>{e.fileName} · {e.source} · SHA-256 <span style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{e.sha256.slice(0, 20)}…</span></span></li>)}</ul>
          {cited.length > 0 && <><h3>Exhibits</h3>
            <div className={s.exhibits}>{cited.slice(0, 2).map(e => <figure key={e.id}><Thumb media={e.media} sizes='320px' /><figcaption>{e.id} · {e.capturedAt.slice(0, 16).replace('T', ' ')}</figcaption></figure>)}</div></>}
        </section>
        <section {...at('limits')}><h3>Limitations</h3>
          <p>Benchmarks for this system are not yet published. A missing analysis branch is treated as missing evidence, never as support for authenticity.</p>
        </section>
        <section {...at('custody')}><h3>Chain of custody</h3>
          <ul className={s.paperList}>{ev.map(e => <li key={e.id}><b>{e.id}</b><span>Received {e.capturedAt.slice(0, 10)} from {e.source}; held read-only; SHA-256 checked on every access.</span></li>)}</ul>
        </section>
  </article>;

  if (previewOnly) return <div className={s.page}>
    <PageHead title='Report preview' desc={`${c.name}. Read-only; edit it in the report studio.`}>
      <Link className={`${s.btn} ${s.ghost}`} href={paths.report(c.id)}><ArrowLeft size={15} />Edit report</Link>
      <button className={s.btn} onClick={() => window.print()}><Download size={15} />Export PDF</button>
    </PageHead>
    <div className={s.paperWrap}>{paperNode}</div>
  </div>;

  return <div className={s.page}>
    <PageHead title='Report studio' desc={`${c.name}. Every claim cites its source and states its confidence.`}>
      <div className={s.actGroup}>
        <button className={`${s.btn} ${s.ghost}`} onClick={() => { try { localStorage.setItem(`nx-report-${c.id}`, JSON.stringify({ lang, cite: [...cite], incl: [...incl] })); } catch {} notify('Draft saved in this browser'); }}>Save draft</button>
        <button className={s.btn} onClick={() => window.print()}><Download size={15} />Export PDF</button>
      </div>
      <button className={`${s.btn} ${s.primary}`} onClick={() => notify('Approval requested from S. Moran')}>Request approval</button>
    </PageHead>

    <div className={`${s.seg} ${s.modeSwitch}`} role='tablist' aria-label='Report mode'>
      <button role='tab' aria-selected={mode === 'edit'} onClick={() => setMode('edit')}><FilePenLine size={15} />Edit</button>
      <button role='tab' aria-selected={mode === 'preview'} onClick={() => setMode('preview')}><Eye size={15} />Preview</button>
    </div>

    <div className={s.reportGrid} data-mode={mode}>
      <div className={s.paperWrap}>{paperNode}</div>

      <div className={s.side}>
        <section className={s.panel} style={{ padding: 10 }}>
          <p className={s.title} style={{ padding: '8px 12px' }}>Structure</p>
          {SECTIONS.map(([, t, d], i) => <button key={t} className={s.section} aria-pressed={sec === i} onClick={() => jump(i)}><GripVertical size={14} /><span><b>{t}</b><small>{d}</small></span>{i === 4 ? <Dot tone='gold'>Draft</Dot> : <Check size={14} />}</button>)}
        </section>
        <section className={s.panel}>
          <label className={s.field}><span>Confidence language</span><select className={s.input} value={lang} onChange={e => setLang(e.target.value as keyof typeof LANG)}><option value='high'>High degree of confidence</option><option value='moderate'>Moderate confidence</option><option value='low'>Insufficient evidence</option></select></label>
          <details className={s.disclose} open>
            <summary><span><b>{incl.size} of {fs.length}</b> findings included</span><ChevronDown size={15} /></summary>
            {fs.map(f => <label key={f.id} className={s.check}><input type='checkbox' checked={incl.has(f.id)} onChange={() => toggle(setIncl, f.id)} /><FindingMark f={f} time={false} /><span>{f.title}</span></label>)}
          </details>
          <details className={s.disclose}>
            <summary><span><b>{cite.size} of {ev.length}</b> sources cited</span><ChevronDown size={15} /></summary>
            {ev.map(e => <label key={e.id} className={s.check}><input type='checkbox' checked={cite.has(e.id)} onChange={() => toggle(setCite, e.id)} /><span className={s.mono}>{e.fileName}</span></label>)}
          </details>
        </section>
      </div>
    </div>
  </div>;
}

