'use client';

/* The hero exhibit: one ordinary frame that becomes evidence, under the visitor's control.
   - One value, v ∈ [0, 1], drives everything. 0 = as shared, .5 = error level, 1 = the match.
     0 → .5 wipes the error-level layer across the frame; .5 → 1 dims it and draws the copy back to its source.
   - Drag across the frame (relative, pointer captured), drag or tap the timeline, tap the frame to step forward,
     or use the step buttons (arrow keys move between them). Releasing snaps to the nearest step.
   - Rendering writes transforms and opacity to refs. A critically damped spring runs only while the value is
     settling, then the loop stops: nothing moves while nobody is looking or touching.
   - Every number on screen is measured from the staged file in public/images/exhibit (see its README). */
import { useCallback, useEffect, useRef, useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { ArrowRight, MoveHorizontal } from 'lucide-react';
import s from './exhibit.module.css';

// the staged edit, in percent of the 1280 × 853 still
const A = { x: 41.8, y: 62.6, w: 5.78, h: 9.85 };   // where the group really stands
const B = { x: 71.02, y: 62.95, w: 5.78, h: 9.85 }; // where it was pasted
const STOPS = [0, .5, 1];
const STEPS = [
  { label: 'As shared', title: 'What everyone saw', body: 'A busy concourse, shared as proof of how crowded the station was. Nothing looks wrong.' },
  { label: 'Error level', title: 'One patch was saved twice', body: 'Re-saving the frame shows how each area was compressed. One patch of plain floor glows at 3.9× the frame’s average: it was compressed on its own, then pasted in.' },
  { label: 'The match', title: 'The crowd repeats itself', body: 'That patch is a copy. The same five people stand 374 px to the left, pose for pose, with a pixel match of 0.987.' },
];
const clamp = (x: number) => Math.max(0, Math.min(1, x));
const pct = (r: typeof A) => ({ left: `${r.x}%`, top: `${r.y}%`, width: `${r.w}%`, height: `${r.h}%` });

export default function Exhibit() {
  const frame = useRef<HTMLDivElement>(null);
  const track = useRef<HTMLDivElement>(null);
  const el = {
    elaO: useRef<HTMLDivElement>(null), elaI: useRef<HTMLDivElement>(null), boxA: useRef<HTMLDivElement>(null), boxB: useRef<HTMLDivElement>(null),
    link: useRef<HTMLDivElement>(null), line: useRef<HTMLElement>(null), card: useRef<HTMLDivElement>(null), rowE: useRef<HTMLParagraphElement>(null), rowM: useRef<HTMLParagraphElement>(null),
    head: useRef<HTMLSpanElement>(null), fill: useRef<HTMLElement>(null),
  };
  const [step, setStep] = useState(0);
  const [touched, setTouched] = useState(false);
  const touchedRef = useRef(false);
  const st = useRef({ v: 0, vel: 0, target: 0, raf: 0, last: 0, step: 0, reduced: false });

  const paint = useCallback((v: number) => {
    const e = clamp(v / .5), m = clamp((v - .5) / .5), set = (r: React.RefObject<HTMLElement | null>, css: Partial<CSSStyleDeclaration>) => { if (r.current) Object.assign(r.current.style, css); };
    set(el.elaO, { transform: `translate3d(${((e - 1) * 100).toFixed(2)}%,0,0)`, opacity: String(1 - .62 * m) });
    set(el.elaI, { transform: `translate3d(${((1 - e) * 100).toFixed(2)}%,0,0)` });
    el.elaO.current?.style.setProperty('--edge', e > .001 && e < .999 ? '1' : '0');
    const b = clamp((e - .72) / .16);
    set(el.boxB, { opacity: String(b), transform: `scale(${(1.25 - .25 * b).toFixed(3)})` });
    const a = clamp(m / .45);
    set(el.boxA, { opacity: String(a), transform: `scale(${(1.25 - .25 * a).toFixed(3)})` });
    set(el.link, { opacity: String(clamp((m - .25) / .2)) });
    set(el.line, { transform: `scaleX(${clamp((m - .3) / .55).toFixed(3)})` });
    el.link.current?.style.setProperty('--tag', String(clamp((m - .8) / .2)));
    const c = clamp((e - .82) / .18);
    set(el.card, { opacity: String(c), transform: `translate3d(0,${((1 - c) * 12).toFixed(1)}px,0)`, visibility: c > 0 ? 'visible' : 'hidden' });
    set(el.rowM, { opacity: String(clamp((m - .6) / .4)) });
    set(el.head, { transform: `translate3d(${(v * 100).toFixed(2)}%,0,0)` });
    set(el.fill, { transform: `scaleX(${v.toFixed(4)})` });
    const n = v < .25 ? 0 : v < .75 ? 1 : 2;
    if (n !== st.current.step) { st.current.step = n; setStep(n); }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // spring toward the target, then sleep: x'' = -k(x - target) - 2√k x'
  const settle = useCallback(() => {
    const S = st.current;
    cancelAnimationFrame(S.raf);
    if (S.reduced) { S.v = S.target; S.vel = 0; paint(S.v); return; }
    const k = 90, c = 2 * Math.sqrt(k);
    S.last = performance.now();
    const tick = (now: number) => {
      const dt = Math.min(.04, (now - S.last) / 1000); S.last = now;
      S.vel += (-k * (S.v - S.target) - c * S.vel) * dt; S.v += S.vel * dt;
      if (Math.abs(S.v - S.target) < .0006 && Math.abs(S.vel) < .002) { S.v = S.target; S.vel = 0; paint(S.v); return; }
      paint(clamp(S.v)); S.raf = requestAnimationFrame(tick);
    };
    S.raf = requestAnimationFrame(tick);
  }, [paint]);
  const goTo = useCallback((t: number) => { st.current.target = clamp(t); settle(); }, [settle]);
  const snap = () => goTo(STOPS.reduce((a, b) => Math.abs(b - st.current.v) < Math.abs(a - st.current.v) ? b : a));

  useEffect(() => {
    const S = st.current;
    S.reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    paint(0);
    if (S.reduced) return;
    // one quiet hint that the frame can be moved, after the entrance; never repeated
    const t1 = setTimeout(() => { if (!touchedRef.current) goTo(.16); }, 1900);
    const t2 = setTimeout(() => { if (!touchedRef.current) goTo(0); }, 2700);
    return () => { clearTimeout(t1); clearTimeout(t2); cancelAnimationFrame(S.raf); };
  }, [paint, goTo]);
  const touch = () => { if (!touchedRef.current) { touchedRef.current = true; setTouched(true); } };

  /* drag across the frame: relative; a full frame-width of travel covers all three steps. A tap steps forward. */
  const onFrameDown = (e: React.PointerEvent) => {
    if (e.button !== 0) return;
    touch();
    const S = st.current, w = frame.current!.clientWidth, x0 = e.clientX, y0 = e.clientY, v0 = S.v, t0 = performance.now();
    let moved = false;
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    const move = (m: PointerEvent) => {
      if (!moved && Math.abs(m.clientX - x0) < 6) return;
      moved = true; cancelAnimationFrame(S.raf);
      S.v = S.target = clamp(v0 + (m.clientX - x0) / (w * .9)); S.vel = 0; paint(S.v);
    };
    const up = (u: PointerEvent) => {
      frame.current?.removeEventListener('pointermove', move); frame.current?.removeEventListener('pointerup', up); frame.current?.removeEventListener('pointercancel', up);
      if (!moved && u.type === 'pointerup' && performance.now() - t0 < 500 && Math.hypot(u.clientX - x0, u.clientY - y0) < 8) { goTo(STOPS[(S.step + 1) % 3]); return; }
      snap();
    };
    frame.current!.addEventListener('pointermove', move); frame.current!.addEventListener('pointerup', up); frame.current!.addEventListener('pointercancel', up);
  };
  /* the timeline: absolute, the handle goes where you press */
  const onTrackDown = (e: React.PointerEvent) => {
    if (e.button !== 0) return;
    touch();
    const S = st.current, r = track.current!.getBoundingClientRect();
    const at = (x: number) => { cancelAnimationFrame(S.raf); S.v = S.target = clamp((x - r.left) / r.width); S.vel = 0; paint(S.v); };
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    at(e.clientX);
    const move = (m: PointerEvent) => at(m.clientX);
    const up = () => { track.current?.removeEventListener('pointermove', move); track.current?.removeEventListener('pointerup', up); track.current?.removeEventListener('pointercancel', up); snap(); };
    track.current!.addEventListener('pointermove', move); track.current!.addEventListener('pointerup', up); track.current!.addEventListener('pointercancel', up);
  };
  const onStepKey = (i: number) => (e: React.KeyboardEvent) => {
    const n = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? Math.min(2, i + 1) : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? Math.max(0, i - 1) : e.key === 'Home' ? 0 : e.key === 'End' ? 2 : -1;
    if (n < 0) return;
    e.preventDefault(); touch(); goTo(STOPS[n]);
    (e.currentTarget.parentElement?.children[n] as HTMLElement | undefined)?.focus();
  };

  return <figure className={s.exhibit} aria-labelledby='exhibit-cap'>
    <div className={s.chrome} data-enter>
      <span><b>Exhibit 01</b> · concourse.webp · 1280 × 853</span>
      <span className={s.flag}>Illustrative · edit staged for this page</span>
    </div>

    <div ref={frame} className={s.frame} onPointerDown={onFrameDown} onDragStart={e => e.preventDefault()} data-step={step} data-enter-frame>
      <i className={s.crop} aria-hidden='true'><i /><i /><i /><i /></i>
      <div className={s.plate}>
        <Image src='/images/exhibit/frame-1280.webp' alt='A busy station concourse with people crossing the floor. One group of five people near the right has been copied from beside the information booth.' fill preload draggable={false} sizes='(max-width: 640px) 160vw, (max-width: 900px) 100vw, 64vw' className={s.img} />
        <div ref={el.elaO} className={s.elaO} aria-hidden='true'><div ref={el.elaI} className={s.elaI}><Image src='/images/exhibit/ela-1280.webp' alt='' fill draggable={false} sizes='(max-width: 640px) 160vw, (max-width: 900px) 100vw, 64vw' className={s.img} /></div></div>
        <div ref={el.boxA} className={`${s.box} ${s.boxA}`} style={pct(A)} aria-hidden='true'><span>A · source</span></div>
        <div ref={el.boxB} className={`${s.box} ${s.boxB}`} style={pct(B)} aria-hidden='true'><span>B · pasted</span></div>
        <div ref={el.link} className={s.link} style={{ left: `${A.x + A.w}%`, top: `${A.y + A.h / 2}%`, width: `${B.x - A.x - A.w}%` }} aria-hidden='true'><i ref={el.line} /><em>374 px apart · same pixels</em></div>
      </div>
      <div ref={el.card} className={s.card} onPointerDown={e => e.stopPropagation()}>
        <p className={s.cardKind}>Finding · spatial</p>
        <p className={s.cardTitle}>Copied group of five people</p>
        <p ref={el.rowE} className={s.cardRow}><span>Error level</span><b>3.9× frame average</b></p>
        <p ref={el.rowM} className={s.cardRow}><span>Matches region A</span><b>0.987</b></p>
        <Link href='/evidence/EV-0149?finding=F-061' className={s.cardLink}>Open in the demo workspace <ArrowRight size={14} /></Link>
      </div>
    </div>

    <div className={s.controls} data-enter>
      <div ref={track} className={s.track} onPointerDown={onTrackDown} aria-hidden='true'>
        <i className={s.rail}><em ref={el.fill} /></i>
        {STOPS.map(x => <i key={x} className={s.tick} style={{ left: `${x * 100}%` }} />)}
        <span ref={el.head} className={s.headWrap}><span className={s.head} /></span>
      </div>
      <div className={s.steps} role='group' aria-label='Examine the exhibit'>
        {STEPS.map((x, i) => <button key={x.label} aria-pressed={step === i} onClick={() => { touch(); goTo(STOPS[i]); }} onKeyDown={onStepKey(i)} tabIndex={step === i ? 0 : -1}>
          <span>0{i + 1}</span>{x.label}
        </button>)}
      </div>
    </div>

    <figcaption id='exhibit-cap' className={s.caption} data-enter>
      <div aria-live='polite'><b>{STEPS[step].title}.</b> {STEPS[step].body}</div>
      <p className={`${s.hint} ${touched ? s.hintGone : ''}`} aria-hidden='true'><MoveHorizontal size={15} />Drag across the frame, or pick a step</p>
    </figcaption>
  </figure>;
}
