'use client';

/* The investigation workspace: evidence · analysis canvas · findings.
   Panels resize by dragging their edges (double-click resets) and collapse with [ and ]; sizes persist.
   Per-frame motion (playhead, timecode, scrub preview, loupe, compare split) is written to transforms through
   refs, so scrubbing never re-renders React. Analysis runs go through the API job (./store useAnalysis). */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Image from 'next/image';
import { AnimatePresence, motion } from 'framer-motion';
import { Check, ChevronsLeftRight, Columns2, FileSearch, Film, ImageIcon, Link2, LoaderCircle, PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen, Pause, Play, Search, ShieldCheck, Sparkles, Waves, X, ZoomIn } from 'lucide-react';
import s from '@/styles/workspace.module.css';
import { useAnalysis, useData } from '@/stores/workspace.store';
import type { Evidence, Finding } from '@/api';
import { BRANCHES, branchColor, branchLabel, findingStatusLabel, severityTone, statusLabel, statusTone, toneColor, type Tool } from '@/utils/labels';
import { aspect, Dot, FindingMark, fmt, series, Thumb, usePreview, type Ctx } from '@/components/ui';

const ease = [.22, 1, .36, 1] as const;
const TOOLS: { id: Tool; label: string; key: string; icon: typeof Film }[] = [
  { id: 'viewer', label: 'Viewer', key: 'V', icon: Film }, { id: 'frames', label: 'Examine', key: 'E', icon: ImageIcon },
  { id: 'timeline', label: 'Timeline', key: 'T', icon: Waves }, { id: 'metadata', label: 'Metadata', key: 'M', icon: FileSearch },
];
const LS = 'nx-ws-panels';
const range = (f: Finding) => f.startSec != null && f.endSec != null && f.endSec > f.startSec;

type Props = Ctx & { tool: Tool; setTool: (t: Tool) => void; finding: string | null; setFinding: (f: string | null) => void; runId: number };

