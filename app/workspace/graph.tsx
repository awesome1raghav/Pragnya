'use client';

/* Evidence relationship graph — NEXTRON's signature view.
   Physics: nodes repel (Coulomb, k/d²), links are springs toward a rest length set by their kind, a weak gravity
   keeps the field centred, and velocity is damped; the system cools (alpha) and sleeps when settled, re-heating
   when you drag or open a cluster. Positions live in a ref and are written to the SVG directly. */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Image from 'next/image';
import { AnimatePresence, motion } from 'framer-motion';
import { ArrowRight, Focus, Info, RotateCcw, Search, X } from 'lucide-react';
import s from './workspace.module.css';
import { useData } from './store';
import { api, type Assessment, type EdgeKind, type GraphNode } from './api';
import { edgeStyle, nodeTone, toneColor } from './data';
import { Dot, type Ctx } from './ui';

type P = { x: number; y: number; vx: number; vy: number; pin?: boolean };
const R: Record<GraphNode['kind'], number> = { case: 28, media: 22, finding: 11, metadata: 12, source: 14 };
const REST: Record<EdgeKind, number> = { contains: 110, pattern: 210, timestamp: 200, metadata: 170, derived: 160 };
const toneWord = { alert: 'Suspicious', steel: 'In review', ok: 'Verified', gold: 'Conflict', mute: 'Context', ink: 'Active' } as const;

