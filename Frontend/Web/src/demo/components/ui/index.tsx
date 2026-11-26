'use client';

import Image from 'next/image';
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import s from '@/styles/workspace.module.css';
import type { Branch, Media } from '@/demo/api';
import { BRANCHES, branchColor, branchLabel, type Tone, type Tool, type View } from '@/demo/utils/labels';

export type Ctx = {
  go: (view: View, opts?: { caseId?: string; evidence?: string; tool?: Tool; finding?: string; run?: boolean }) => void;
  notify: (msg: string, undo?: () => void) => void;
  caseId: string; evidenceId: string;
};

export const Dot = ({ tone = 'mute', children }: { tone?: Tone; children: ReactNode }) => <span className={s.dot} data-tone={tone}>{children}</span>;

/* A finding looks the same everywhere: a diamond in its severity colour and its ID (the graph draws findings as
   diamonds too), then the time range when it has one. This is how one clue is traced from queue to report. */
export function FindingMark({ f, time = true }: { f: { id: string; severity: string; startSec: number | null; endSec: number | null }; time?: boolean }) {
  const r = f.startSec != null && f.endSec != null && f.endSec > f.startSec;
  return <span className={s.fMark} data-tone={f.severity === 'high' ? 'alert' : f.severity === 'medium' ? 'steel' : 'mute'}>
    <i aria-hidden='true' /><b>{f.id}</b>{time && r && <span>{fmt(f.startSec!)}–{fmt(f.endSec!)}</span>}
  </span>;
}

export const focusPos = (m: Media) => m.focus ? `${m.focus.x * 100}% ${m.focus.y * 100}%` : '50% 50%';
export const aspect = (m: Media) => m.width / m.height;

export function Thumb({ media, big, className, style, sizes = '120px', eager }: { media: Media; big?: boolean; className?: string; style?: React.CSSProperties; sizes?: string; eager?: boolean }) {
  return <span className={`${s.thumb} ${className ?? ''}`} style={{ display: 'block', ...style }}>
    <Image src={big ? media.still : media.thumb} alt='' fill sizes={sizes} loading={eager ? 'eager' : undefined} style={{ objectPosition: focusPos(media) }} />
  </span>;
}

/* readiness per analysis branch, as four quiet segments */
export function Ready({ value }: { value: Record<Branch, number | null> }) {
  return <span className={s.ready} title={BRANCHES.map(b => `${branchLabel[b]} ${value[b] ?? '—'}${value[b] == null ? '' : '%'}`).join(' · ')}>
    {BRANCHES.map(b => <i key={b}><em style={{ transform: `scaleX(${(value[b] ?? 0) / 100})`, background: branchColor[b] }} /></i>)}
  </span>;
}

/* object-fit: cover maths: map a region in image percent into a box of another aspect */
export function coverBox(b: { x: number; y: number; w: number; h: number }, arImg: number, arBox: number, px = .5, py = .5) {
  if (arBox > arImg) { const f = arImg / arBox, off = (1 - f) * py * 100; return { x: b.x, w: b.w, y: (b.y - off) / f, h: b.h / f }; }
  const f = arBox / arImg, off = (1 - f) * px * 100; return { y: b.y, h: b.h, x: (b.x - off) / f, w: b.w / f };
}
export function useAspect<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [ar, setAr] = useState(1.6);
  useEffect(() => {
    const el = ref.current; if (!el) return;
    const ro = new ResizeObserver(([e]) => { const { width, height } = e.contentRect; if (height) setAr(width / height); });
    ro.observe(el); return () => ro.disconnect();
  }, []);
  return [ref, ar] as const;
}

/* hover preview: a larger frame after a short intent delay */
export function usePreview() {
  const [p, setP] = useState<{ media: Media; title: ReactNode; meta?: ReactNode; x: number; y: number } | null>(null);
  const t = useRef<ReturnType<typeof setTimeout>>(undefined);
  const bind = useCallback((media: Media, title: ReactNode, meta?: ReactNode) => ({
    onMouseEnter: (e: React.MouseEvent) => { const { clientX: x, clientY: y } = e; clearTimeout(t.current); t.current = setTimeout(() => setP({ media, title, meta, x, y }), 320); },
    onMouseMove: (e: React.MouseEvent) => setP(v => v && { ...v, x: e.clientX, y: e.clientY }),
    onMouseLeave: () => { clearTimeout(t.current); setP(null); },
    onMouseDown: () => { clearTimeout(t.current); setP(null); },
  }), []);
  const node = p && typeof document !== 'undefined' ? createPortal(
    <div className={s.preview} style={{ left: Math.min(p.x + 18, window.innerWidth - 316), top: Math.min(p.y + 18, window.innerHeight - 240) }} aria-hidden='true'>
      <Thumb media={p.media} big sizes='300px' /><p><b>{p.title}</b>{p.meta}</p>
    </div>, document.body) : null;
  return { bind, node };
}

export const PageHead = ({ title, desc, children }: { title: string; desc?: ReactNode; children?: ReactNode }) =>
  <header className={s.pageHead}><div><h1>{title}</h1>{desc && <p>{desc}</p>}</div>{children && <div className={s.actions}>{children}</div>}</header>;

/* loading skeleton that keeps the layout's shape */
export const Skeleton = ({ h = 16, w = '100%', r = 8, style }: { h?: number; w?: number | string; r?: number; style?: React.CSSProperties }) => <i className={s.skel} style={{ height: h, width: w, borderRadius: r, ...style }} />;

export const fmt = (t: number) => `${String(Math.floor(t / 60)).padStart(2, '0')}:${String(Math.floor(t % 60)).padStart(2, '0')}.${String(Math.floor((t % 1) * 100)).padStart(2, '0')}`;
export const series = (n: number, seed: number) => Array.from({ length: n }, (_, i) => Math.round(28 + Math.abs(Math.sin(i * 1.37 + seed) * Math.cos(i * .41 + seed * 2)) * 66));
