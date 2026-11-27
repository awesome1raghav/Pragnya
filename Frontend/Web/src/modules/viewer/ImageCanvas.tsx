'use client';

/* Image examination canvas. The preserved original is shown as stored; overlays are the analysis' own artifacts (ELA and
   noise heatmaps, with the method each records); boxes are the regions findings recorded, in percent of the frame.
   Nothing is drawn that a module did not produce. Zoom and pan change only the view, never the evidence. */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Columns2, Expand, Maximize, Minus, Plus, SplitSquareHorizontal, Square } from 'lucide-react';
import { api, type Artifact } from '@/api';
import type { ViewerFinding } from './normalize';
import v from './viewer.module.css';

type Mode = 'single' | 'slider' | 'side';
type View = { z: number; x: number; y: number; animate: boolean };

export function ImageCanvas({ evidenceId, filename, findings, selected, onSelect, heatmaps }: {
  evidenceId: string; filename: string; findings: ViewerFinding[]; selected: ViewerFinding | null; onSelect: (id: string) => void; heatmaps: Artifact[];
}) {
  const box = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState<{ w: number; h: number } | null>(null);
  const [view, setView] = useState<View>({ z: 1, x: 0, y: 0, animate: false });
  const [overlay, setOverlay] = useState<string>('');
  const [opacity, setOpacity] = useState(0.6);
  const [mode, setMode] = useState<Mode>('single');
  const [split, setSplit] = useState(50);
  const drag = useRef<{ x: number; y: number; vx: number; vy: number } | null>(null);
  const src = api.evidence.previewUrl(evidenceId);
  const heat = heatmaps.find(h => h.artifact_id === overlay) ?? null;
  const regions = findings.filter(f => f.location.kind === 'region');

  const fit = useCallback((animate = true) => {
    const el = box.current; if (!el || !size) return;
    const z = Math.min(el.clientWidth / size.w, el.clientHeight / size.h) * 0.96;
    setView({ z, x: (el.clientWidth - size.w * z) / 2, y: (el.clientHeight - size.h * z) / 2, animate });
  }, [size]);
  useEffect(() => { fit(false); }, [fit]);
  useEffect(() => { const r = new ResizeObserver(() => fit(false)); if (box.current) r.observe(box.current); return () => r.disconnect(); }, [fit]);

  // a region finding was chosen: move the view so the recorded region fills the frame
  useEffect(() => {
    const el = box.current;
    if (!el || !size || !selected || selected.location.kind !== 'region') return;
    const l = selected.location;
    const rw = (l.w / 100) * size.w, rh = (l.h / 100) * size.h;
    const z = Math.min(el.clientWidth / rw, el.clientHeight / rh, 8) * 0.55;
    const cx = ((l.x + l.w / 2) / 100) * size.w, cy = ((l.y + l.h / 2) / 100) * size.h;
    setView({ z, x: el.clientWidth / 2 - cx * z, y: el.clientHeight / 2 - cy * z, animate: true });
  }, [selected, size]);
  // a heatmap-backed finding was chosen: show its own heatmap
  useEffect(() => { const h = selected?.artifacts.find(a => a.kind === 'HEATMAP'); if (h) setOverlay(h.artifact_id); }, [selected]);

  const zoomAt = (factor: number, px?: number, py?: number) => setView(cur => {
    const el = box.current!; const ax = px ?? el.clientWidth / 2, ay = py ?? el.clientHeight / 2;
    const z = Math.min(Math.max(cur.z * factor, 0.05), 16);
    return { z, x: ax - ((ax - cur.x) * z) / cur.z, y: ay - ((ay - cur.y) * z) / cur.z, animate: px === undefined };
  });
  const actual = () => { const el = box.current; if (!el || !size) return; setView({ z: 1, x: (el.clientWidth - size.w) / 2, y: (el.clientHeight - size.h) / 2, animate: true }); };

  useEffect(() => {
    const el = box.current; if (!el) return;
    const wheel = (e: WheelEvent) => { e.preventDefault(); const r = el.getBoundingClientRect(); zoomAt(e.deltaY < 0 ? 1.15 : 1 / 1.15, e.clientX - r.left, e.clientY - r.top); };
    el.addEventListener('wheel', wheel, { passive: false });
    return () => el.removeEventListener('wheel', wheel);
  }, []);
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).closest('input, textarea, select')) return;
      if (e.key === '+' || e.key === '=') zoomAt(1.25); else if (e.key === '-') zoomAt(1 / 1.25); else if (e.key === '0') fit(); else if (e.key === '1') actual();
    };
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
  });

  const layer = (withOverlay: boolean, clip?: string) => size && <div className={v.layer} style={{ width: size.w, height: size.h, transform: `translate(${view.x}px, ${view.y}px) scale(${view.z})`, transition: view.animate ? 'transform .45s cubic-bezier(.22,1,.36,1)' : 'none', clipPath: clip }}>
    {/* eslint-disable-next-line @next/next/no-img-element */}
    <img src={src} alt={`${filename}, the preserved original`} draggable={false} />
    {withOverlay && heat && /* eslint-disable-next-line @next/next/no-img-element */
      <img className={v.heat} src={api.analysis.artifactUrl(heat.artifact_id)} alt={`${String(heat.attributes.method ?? 'analysis')} heatmap produced by the analysis`} style={{ opacity }} draggable={false} />}
    {regions.map(f => f.location.kind === 'region' && <button key={f.id} className={v.region} data-on={selected?.id === f.id || undefined}
      style={{ left: `${f.location.x}%`, top: `${f.location.y}%`, width: `${f.location.w}%`, height: `${f.location.h}%`, borderWidth: 2 / view.z }}
      onClick={e => { e.stopPropagation(); onSelect(f.id); }} aria-label={`Region recorded by ${f.moduleId}: ${f.title}`} />)}
  </div>;

  return <div className={v.canvasWrap}>
    <div className={v.toolbar} role='toolbar' aria-label='Image tools'>
      <div className={v.group}>
        <button onClick={() => zoomAt(1 / 1.25)} aria-label='Zoom out'><Minus size={15} /></button>
        <span className={v.zoom} aria-live='polite'>{Math.round(view.z * 100)}%</span>
        <button onClick={() => zoomAt(1.25)} aria-label='Zoom in'><Plus size={15} /></button>
        <button onClick={() => fit()} aria-label='Fit to screen' title='Fit (0)'><Maximize size={15} /></button>
        <button onClick={actual} aria-label='Actual size' title='Actual size (1)'><Expand size={15} /></button>
      </div>
      <div className={v.group}>
        <label className={v.select}><span>Overlay</span>
          <select value={overlay} onChange={e => setOverlay(e.target.value)} aria-label='Overlay'>
            <option value=''>None</option>
            {heatmaps.map(h => <option key={h.artifact_id} value={h.artifact_id}>{String(h.attributes.method ?? 'heatmap')} heatmap</option>)}
          </select></label>
        {heat && <label className={v.range}><span>Opacity</span><input type='range' min={0} max={1} step={0.05} value={opacity} onChange={e => setOpacity(Number(e.target.value))} aria-label='Overlay opacity' /></label>}
      </div>
      <div className={v.group} role='group' aria-label='Comparison'>
        <button aria-pressed={mode === 'single'} onClick={() => setMode('single')} aria-label='Single view'><Square size={15} /></button>
        <button aria-pressed={mode === 'slider'} onClick={() => setMode('slider')} aria-label='Before and after slider' disabled={!heat} title={heat ? undefined : 'Choose an overlay to compare'}><SplitSquareHorizontal size={15} /></button>
        <button aria-pressed={mode === 'side'} onClick={() => setMode('side')} aria-label='Side by side' disabled={!heat} title={heat ? undefined : 'Choose an overlay to compare'}><Columns2 size={15} /></button>
      </div>
    </div>
    <div className={v.stageRow} data-mode={heat ? mode : 'single'}>
      {(heat && mode === 'side' ? [false, true] : [heat ? mode !== 'slider' : false]).map((withOverlay, i) =>
        <div key={i} ref={i === 0 ? box : undefined} className={v.stage}
          onPointerDown={e => { (e.target as HTMLElement).setPointerCapture?.(e.pointerId); drag.current = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y }; }}
          onPointerMove={e => { const d = drag.current; if (d) setView(cur => ({ ...cur, x: d.vx + e.clientX - d.x, y: d.vy + e.clientY - d.y, animate: false })); }}
          onPointerUp={() => { drag.current = null; }} onDoubleClick={() => fit()}>
          {layer(withOverlay)}
          {heat && mode === 'slider' && <>{layer(true, `inset(0 0 0 ${split}%)`)}
            <div className={v.splitLine} style={{ left: `${split}%` }} aria-hidden='true' />
            <input className={v.splitRange} type='range' min={0} max={100} value={split} onChange={e => setSplit(Number(e.target.value))} aria-label='Compare original and heatmap' />
            <span className={v.splitTag} style={{ left: 12 }}>Original</span><span className={v.splitTag} style={{ right: 12 }}>{String(heat.attributes.method ?? '')} heatmap</span>
          </>}
          {heat && mode === 'side' && <span className={v.splitTag} style={{ left: 12 }}>{withOverlay ? `${String(heat.attributes.method ?? '')} heatmap` : 'Original'}</span>}
          {/* hidden probe for the natural size of the preserved image */}
          {i === 0 && !size && /* eslint-disable-next-line @next/next/no-img-element */ <img src={src} alt='' aria-hidden='true' className={v.probe} onLoad={e => setSize({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })} />}
        </div>)}
    </div>
    <p className={v.canvasNote}>{regions.length ? `${regions.length} recorded region${regions.length === 1 ? '' : 's'}; select one to focus it.` : 'No finding recorded a region in this image.'}
      {heatmaps.length ? ` Overlays are the analysis' own heatmaps (${heatmaps.map(h => String(h.attributes.method ?? 'heatmap')).join(', ')}).` : ' No heatmap was produced.'} Drag to pan, scroll to zoom, double-click to fit.</p>
  </div>;
}