export default function Graph({ go, caseId }: Ctx) {
  const { graph, evidence, findings } = useData();
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set(graph.nodes.filter(n => n.kind === 'case' && n.id !== caseId).slice(-1).map(n => n.id)));
  const [kinds, setKinds] = useState<Set<EdgeKind>>(new Set(Object.keys(edgeStyle) as EdgeKind[]));
  const [sel, setSel] = useState<string | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const [q, setQ] = useState('');
  const [legend, setLegend] = useState(false);
  const [showOut, setShowOut] = useState(false);
  const [assess, setAssess] = useState<Assessment | null>(null);
  useEffect(() => { api.getAssessment(caseId).then(setAssess).catch(() => {}); }, [caseId]);

  const visible = useMemo(() => graph.nodes.filter(n => !(n.cluster && collapsed.has(n.cluster) && n.kind !== 'case')), [graph.nodes, collapsed]);
  const vis = useMemo(() => new Set(visible.map(n => n.id)), [visible]);
  const links = useMemo(() => graph.edges.filter(e => vis.has(e.from) && vis.has(e.to) && kinds.has(e.kind)), [graph.edges, vis, kinds]);
  const near = useMemo(() => { const id = hover ?? sel; if (!id) return null; const n = new Set([id]); graph.edges.forEach(e => { if (e.from === id) n.add(e.to); if (e.to === id) n.add(e.from); }); return n; }, [hover, sel, graph.edges]);
  const match = q.trim().toLowerCase();

  /* ── simulation ── */
  const pos = useRef<Map<string, P>>(new Map());
  const alpha = useRef(1);
  const view = useRef({ k: 1, x: 0, y: 0 });
  const svg = useRef<SVGSVGElement>(null), root = useRef<SVGGElement>(null);
  const nodeEls = useRef<Map<string, SVGGElement>>(new Map()), edgeEls = useRef<Map<string, SVGPathElement>>(new Map());
  const live = useRef({ visible, links }); live.current = { visible, links };
  useEffect(() => { alpha.current = Math.max(alpha.current, .06); }, [links]);

  const applyView = () => { const v = view.current; root.current?.setAttribute('transform', `translate(${v.x} ${v.y}) scale(${v.k})`); };
  const fit = useCallback(() => {
    const b = svg.current?.getBoundingClientRect(); if (!b) return;
    const ps = live.current.visible.map(n => pos.current.get(n.id)).filter(Boolean) as P[]; if (!ps.length) return;
    const xs = ps.map(p => p.x), ys = ps.map(p => p.y);
    const w = Math.max(...xs) - Math.min(...xs) + 200, h = Math.max(...ys) - Math.min(...ys) + 180;
    const k = Math.max(.45, Math.min(1.3, Math.min(b.width / w, b.height / h)));
    view.current = { k, x: b.width / 2 - k * (Math.max(...xs) + Math.min(...xs)) / 2, y: b.height / 2 - k * (Math.max(...ys) + Math.min(...ys)) / 2 };
    applyView();
  }, []);

  useEffect(() => {
    visible.forEach((n, i) => {
      if (pos.current.has(n.id)) return;
      const parent = n.cluster && pos.current.get(n.cluster);
      const a = i * 2.39996, d = 40 + 22 * Math.sqrt(i);
      pos.current.set(n.id, parent ? { x: parent.x + Math.cos(a) * 30, y: parent.y + Math.sin(a) * 30, vx: 0, vy: 0 } : { x: Math.cos(a) * d, y: Math.sin(a) * d, vx: 0, vy: 0 });
    });
    alpha.current = Math.max(alpha.current, .8);
  }, [visible]);

  useEffect(() => {
    let raf = 0, fitted = false;
    const step = () => {
      const { visible: ns, links: es } = live.current;
      const a = alpha.current;
      if (a <= .004) { raf = requestAnimationFrame(step); return; } // settled: nothing to integrate or draw
      const arr = ns.map(n => [n, pos.current.get(n.id)!] as const).filter(([, p]) => p);
      for (let i = 0; i < arr.length; i++) for (let j = i + 1; j < arr.length; j++) {
        const [na, pa] = arr[i], [nb, pb] = arr[j];
        let dx = pb.x - pa.x, dy = pb.y - pa.y; let d2 = dx * dx + dy * dy;
        if (d2 < 1) { dx = Math.random() - .5; dy = Math.random() - .5; d2 = 1; }
        const d = Math.sqrt(d2), min = R[na.kind] + R[nb.kind] + 22;
        const f = (7200 / d2 + (d < min ? (min - d) * .7 : 0)) * a;
        pa.vx -= dx / d * f; pa.vy -= dy / d * f; pb.vx += dx / d * f; pb.vy += dy / d * f;
      }
      for (const e of es) {
        const pa = pos.current.get(e.from), pb = pos.current.get(e.to); if (!pa || !pb) continue;
        const dx = pb.x - pa.x, dy = pb.y - pa.y, d = Math.sqrt(dx * dx + dy * dy) || 1;
        const f = (d - REST[e.kind]) * .045 * a;
        pa.vx += dx / d * f; pa.vy += dy / d * f; pb.vx -= dx / d * f; pb.vy -= dy / d * f;
      }
      for (const [, p] of arr) {
        p.vx -= p.x * .006 * a; p.vy -= p.y * .006 * a;
        p.vx *= .82; p.vy *= .82;
        if (!p.pin) { p.x += p.vx; p.y += p.vy; } else { p.vx = 0; p.vy = 0; }
      }
      alpha.current *= .985;
      if (!fitted && a < .25) { fitted = true; fit(); }
      for (const n of ns) { const p = pos.current.get(n.id), el = nodeEls.current.get(n.id); if (p && el) el.setAttribute('transform', `translate(${p.x.toFixed(1)} ${p.y.toFixed(1)})`); }
      for (const e of es) {
        const pa = pos.current.get(e.from), pb = pos.current.get(e.to), el = edgeEls.current.get(`${e.from}>${e.to}`);
        if (!pa || !pb || !el) continue;
        const mx = (pa.x + pb.x) / 2, my = (pa.y + pb.y) / 2, dx = pb.x - pa.x, dy = pb.y - pa.y, bend = e.kind === 'contains' ? 0 : .12;
        el.setAttribute('d', `M${pa.x.toFixed(1)} ${pa.y.toFixed(1)} Q${(mx - dy * bend).toFixed(1)} ${(my + dx * bend).toFixed(1)} ${pb.x.toFixed(1)} ${pb.y.toFixed(1)}`);
      }
      raf = requestAnimationFrame(step);
    };
    const b = svg.current!.getBoundingClientRect(); view.current = { k: .9, x: b.width / 2, y: b.height / 2 }; applyView();
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [fit]);

  /* ── pointer: node drag, background pan, wheel zoom ── */
  const toWorld = (cx: number, cy: number) => { const b = svg.current!.getBoundingClientRect(), v = view.current; return { x: (cx - b.left - v.x) / v.k, y: (cy - b.top - v.y) / v.k }; };
  const onNodeDown = (id: string) => (e: React.PointerEvent) => {
    e.stopPropagation();
    const p = pos.current.get(id)!, start = { x: e.clientX, y: e.clientY }; let moved = false;
    const move = (m: PointerEvent) => { if (!moved && Math.hypot(m.clientX - start.x, m.clientY - start.y) < 4) return; moved = true; const w = toWorld(m.clientX, m.clientY); p.x = w.x; p.y = w.y; p.pin = true; alpha.current = Math.max(alpha.current, .35); };
    const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); if (!moved) setSel(v => v === id ? null : id); };
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up);
  };
  const onBgDown = (e: React.PointerEvent) => {
    if (e.button !== 0) return;
    const v0 = { ...view.current }, x0 = e.clientX, y0 = e.clientY; let moved = false;
    const move = (m: PointerEvent) => { if (Math.hypot(m.clientX - x0, m.clientY - y0) > 3) moved = true; view.current = { ...v0, x: v0.x + m.clientX - x0, y: v0.y + m.clientY - y0 }; applyView(); };
    const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); if (!moved) setSel(null); };
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up);
  };
  useEffect(() => {
    const el = svg.current!;
    const wheel = (e: WheelEvent) => {
      e.preventDefault();
      const b = el.getBoundingClientRect(), v = view.current, k = Math.max(.35, Math.min(2.6, v.k * Math.exp(-e.deltaY * .0015)));
      const mx = e.clientX - b.left, my = e.clientY - b.top;
      view.current = { k, x: mx - (mx - v.x) * k / v.k, y: my - (my - v.y) * k / v.k }; applyView();
    };
    el.addEventListener('wheel', wheel, { passive: false });
    return () => el.removeEventListener('wheel', wheel);
  }, []);
  const focusOn = (id: string) => { setSel(id); const p = pos.current.get(id), b = svg.current!.getBoundingClientRect(); if (!p) return; const k = Math.max(view.current.k, 1); view.current = { k, x: b.width / 2 - p.x * k, y: b.height / 2 - p.y * k }; applyView(); };
  const toggleCluster = (id: string) => { setCollapsed(v => { const n = new Set(v); if (n.has(id)) n.delete(id); else n.add(id); return n; }); alpha.current = .9; };
  const relayout = () => { pos.current.forEach(p => { p.pin = false; p.x *= .3; p.y *= .3; }); alpha.current = 1; setTimeout(fit, 900); };

  const node = graph.nodes.find(n => n.id === sel);
  const conns = node ? graph.edges.filter(e => e.from === node.id || e.to === node.id).map(e => ({ e, other: graph.nodes.find(n => n.id === (e.from === node.id ? e.to : e.from))! })) : [];
  const nodeEv = node?.kind === 'media' ? evidence.find(e => e.id === node.refId) : undefined;
  const nodeFi = node?.kind === 'finding' ? findings.find(f => f.id === node.refId) : undefined;
  const lead = assess?.outcomes[0];

  return <div className={`${s.graphWrap} ${node ? s.graphOpen : ''}`}>
    <div className={s.graph} onPointerDown={onBgDown}>
      <div className={s.gridDots} />
      <svg ref={svg} role='img' aria-label='Evidence relationship graph'>
        <defs>{visible.filter(n => n.thumb).map(n => <clipPath key={n.id} id={`c-${n.id}`}><circle r={R[n.kind] - 2} /></clipPath>)}</defs>
        <g ref={root}>
          <g>{links.map(e => { const st = edgeStyle[e.kind]; const dim = near && !(near.has(e.from) && near.has(e.to)); return <path key={`${e.from}>${e.to}`} ref={el => { if (el) edgeEls.current.set(`${e.from}>${e.to}`, el); }} className={`${s.edge} ${e.kind === 'pattern' ? s.edgeFlow : ''} ${dim ? s.dim : ''}`} stroke={toneColor[st.tone]} strokeOpacity={e.kind === 'contains' ? .3 : .85} strokeDasharray={st.dash} />; })}</g>
          <g>{visible.map(n => {
            const r = R[n.kind], c = toneColor[nodeTone(n)], dim = (near && !near.has(n.id)) || (match && !`${n.label} ${n.id}`.toLowerCase().includes(match));
            const hidden = n.kind === 'case' && collapsed.has(n.id) ? graph.nodes.filter(x => x.cluster === n.id).length : 0;
            const showLabel = n.kind === 'case' || n.kind === 'media' || sel === n.id || hover === n.id || (near?.has(n.id) ?? false);
            return <g key={n.id} ref={el => { if (el) nodeEls.current.set(n.id, el); }} className={`${s.node} ${sel === n.id ? s.nodeSel : ''} ${dim ? s.dim : ''}`} onPointerDown={onNodeDown(n.id)} onPointerEnter={() => setHover(n.id)} onPointerLeave={() => setHover(null)} onDoubleClick={() => { const p = pos.current.get(n.id); if (p) p.pin = false; alpha.current = .5; }} role='button' aria-label={`${n.kind} ${n.label}`} tabIndex={0} onKeyDown={e => { if (e.key === 'Enter') setSel(n.id); }}>
              <circle className={s.ringSel} r={r + 7} fill='none' stroke='#e9a23b' strokeWidth='1.5' strokeDasharray='3 3' />
              {n.kind === 'case' && <><circle r={r} fill='#15110b' stroke={c} strokeWidth='2' /><circle r={r - 8} fill={c} opacity='.16' /><text textAnchor='middle' dy='4' fill={c} style={{ font: '600 10px var(--mono)' }}>{n.id.slice(-5)}</text></>}
              {n.kind === 'media' && <><circle r={r} fill='#050505' stroke={c} strokeWidth='2' />{n.thumb && <image href={n.thumb} x={-r} y={-r} width={r * 2} height={r * 2} preserveAspectRatio='xMidYMid slice' clipPath={`url(#c-${n.id})`} />}</>}
              {n.kind === 'finding' && <rect x={-r} y={-r} width={r * 2} height={r * 2} rx='3' transform='rotate(45)' fill={c} fillOpacity='.9' stroke='#0b0a09' strokeWidth='2' />}
              {n.kind === 'metadata' && <rect x={-r} y={-r} width={r * 2} height={r * 2} rx='5' fill='#0b0a09' stroke={c} strokeWidth='1.8' />}
              {n.kind === 'source' && <polygon points={Array.from({ length: 6 }, (_, i) => `${(Math.cos(i * Math.PI / 3) * r).toFixed(1)},${(Math.sin(i * Math.PI / 3) * r).toFixed(1)}`).join(' ')} fill='#0b0a09' stroke={c} strokeWidth='1.8' />}
              {hidden > 0 && <g transform={`translate(${r - 4} ${-r + 4})`} onPointerDown={e => { e.stopPropagation(); toggleCluster(n.id); }}><circle r='10' fill='#e9a23b' /><text textAnchor='middle' dy='3.5' fill='#1a1206' style={{ font: '600 10px var(--sans)' }}>+{hidden}</text></g>}
              {showLabel && <text className={s.nodeLabel} y={r + 16} textAnchor='middle'>{n.label.length > 24 ? n.label.slice(0, 23) + '…' : n.label}</text>}
            </g>;
          })}</g>
        </g>
      </svg>

      <div className={s.gTools} onPointerDown={e => e.stopPropagation()}>
        <label className={s.cmdk} style={{ width: 220, background: '#100f0de6' }}><Search size={14} /><input value={q} onChange={e => setQ(e.target.value)} placeholder='Find a node' aria-label='Find a node' style={{ flex: 1, minWidth: 0, border: 0, outline: 0, background: 'none', color: 'var(--ink)', font: 'inherit' }} /></label>
        <div className={s.seg}><button onClick={fit}><Focus size={14} />Fit</button><button onClick={relayout}><RotateCcw size={14} />Re-layout</button></div>
      </div>

      <div className={s.legendToggle} onPointerDown={e => e.stopPropagation()}>
        <AnimatePresence>{legend && <motion.div className={s.legend} style={{ position: 'absolute', left: 0, bottom: 44 }} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: .16 }}>
          {(Object.keys(edgeStyle) as EdgeKind[]).map(k => <button key={k} aria-pressed={kinds.has(k)} onClick={() => setKinds(v => { const n = new Set(v); if (n.has(k)) n.delete(k); else n.add(k); return n; })}>
            <svg width='28' height='8' aria-hidden='true'><line x1='1' y1='4' x2='27' y2='4' stroke={toneColor[edgeStyle[k].tone]} strokeWidth='2' strokeDasharray={edgeStyle[k].dash} /></svg>{edgeStyle[k].label}
          </button>)}
        </motion.div>}</AnimatePresence>
        <button className={s.pill} onClick={() => setLegend(v => !v)} aria-expanded={legend}><Info size={14} />Relationships</button>
      </div>

      {lead && <div className={s.outcome} style={showOut ? undefined : { padding: 0, width: 'auto', background: 'none', border: 0 }} onPointerDown={e => e.stopPropagation()}>
        {showOut ? <>
          <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}><p className={s.title}>Fused assessment</p><button className={s.iconBtn} style={{ width: 28, height: 28 }} onClick={() => setShowOut(false)} aria-label='Close'><X size={14} /></button></header>
          {assess!.outcomes.map((o, i) => <div key={o.label} className={`${s.outRow} ${i === 0 ? s.outLead : ''}`}><b style={{ fontWeight: i === 0 ? 600 : 400 }}>{o.label}</b><span>{o.low}–{o.high}%</span><i><em style={{ left: `${o.low}%`, width: `${o.high - o.low}%` }} /></i></div>)}
          <p className={s.cap}>{assess!.note}</p>
        </> : <button className={s.pill} onClick={() => setShowOut(true)}><b style={{ color: 'var(--gold-2)' }}>{lead.low}–{lead.high}%</b>{lead.label}</button>}
      </div>}
    </div>

    <aside className={s.detail} aria-label='Node details'>
      <AnimatePresence mode='wait'>{node && <motion.div key={node.id} className={s.detailIn} initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} transition={{ duration: .2, ease: [.22, 1, .36, 1] }}>
        <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}><Dot tone={nodeTone(node)}>{toneWord[nodeTone(node)]}</Dot><button className={s.iconBtn} onClick={() => setSel(null)} aria-label='Close details'><X size={16} /></button></header>
        {nodeEv && <span className={s.thumb} style={{ display: 'block', aspectRatio: '16 / 10', borderRadius: 14 }}><Image src={nodeEv.media.still} alt='' fill sizes='340px' style={{ objectFit: 'cover' }} /></span>}
        <div><h2>{node.label}</h2><p style={{ marginTop: 10, color: 'var(--soft)', fontSize: 14 }}>{nodeFi?.detail ?? node.detail}</p></div>
        <div className={s.actions}>
          {node.kind === 'case' && <><button className={`${s.btn} ${s.primary}`} onClick={() => go('investigate', { caseId: node.id })}>Open investigation <ArrowRight size={14} /></button><button className={`${s.btn} ${s.ghost}`} onClick={() => toggleCluster(node.id)}>{collapsed.has(node.id) ? 'Expand' : 'Collapse'}</button></>}
          {node.kind === 'media' && <button className={`${s.btn} ${s.primary}`} onClick={() => go('investigate', { evidence: node.refId })}>Open in workspace <ArrowRight size={14} /></button>}
          {nodeFi && <button className={`${s.btn} ${s.primary}`} onClick={() => go('investigate', { evidence: nodeFi.evidenceId, finding: nodeFi.id })}>Inspect finding <ArrowRight size={14} /></button>}
        </div>
        <div><p className={s.cap} style={{ marginBottom: 8 }}>Connected to</p>
          <div className={s.links}>{conns.map(({ e, other }) => <button key={e.from + e.to} onClick={() => focusOn(other.id)}>
            <svg width='18' height='8' aria-hidden='true'><line x1='1' y1='4' x2='17' y2='4' stroke={toneColor[edgeStyle[e.kind].tone]} strokeWidth='2' strokeDasharray={edgeStyle[e.kind].dash} /></svg>
            <span>{other.label}</span><small>{e.label ?? edgeStyle[e.kind].label}</small></button>)}</div>
        </div>
      </motion.div>}</AnimatePresence>
    </aside>
  </div>;
}