export default function Investigate({ go, notify, caseId, evidenceId, tool, setTool, finding, setFinding, runId }: Props) {
  const { cases, evidence, findings, setFindingStatus } = useData();
  const c = cases.find(x => x.id === caseId)!;
  const items = evidence.filter(e => e.caseId === caseId);
  const ev = evidence.find(x => x.id === evidenceId && x.caseId === caseId) ?? items[0];
  const evFindings = useMemo(() => findings.filter(f => f.evidenceId === ev.id), [findings, ev.id]);
  const sel = evFindings.find(f => f.id === finding) ?? null;
  const dur = ev.durationSec || 1;
  const ar = aspect(ev.media);
  const { bind, node: previewNode } = usePreview();

  /* ── panels ── */
  const [size, setSize] = useState({ l: 280, r: 360 });
  const [left, setLeft] = useState(true);
  const [right, setRight] = useState(true);
  const [drag, setDrag] = useState<'l' | 'r' | null>(null);
  useEffect(() => {
    try { const v = JSON.parse(localStorage.getItem(LS) || 'null'); if (v?.l) setSize(v); } catch {}
    if (matchMedia('(max-width: 1024px)').matches) { setLeft(false); setRight(false); }
  }, []);
  const startDrag = (side: 'l' | 'r') => (e: React.PointerEvent) => {
    e.preventDefault(); setDrag(side);
    const x0 = e.clientX, w0 = size[side];
    const move = (m: PointerEvent) => setSize(v => ({ ...v, [side]: Math.round(Math.max(220, Math.min(520, w0 + (side === 'l' ? m.clientX - x0 : x0 - m.clientX)))) }));
    const up = () => { setDrag(null); window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); setSize(v => { try { localStorage.setItem(LS, JSON.stringify(v)); } catch {} return v; }); };
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up);
  };
  // the same edges, from the keyboard: arrows move 16 px (Shift: 64), Home resets, Enter collapses
  const keyDrag = (side: 'l' | 'r') => (e: React.KeyboardEvent) => {
    const step = e.shiftKey ? 64 : 16, dir = side === 'l' ? 1 : -1;
    const set = (w: number) => setSize(v => { const n = { ...v, [side]: Math.max(220, Math.min(520, w)) }; try { localStorage.setItem(LS, JSON.stringify(n)); } catch {} return n; });
    if (e.key === 'ArrowRight') set(size[side] + step * dir);
    else if (e.key === 'ArrowLeft') set(size[side] - step * dir);
    else if (e.key === 'Home') set(side === 'l' ? 280 : 360);
    else if (e.key === 'Enter') (side === 'l' ? setLeft : setRight)(v => !v);
    else return;
    e.preventDefault();
  };
  const sepProps = (side: 'l' | 'r', label: string) => ({ role: 'separator', 'aria-orientation': 'vertical' as const, 'aria-label': label, 'aria-valuenow': size[side], 'aria-valuemin': 220, 'aria-valuemax': 520, tabIndex: 0, onKeyDown: keyDrag(side), title: 'Drag, or focus and use the arrow keys. Double-click to reset.' });

  /* ── analysis job ── */
  const onDone = useCallback((fs: Finding[]) => { notify(`Analysis complete · ${fs.length} finding${fs.length === 1 ? '' : 's'}`); }, [notify]);
  const { job, run, running } = useAnalysis(onDone);
  const seenRun = useRef(0);
  useEffect(() => { if (runId && runId !== seenRun.current) { seenRun.current = runId; setFinding(null); run(ev.id); } }, [runId, run, ev.id, setFinding]);
  const revealed = !running;

  /* ── clock, playhead, scrub preview ── */
  const t = useRef(0);
  const [playing, setPlaying] = useState(false);
  const r = { head: useRef<HTMLElement>(null), time: useRef<HTMLElement>(null), track: useRef<HTMLDivElement>(null), peek: useRef<HTMLDivElement>(null), peekImg: useRef<HTMLDivElement>(null), peekTxt: useRef<HTMLParagraphElement>(null) };
  const paint = useCallback(() => {
    const p = t.current / dur;
    if (r.head.current) r.head.current.style.transform = `translate3d(${(p * 100).toFixed(3)}%,0,0)`;
    if (r.time.current) r.time.current.textContent = `${fmt(t.current)} / ${fmt(dur)}`;
  }, [dur]); // eslint-disable-line react-hooks/exhaustive-deps
  const seek = useCallback((sec: number) => { t.current = Math.max(0, Math.min(dur - .01, sec)); paint(); }, [dur, paint]);
  useEffect(() => { setPlaying(false); seek(sel?.startSec ?? 0); }, [ev.id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (sel?.startSec != null) seek(sel.startSec); }, [sel, seek]);
  useEffect(() => {
    paint();
    if (!playing) return;
    let raf = 0, last = performance.now();
    const tick = (now: number) => { t.current = (t.current + (now - last) / 1000) % dur; last = now; paint(); raf = requestAnimationFrame(tick); };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, dur, paint, tool]);

  const scrubAt = (x: number) => { const b = r.track.current!.getBoundingClientRect(); return Math.max(0, Math.min(1, (x - b.left) / b.width)); };
  const peekAt = (x: number) => {
    const b = r.track.current!.getBoundingClientRect(); const p = scrubAt(x); const sec = p * dur;
    const hot = evFindings.find(f => range(f) && sec >= f.startSec! && sec <= f.endSec!);
    if (r.peek.current) { r.peek.current.style.opacity = '1'; r.peek.current.style.transform = `translate3d(${Math.max(84, Math.min(b.width - 84, p * b.width))}px,0,0)`; r.peek.current.classList.toggle(s.peekHot, !!hot); }
    if (r.peekImg.current) r.peekImg.current.style.backgroundPosition = `${30 + p * 40}% ${(ev.media.focus?.y ?? .5) * 100}%`;
    if (r.peekTxt.current) r.peekTxt.current.innerHTML = `<span>${fmt(sec)}</span>${hot ? `<b>${hot.id}</b>` : ''}`;
  };
  const onScrub = (e: React.PointerEvent) => {
    seek(scrubAt(e.clientX) * dur); peekAt(e.clientX);
    const move = (m: PointerEvent) => { seek(scrubAt(m.clientX) * dur); peekAt(m.clientX); };
    const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); };
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up);
  };

  /* ── compare split + loupe (transforms only) ── */
  const [compare, setCompare] = useState(true);
  const [overlay, setOverlay] = useState(true);
  const [strength, setStrength] = useState(85);
  const [loupe, setLoupe] = useState(true);
  const stage = useRef<HTMLDivElement>(null), so = useRef<HTMLDivElement>(null), si = useRef<HTMLDivElement>(null), sl = useRef<HTMLDivElement>(null), lp = useRef<HTMLDivElement>(null);
  const setSplit = (p: number) => {
    const v = `${(p * 100).toFixed(2)}%`;
    if (so.current) so.current.style.transform = `translate3d(${v},0,0)`;
    if (si.current) si.current.style.transform = `translate3d(-${v},0,0)`;
    if (sl.current) sl.current.style.transform = `translate3d(${v},0,0)`;
  };
  useEffect(() => { setSplit(.5); }, [tool, compare, ev.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const onStageMove = (e: React.PointerEvent) => {
    const b = stage.current!.getBoundingClientRect(), x = e.clientX - b.left, y = e.clientY - b.top;
    if (tool === 'viewer' && compare && e.buttons === 1) setSplit(Math.max(.02, Math.min(.98, x / b.width)));
    if (tool === 'frames' && loupe && lp.current) {
      lp.current.style.opacity = '1';
      lp.current.style.transform = `translate3d(${x}px,${y}px,0)`;
      lp.current.style.backgroundSize = `${b.width * 3}px ${b.height * 3}px`;
      lp.current.style.backgroundPosition = `${-(x * 3 - 75)}px ${-(y * 3 - 75)}px`;
    }
  };

  /* ── keyboard ── */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).closest('input, textarea, select, [role=dialog]') || e.metaKey || e.ctrlKey || e.altKey) return;
      const k = e.key.toLowerCase();
      if (k === '[') setLeft(v => !v); else if (k === ']') setRight(v => !v);
      else if (k === ' ' && ev.kind !== 'image') { e.preventDefault(); setPlaying(p => !p); }
      else if (k === 'c' && tool === 'viewer') setCompare(v => !v);
      else if (k === 'l' && tool === 'frames') setLoupe(v => !v);
      else { const hit = TOOLS.find(x => x.key.toLowerCase() === k); if (hit) setTool(hit.id); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [tool, setTool, ev.kind]);

  const Regions = () => <>{revealed && evFindings.filter(f => f.region).map(f => {
    const on = sel?.id === f.id;
    return <motion.button key={f.id} className={s.region} data-tone={severityTone[f.severity]} title={f.title} aria-label={`Region of ${f.title}`}
      onClick={e => { e.stopPropagation(); setFinding(on ? null : f.id); }} onPointerDown={e => e.stopPropagation()}
      style={{ left: `${f.region!.x}%`, top: `${f.region!.y}%`, width: `${f.region!.w}%`, height: `${f.region!.h}%`, pointerEvents: 'auto', background: 'none', padding: 0, zIndex: on ? 3 : 2, boxShadow: on ? '0 0 0 999px #00000066' : 'none', cursor: 'pointer' }}
      initial={{ opacity: 0, scale: 1.12 }} animate={{ opacity: sel && !on ? .3 : 1, scale: 1 }} transition={{ duration: .3, ease }}>{on && <span>{f.title}</span>}</motion.button>;
  })}</>;

  return <div className={`${s.ws} ${left ? s.wsLeftShow : s.wsLeftOff} ${right ? s.wsRightShow : s.wsRightOff}`} style={{ ['--l' as string]: `${size.l}px`, ['--r' as string]: `${size.r}px` }}>
    {/* ── left: evidence ── */}
    <aside className={s.pane} aria-label='Evidence'>
      <i className={s.grabber} aria-hidden='true' />
      <div className={s.paneHead}><div style={{ minWidth: 0 }}><b className={s.title} style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.name}</b><span className={s.cap}>{items.length} pieces of evidence</span></div><button className={s.iconBtn} onClick={() => setLeft(false)} aria-label='Collapse evidence panel'><PanelLeftClose size={16} /></button></div>
      <div className={s.paneBody}>
        <EvidenceNav items={items} active={ev.id} onPick={id => { go('investigate', { evidence: id, tool }); if (matchMedia('(max-width: 1024px)').matches) setLeft(false); }} bind={bind} />
        <div className={s.nav} style={{ paddingTop: 0 }}><button className={s.navMeta} onClick={() => go('graph', { caseId: c.id })}><Link2 size={15} />See how this evidence connects</button></div>
      </div>
    </aside>
    <div className={`${s.handle} ${drag === 'l' ? s.handleOn : ''}`} onPointerDown={startDrag('l')} onDoubleClick={() => setSize(v => ({ ...v, l: 280 }))} {...sepProps('l', 'Resize evidence panel')} />

    {/* ── centre: canvas ── */}
    <section className={s.center} aria-label='Analysis canvas'>
      <div className={s.toolbar}>
        {!left && <button className={`${s.btn} ${s.ghost} ${s.tbLeft}`} onClick={() => setLeft(true)} aria-label='Show evidence panel'><PanelLeftOpen size={16} /><span className={s.phoneOnly}>Evidence</span></button>}
        <p className={s.tbCtx}><b>{c.name}</b><span className={s.mono}>{ev.fileName}</span></p>
        <div className={`${s.seg} ${s.tbModes}`} role='tablist' aria-label='Tool'>{TOOLS.map(x => <button key={x.id} role='tab' aria-selected={tool === x.id} onClick={() => setTool(x.id)} title={`${x.label} · ${x.key}`}><x.icon size={14} />{x.label}</button>)}</div>
        <div className={s.tbAct}>
          {tool === 'viewer' && ev.media.overlay && <button className={`${s.btn} ${s.sm} ${s.toggle}`} aria-pressed={compare} onClick={() => setCompare(v => !v)}><Columns2 size={14} />Compare</button>}
          {tool === 'frames' && <>
            {ev.media.overlay && <button className={`${s.btn} ${s.sm} ${s.toggle}`} aria-pressed={overlay} onClick={() => setOverlay(v => !v)}><Waves size={14} />Error level</button>}
            <button className={`${s.btn} ${s.sm} ${s.toggle}`} aria-pressed={loupe} onClick={() => setLoupe(v => !v)}><ZoomIn size={14} />Loupe</button>
          </>}
        </div>
        <span className={s.grow} />
        <button className={`${s.btn} ${s.sm} ${s.primary} ${s.tbRun}`} onClick={() => { setFinding(null); run(ev.id); }} disabled={running}>{running ? <LoaderCircle size={14} className={s.spin} /> : <Sparkles size={14} />}{running ? 'Analyzing' : 'Run analysis'}</button>
        {!right && <button className={`${s.btn} ${s.ghost} ${s.tbRight}`} onClick={() => setRight(true)} aria-label={`Show findings panel, ${evFindings.length} findings`}><PanelRightOpen size={16} /><span className={s.phoneOnly}>Findings {revealed ? evFindings.length : ''}</span></button>}
      </div>

      <div className={s.canvas}>
        {(tool === 'viewer' || tool === 'frames') && <div ref={stage} className={s.stage} style={{ ['--ar' as string]: ar }} onPointerMove={onStageMove} onPointerDown={onStageMove} onPointerLeave={() => { if (lp.current) lp.current.style.opacity = '0'; }} onClick={() => setFinding(null)}>
          <Image src={ev.media.still} alt={`Frame from ${ev.fileName}`} fill preload sizes='(max-width: 1024px) 100vw, 60vw' style={{ objectFit: 'cover' }} />
          {tool === 'viewer' && compare && ev.media.overlay && <>
            <div ref={so} className={s.layer} aria-hidden='true'><div ref={si} className={s.layerIn}><Image src={ev.media.overlay} alt='' fill sizes='60vw' style={{ objectFit: 'cover' }} /></div></div>
            <div ref={sl} className={s.split} aria-hidden='true'><i /><b><ChevronsLeftRight size={16} /></b><span>Original</span><span>Error level</span></div>
          </>}
          {tool === 'frames' && overlay && ev.media.overlay && <Image src={ev.media.overlay} alt='' fill sizes='60vw' style={{ objectFit: 'cover', opacity: strength / 100, transition: 'opacity .2s' }} />}
          {tool === 'frames' && overlay && ev.media.overlay && <div className={s.elaLegend} onPointerDown={e => e.stopPropagation()} onClick={e => e.stopPropagation()}>
            <span>Error level</span><i aria-hidden='true' /><input className={s.range} type='range' min={0} max={100} value={strength} onChange={e => setStrength(+e.target.value)} aria-label='Error-level overlay strength' /><b className={s.mono}>{strength}%</b>
          </div>}
          {tool === 'frames' && loupe && <div ref={lp} className={s.loupe} style={{ opacity: 0, backgroundImage: `url(${overlay && ev.media.overlay ? ev.media.overlay : ev.media.still})`, left: 0, top: 0 }} aria-hidden='true' />}
          <Regions />
          {job && <motion.div style={{ position: 'absolute', inset: 0, zIndex: 6, background: 'linear-gradient(to bottom, transparent, #e9a23b22)', borderBottom: '2px solid #f6c26b', pointerEvents: 'none' }} initial={{ y: '-100%' }} animate={{ y: `${(job.progress - 1) * 100}%` }} transition={{ duration: .3, ease: 'linear' }} />}
        </div>}

        {tool === 'timeline' && <div className={s.tl}>
          {BRANCHES.map((b, i) => <div key={b} className={s.tlRow}><span>{branchLabel[b]}</span><div className={s.trace}>{series(72, i + ev.id.length).map((h, k) => <i key={k} style={{ ['--h' as string]: `${h}%`, ['--c' as string]: branchColor[b] }} />)}
            {revealed && evFindings.filter(f => f.branch === b && range(f)).map(f => <button key={f.id} className={`${s.tlMark} ${sel?.id === f.id ? s.tlMarkOn : ''}`} data-tone={severityTone[f.severity]} style={{ left: `${(f.startSec! / dur) * 100}%`, width: `${Math.max(1.2, ((f.endSec! - f.startSec!) / dur) * 100)}%` }} onClick={() => setFinding(f.id)} aria-label={`${f.id} ${f.title}`} />)}
          </div></div>)}
          <div className={s.tlAxis}>{[0, .25, .5, .75, 1].map(p => <span key={p}>{fmt(p * dur)}</span>)}</div>
          <div className={s.tlDetail}>
            <p className={s.cap}>{revealed ? `${evFindings.filter(range).length} flagged intervals` : 'Analyzing…'}</p>
            {revealed && evFindings.filter(range).map(f => <button key={f.id} className={`${s.tlItem} ${sel?.id === f.id ? s.tlItemOn : ''}`} onClick={() => setFinding(sel?.id === f.id ? null : f.id)} aria-pressed={sel?.id === f.id}>
              <Thumb media={ev.media} sizes='96px' />
              <span><FindingMark f={f} /><b>{f.title}</b><small>{branchLabel[f.branch]} · confidence {f.confidence.toFixed(2)}</small></span>
            </button>)}
          </div>
        </div>}

        {tool === 'metadata' && <div className={s.meta}>
          <h3 className={s.title}>{ev.fileName}</h3>
          <dl>{[{ key: 'SHA-256', value: ev.sha256 }, { key: 'Captured', value: ev.capturedAt.replace('T', ' ').replace('Z', ' UTC') }, { key: 'Source', value: ev.source }, { key: 'Codec', value: `${ev.codec} · ${ev.width} × ${ev.height}` }, ...ev.metadata].map(m =>
            <div key={m.key} className={`${s.metaRow} ${'conflict' in m && m.conflict ? s.metaConflict : ''}`} title={'note' in m ? m.note : undefined}><dt>{m.key}</dt><dd>{m.value}</dd>{'conflict' in m && m.conflict ? <Dot tone='alert'>Conflicts</Dot> : <span />}</div>)}</dl>
        </div>}
      </div>

      {ev.kind !== 'image' && tool !== 'metadata' && <div className={s.scrubArea}>
        <div className={s.controls}>
          <button className={s.iconBtn} onClick={() => setPlaying(p => !p)} aria-label={playing ? 'Pause' : 'Play'} style={{ background: 'var(--gold)', color: 'var(--gold-ink)' }}>{playing ? <Pause size={16} /> : <Play size={16} />}</button>
          <span ref={r.time} className={s.time} />
        </div>
        <div ref={r.track} className={s.track} onPointerDown={onScrub} onPointerMove={e => e.buttons === 0 && peekAt(e.clientX)} onPointerLeave={() => { if (r.peek.current) r.peek.current.style.opacity = '0'; }} role='slider' aria-label='Scrub through the clip' aria-valuemin={0} aria-valuemax={dur} aria-valuenow={0} tabIndex={0} onKeyDown={e => { if (e.key === 'ArrowRight') seek(t.current + 1); if (e.key === 'ArrowLeft') seek(t.current - 1); }}>
          <div className={s.frames} aria-hidden='true'>{Array.from({ length: 16 }, (_, i) => <span key={i} style={{ backgroundImage: `url(${ev.media.thumb})`, backgroundPosition: `${30 + (i / 15) * 40}% ${(ev.media.focus?.y ?? .5) * 100}%` }} />)}</div>
          {evFindings.filter(f => range(f) && f.endSec! - f.startSec! < dur * .9).map(f => <i key={f.id} className={`${s.mark} ${sel?.id === f.id ? s.markOn : ''}`} data-tone={severityTone[f.severity]} style={{ left: `${(f.startSec! / dur) * 100}%`, width: `${Math.max(.8, ((f.endSec! - f.startSec!) / dur) * 100)}%` }} />)}
          <i ref={r.head} className={s.head} />
          <div ref={r.peek} className={s.peek} style={{ opacity: 0, left: 0 }} aria-hidden='true'><div ref={r.peekImg} className={s.thumb} style={{ backgroundImage: `url(${ev.media.thumb})`, backgroundSize: 'cover' }} /><p ref={r.peekTxt} /></div>
        </div>
      </div>}

      {revealed && evFindings.length > 0 && <div className={s.fStrip} role='group' aria-label='Findings in this file'>
        {evFindings.map(f => <button key={f.id} aria-pressed={sel?.id === f.id} onClick={() => setFinding(sel?.id === f.id ? null : f.id)}><FindingMark f={f} time={false} /><span>{f.title}</span></button>)}
        {sel && <button className={s.fStripMore} onClick={() => setRight(true)}>Details and decision</button>}
      </div>}
    </section>

    <div className={`${s.handle} ${drag === 'r' ? s.handleOn : ''}`} onPointerDown={startDrag('r')} onDoubleClick={() => setSize(v => ({ ...v, r: 360 }))} {...sepProps('r', 'Resize findings panel')} />

    {/* ── right: findings ── */}
    <aside className={s.pane} aria-label='Findings'>
      <i className={s.grabber} aria-hidden='true' />
      <div className={s.paneHead}><b className={s.title}>Findings {revealed && <span className={s.muted} style={{ fontWeight: 400 }}>{evFindings.length}</span>}</b><button className={s.iconBtn} onClick={() => setRight(false)} aria-label='Collapse findings panel'><PanelRightClose size={16} /></button></div>
      <div className={s.paneBody}>
        {job ? <div className={s.analysis}>
          <p className={s.cap}>Analyzing <span className={s.mono}>{ev.fileName}</span></p>
          <i className={s.bar}><em style={{ transform: `scaleX(${job.progress})`, transition: 'transform .3s linear' }} /></i>
          <ol className={s.stageList}>{job.stages.map(st => <li key={st.key} data-s={st.state === 'done' ? 'done' : st.state === 'running' ? 'run' : 'wait'}><span>{st.state === 'done' ? <Check size={11} /> : st.state === 'running' ? <LoaderCircle size={11} className={s.spin} /> : null}</span>{st.label}</li>)}</ol>
        </div> : evFindings.length ? <ul className={s.fList}>{evFindings.map((f, i) => <motion.li key={f.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * .07, duration: .25, ease }}>
          <button className={`${s.finding} ${sel?.id === f.id ? s.fOn : ''}`} style={{ ['--c' as string]: toneColor[severityTone[f.severity]] }} onClick={() => setFinding(sel?.id === f.id ? null : f.id)} aria-pressed={sel?.id === f.id}>
            <i />
            <div>
              <FindingMark f={f} />
              <h3>{f.title}</h3>
              <p className={s.metaLine}><span>{branchLabel[f.branch]}</span><span className={s.mono}>{f.confidence.toFixed(2)}</span>{f.status !== 'open' && <span>{findingStatusLabel[f.status]}</span>}</p>
            </div>
          </button>
        </motion.li>)}</ul> : <div className={s.allClear} style={{ padding: 32 }}><ShieldCheck size={26} /><b style={{ color: 'var(--ink)' }}>No anomalies found</b><span>Every branch agrees this item matches its source.</span></div>}

        <AnimatePresence mode='wait'>{sel && revealed && <motion.div key={sel.id} className={s.inspect} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: .2, ease }}>
          <Inspector f={sel} ev={ev} onClose={() => setFinding(null)} onDecide={(status, label) => { setFindingStatus(sel.id, status); notify(`${label} · ${sel.title}`); }} />
        </motion.div>}</AnimatePresence>
      </div>
    </aside>
    {previewNode}
  </div>;
}

