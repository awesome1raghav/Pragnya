'use client';

/* Entry loader, once per browser session.
   - Server-rendered, so it covers the page from the first paint; an inline head script marks returning
     visits (sessionStorage) and the CSS hides it before anything is drawn.
   - Progress is honest: it chases real readiness (web fonts, the hero's priority images, window load)
     through a critically damped spring, so the number never jumps or runs backwards. A floor of 1.4 s
     keeps the brand moment readable; a ceiling of 4 s means a slow network never holds the visitor.
   - Exit: two shutters part by transform only, the aperture closes, then the page receives `nx:ready`. */
import { useEffect, useRef, useState } from 'react';
import s from './loader.module.css';

const LINES = ['Sealing the original', 'Loading spatial branch', 'Aligning audio and frames', 'Calibrating evidence fusion'];
const MIN = 1400, MAX = 4000;

function release() {
  document.documentElement.dataset.nxReady = '1';
  window.dispatchEvent(new Event('nx:ready'));
}

export default function Loader() {
  const root = useRef<HTMLDivElement>(null);
  const pct = useRef<HTMLSpanElement>(null);
  const bar = useRef<HTMLElement>(null);
  const [line, setLine] = useState(0);
  const [phase, setPhase] = useState<'load' | 'exit' | 'gone'>('load');

  useEffect(() => {
    const html = document.documentElement;
    if (html.classList.contains('nx-seen')) { release(); setPhase('gone'); return; }
    try { sessionStorage.setItem('nx-intro', '1'); } catch {}
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const t0 = performance.now();

    // real readiness, each signal worth a share of the bar
    let target = .08;
    const add = (v: number) => { target = Math.min(1, target + v); };
    document.fonts?.ready.then(() => add(.3));
    const imgs = [...document.querySelectorAll<HTMLImageElement>('img[fetchpriority="high"], img[loading="eager"]')].slice(0, 6);
    const share = imgs.length ? .32 / imgs.length : 0;
    if (!imgs.length) add(.32);
    imgs.forEach(img => { if (img.complete) add(share); else { img.addEventListener('load', () => add(share), { once: true }); img.addEventListener('error', () => add(share), { once: true }); } });
    if (document.readyState === 'complete') add(.3); else window.addEventListener('load', () => add(.3), { once: true });

    // critically damped spring toward the target: x'' = -k(x - target) - 2√k x'
    let x = 0, v = 0, last = t0, raf = 0, shown = -1, lineAt = 0;
    const k = 38, c = 2 * Math.sqrt(k);
    const frame = (now: number) => {
      const dt = Math.min(.05, (now - last) / 1000); last = now;
      const age = now - t0;
      const goal = age > MAX ? 1 : Math.min(target, .25 + .75 * Math.min(1, age / MIN)); // never ahead of the floor
      v += (-k * (x - goal) - c * v) * dt; x += v * dt; x = Math.max(0, Math.min(1, x));
      const p = Math.round(x * 100);
      if (p !== shown) { shown = p; if (pct.current) pct.current.textContent = String(p).padStart(3, '0'); }
      if (bar.current) bar.current.style.transform = `scaleX(${x})`;
      const li = Math.min(LINES.length - 1, Math.floor(x * LINES.length));
      if (li !== lineAt) { lineAt = li; setLine(li); }
      if (p >= 100 && age >= (reduced ? 400 : MIN)) {
        setPhase('exit');
        setTimeout(release, reduced ? 0 : 380);           // the page starts its intro as the shutters part
        setTimeout(() => setPhase('gone'), reduced ? 250 : 1100);
        return;
      }
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    html.style.overflow = 'hidden';
    return () => { cancelAnimationFrame(raf); html.style.overflow = ''; };
  }, []);

  useEffect(() => { if (phase === 'gone') document.documentElement.style.overflow = ''; }, [phase]);

  if (phase === 'gone') return null;
  return <div ref={root} className={`${s.loader} ${phase === 'exit' ? s.exit : ''}`} role='status' aria-live='polite' aria-label='Loading NEXTRON'>
    <div className={`${s.shutter} ${s.top}`} /><div className={`${s.shutter} ${s.bottom}`} />
    <div className={s.center}>
      <svg className={s.mark} viewBox='0 0 64 64' aria-hidden='true'>
        <circle className={s.ring} cx='32' cy='32' r='27' />
        <g className={s.blades}>{Array.from({ length: 6 }, (_, i) => <path key={i} style={{ ['--i' as string]: i }} d='M32 5 L46 29' transform={`rotate(${i * 60} 32 32)`} />)}</g>
        <circle className={s.core} cx='32' cy='32' r='5' />
      </svg>
      <p className={s.word} aria-hidden='true'>{'NEXTRON'.split('').map((ch, i) => <span key={i} style={{ ['--i' as string]: i }}>{ch}</span>)}</p>
      <div className={s.meter}>
        <p><span className={s.line} key={line}>{LINES[line]}</span><b><span ref={pct}>000</span>%</b></p>
        <i><em ref={bar} /></i>
      </div>
    </div>
    <p className={s.foot}>Digital media verification</p>
  </div>;
}
