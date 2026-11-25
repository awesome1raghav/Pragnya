'use client';

import { useEffect, useRef } from 'react';

/* A flowing field of dots under the hero.
   Physics: three superposed surface waves obey the deep-water dispersion relation ω = √(g·k), so short
   ripples travel faster than long swells. That is why the motion reads as water, not as a looped GIF.
   Cost: per-row constants are computed once per resize; each frame evaluates the waves on a coarse
   column grid shared by every row, then draws two batched paths (amber crest, ember edges): 2 fills a
   frame instead of thousands. Device pixel ratio is capped, the loop sleeps off screen and in hidden
   tabs, and if frames run long it widens the dot spacing on its own (adaptive quality). */
const G = 9.8;
const WAVES = [ // wave number k (per screen width, ×2π implied in u), amplitude share, phase per row
  { k: 6.2, a: .55, row: 2.4, dir: 1 },
  { k: 13.0, a: .18, row: 5.0, dir: -1 },
  { k: 2.4, a: .5, row: 0, dir: 1, deep: true },
];
const SPEED = .17; // global time scale so ω = √(g·k) lands in a calm range

export default function WaveField({ running, reduced, className }: { running: boolean; reduced: boolean; className?: string }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const state = useRef({ running, reduced });
  state.current = { running, reduced };

  useEffect(() => {
    const el = canvas.current!;
    const ctx = el.getContext('2d', { alpha: true, desynchronized: true })!;
    const ROWS = 30;
    let w = 0, h = 0, raf = 0, t = 0, last = performance.now(), visible = true, step = 7, slow = 0;
    let rows: { base: number; amp: number; alpha: number; size: number; crest: boolean; k: number; band: number }[] = [];
    let cols = new Float32Array(0), sinA = new Float32Array(0), sinB = new Float32Array(0), sinC = new Float32Array(0);
    const omega = WAVES.map(wv => Math.sqrt(G * wv.k) * SPEED);

    const layout = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, w < 700 ? 1 : 1.5);
      w = el.clientWidth; h = el.clientHeight;
      el.width = Math.round(w * dpr); el.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      rows = Array.from({ length: ROWS }, (_, r) => {
        const k = r / (ROWS - 1);
        const alpha = .08 + .5 * Math.pow(Math.sin(Math.PI * k), 1.6);
        return { k, base: h * (.28 + k * .58), amp: h * (.16 + .1 * Math.sin(k * 3.1)), alpha, size: .9 + 1.1 * alpha, crest: k > .35 && k < .7, band: Math.min(3, Math.floor(alpha / .145)) };
      });
      const n = Math.ceil(w / step) + 2;
      cols = new Float32Array(n); sinA = new Float32Array(n); sinB = new Float32Array(n); sinC = new Float32Array(n);
      for (let i = 0; i < n; i++) cols[i] = (i - 1) * step;
      draw();
    };

    const draw = () => {
      ctx.clearRect(0, 0, w, h);
      const n = cols.length;
      // the row-independent part of each wave's phase, evaluated once per column
      for (let i = 0; i < n; i++) {
        const u = cols[i] / w;
        sinA[i] = u * WAVES[0].k + omega[0] * t;
        sinB[i] = u * WAVES[1].k - omega[1] * t;
        sinC[i] = Math.sin(u * WAVES[2].k + omega[2] * t);
      }
      // rows are batched by colour and by one of four opacity bands: at most 8 fills a frame
      for (let pass = 0; pass < 8; pass++) {
        const crest = pass >= 4, band = pass % 4;
        ctx.beginPath();
        let any = false;
        for (const r of rows) {
          if (r.crest !== crest || r.band !== band) continue;
          any = true;
          const phA = r.k * WAVES[0].row, phB = r.k * WAVES[1].row, deep = r.amp * WAVES[2].a * (1 - r.k);
          const aA = r.amp * WAVES[0].a, aB = r.amp * WAVES[1].a;
          for (let i = 0; i < n; i++) {
            const u = cols[i] / w;
            const y = r.base + Math.sin(sinA[i] + phA) * aA + Math.sin(sinB[i] + phB) * aB + sinC[i] * deep;
            const sz = r.size * (1 - Math.abs(u - .5) * .9);
            ctx.rect(cols[i], y, sz, sz);
          }
        }
        if (!any) continue;
        const a = .1 + band * .145;
        ctx.fillStyle = crest ? `rgba(233,162,59,${a})` : `rgba(217,101,43,${a * .85})`;
        ctx.fill();
      }
    };

    const loop = (now: number) => {
      const ms = now - last; last = now;
      if (visible && state.current.running && !state.current.reduced) {
        t += Math.min(.05, ms / 1000);
        const t0 = performance.now(); draw(); const cost = performance.now() - t0;
        // adaptive quality: if drawing alone eats over 4 ms for a while, space the dots wider
        slow = cost > 4 ? slow + 1 : Math.max(0, slow - 1);
        if (slow > 20 && step < 12) { step += 1; slow = 0; layout(); }
      }
      raf = requestAnimationFrame(loop);
    };

    const ro = new ResizeObserver(layout); ro.observe(el);
    const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; }); io.observe(el);
    const vis = () => { last = performance.now(); if (document.visibilityState !== 'visible') visible = false; };
    document.addEventListener('visibilitychange', vis);
    layout();
    raf = requestAnimationFrame(loop);
    return () => { cancelAnimationFrame(raf); ro.disconnect(); io.disconnect(); document.removeEventListener('visibilitychange', vis); };
  }, []);

  return <canvas ref={canvas} className={className} aria-hidden='true' />;
}