function EvidenceNav({ items, active, onPick, bind }: { items: Evidence[]; active: string; onPick: (id: string) => void; bind: ReturnType<typeof usePreview>['bind'] }) {
  const [q, setQ] = useState('');
  const list = items.filter(e => `${e.fileName} ${e.id} ${e.source}`.toLowerCase().includes(q.toLowerCase()));
  return <>
    {items.length > 4 && <label className={`${s.cmdk} ${s.navSearch}`} style={{ width: 'auto', cursor: 'text' }}><Search size={14} /><input value={q} onChange={e => setQ(e.target.value)} placeholder='Filter' aria-label='Filter evidence' style={{ flex: 1, minWidth: 0, border: 0, outline: 0, background: 'none', color: 'var(--ink)', font: 'inherit' }} /></label>}
    <div className={s.nav}>
      {list.map(e => <button key={e.id} className={`${s.navItem} ${e.id === active ? s.navOn : ''}`} onClick={() => onPick(e.id)} aria-current={e.id === active} {...bind(e.media, e.fileName, <span className={s.mono}>{e.id}</span>)}>
        <Thumb media={e.media} sizes='64px' />
        <span style={{ minWidth: 0 }}><b>{e.fileName}</b><small><Dot tone={statusTone[e.status]}>{statusLabel[e.status]}</Dot></small></span>
      </button>)}
      {!list.length && <p className={s.cap} style={{ padding: 10 }}>Nothing matches “{q}”.</p>}
    </div>
  </>;
}

function Inspector({ f, ev, onDecide, onClose }: { f: Finding; ev: Evidence; onDecide: (s: Finding['status'], label: string) => void; onClose: () => void }) {
  const [alt, setAlt] = useState(0);
  const ar = aspect(ev.media), boxAr = 16 / 9;
  const b = f.region ?? { x: 0, y: 0, w: 100, h: 100 };
  // size the still (in window units) so the region with margin fills a 16:9 window, then centre it
  const S = Math.min(6, Math.max(1, Math.min(100 / (b.w * 1.5), (100 / (b.h * 1.5)) * ar / boxAr)));
  const Hc = S * boxAr / ar, cx = (b.x + b.w / 2) / 100, cy = (b.y + b.h / 2) / 100;
  const left = Math.min(0, Math.max(1 - S, .5 - cx * S)) * 100, top = Math.min(0, Math.max(1 - Hc, .5 - cy * Hc)) * 100;
  return <>
    <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}><FindingMark f={f} /><Dot tone={severityTone[f.severity]}>{branchLabel[f.branch]}</Dot><button className={s.iconBtn} style={{ marginLeft: 'auto' }} onClick={onClose} aria-label='Close inspector'><X size={15} /></button></header>
    {f.region && <div className={s.thumb} style={{ aspectRatio: '16 / 9', borderRadius: 12 }}>
      <img src={ev.media.still} alt={`Region of ${f.title}`} style={{ position: 'absolute', width: `${S * 100}%`, height: `${Hc * 100}%`, left: `${left}%`, top: `${top}%`, maxWidth: 'none' }} />
    </div>}
    <div><h3 className={s.title} style={{ fontSize: 16 }}>{f.title}</h3><p style={{ marginTop: 8, color: 'var(--soft)', fontSize: 14 }}>{f.detail}</p></div>
    <p className={s.metaLine}><span>Confidence <b className={s.mono}>{f.confidence.toFixed(2)}</b></span>{range(f) && <span>At <b className={s.mono}>{fmt(f.startSec!)}</b></span>}<span>Model <b className={s.mono}>{f.model.name} {f.model.version}</b></span></p>
    <div><p className={s.cap} style={{ marginBottom: 8 }}>Most likely cause</p>
      <div className={s.chips}>{f.explanations.map((x, i) => <button key={x.label} aria-pressed={alt === i} onClick={() => setAlt(i)}>{x.label}<em>{Math.round(x.likelihood * 100)}%</em></button>)}</div>
    </div>
    <div className={s.actions}>
      <button className={`${s.btn} ${s.primary}`} onClick={() => onDecide('accepted', 'Finding accepted')}><Check size={14} />Accept</button>
      <button className={`${s.btn} ${s.ghost}`} onClick={() => onDecide('second_review', 'Sent for second review')}>Second review</button>
      <button className={`${s.btn} ${s.ghost}`} onClick={() => onDecide('rejected', 'Finding rejected')}>Reject</button>
    </div>
  </>;
}
