'use client';

/* The hero console: a staged analysis run.
   Performance model
   - One requestAnimationFrame engine per console. Per-frame values (scan position, reveal, progress bar,
     playhead, timecode, divider spring) are written straight to transforms and text nodes through refs:
     no React render, no layout, no paint, only compositing.
   - React re-renders only on discrete events: a stage completes, a log line lands, the run finishes.
   - Every tint, grayscale and heat grid is baked into WebP (public/images/console), so nothing is
     filtered or blended live.
   - The engine sleeps while the console is off screen or the tab is hidden. */

import { useCallback, useEffect, useRef, useState } from 'react';
import Image from 'next/image';
import gsap from 'gsap';
import { motion, AnimatePresence } from 'framer-motion';
import { ImageIcon, SquarePlay, AudioLines, TriangleAlert, Crosshair, Layers3, Tag, Check, Pause, Play, RotateCcw, LoaderCircle } from 'lucide-react';
import s from './console.module.css';
import { isReady } from './ready';

const IMG = '/images/console';
const DURATION = 48; // seconds of the staged clip
const FPS = 30;

export const modes = [
  {
    name: 'Image', icon: ImageIcon, branch: 'Spatial', tone: 'alert', title: 'Manipulation detected', confidence: 96.3,
    region: 'Face (partial)', type: 'Face swap', flag: [38, 52], seconds: 4.6,
    stages: ['Seal original · SHA-256', 'Sample 1,440 frames', 'Track face', 'Spatial branch · seams + texture', 'Fuse evidence'],
    log: ['sha256 9f4e2a6b…d4e5 sealed', '1,440 frames @ 30 fps', 'face_01 tracked · 0.99', 'seam score 0.91 · left jaw', 'texture Δ 0.34 · cheek', 'verdict: manipulated · 96.3%'],
  },
  {
    name: 'Video', icon: SquarePlay, branch: 'Temporal', tone: 'alert', title: 'Frame splice detected', confidence: 88.1,
    region: '00:23.7 – 00:24.1', type: 'Frame insertion', flag: [49, 51], seconds: 3.8,
    stages: ['Seal original · SHA-256', 'Sample 1,440 frames', 'Estimate motion vectors', 'Temporal branch · continuity', 'Fuse evidence'],
    log: ['sha256 9f4e2a6b…d4e5 sealed', '1,440 frames @ 30 fps', 'optical flow · 1,439 pairs', 'break @ F0712 → F0724', 'cut score 0.88', 'verdict: splice · 88.1%'],
  },
  {
    name: 'Audio', icon: AudioLines, branch: 'Audio-visual', tone: 'warn', title: 'Alignment inconclusive', confidence: 61.4,
    region: 'Speech, 00:21 – 00:27', type: 'Lip-sync drift', flag: [43, 57], seconds: 3.8,
    stages: ['Seal original · SHA-256', 'Extract audio · 48 kHz', 'Align speech to mouth', 'Audio-visual branch · sync', 'Fuse evidence'],
    log: ['sha256 9f4e2a6b…d4e5 sealed', 'audio 48 kHz · mono', '6 words aligned', 'mouth trails audio +140 ms', 'codec delay possible', 'verdict: inconclusive · 61.4%'],
  },
] as const;

/* Work is not linear: each stage has its own share of the run and eases in and out inside it,
   the way a real pipeline speeds up on cheap steps and slows on the expensive branch. */
const WEIGHTS = [.1, .18, .17, .38, .17];
const CUM = WEIGHTS.reduce<number[]>((a, w) => [...a, (a.at(-1) ?? 0) + w], []);
const smooth = (x: number) => x * x * (3 - 2 * x);
function work(u: number) { // wall-clock share 0..1 -> completed work 0..1
  const t = Math.min(1, Math.max(0, u)) * CUM.length;
  const i = Math.min(CUM.length - 1, Math.floor(t));
  return (i ? CUM[i - 1] : 0) + WEIGHTS[i] * smooth(t - i);
}
const stageOf = (p: number) => { const i = CUM.findIndex(c => p < c - 1e-6); return i === -1 ? CUM.length : i; };

function Ring({ value, tone, reduced }: { value: number; tone: string; reduced: boolean }) {
  const arc = useRef<SVGCircleElement>(null);
  const label = useRef<HTMLElement>(null);
  const C = 2 * Math.PI * 9;
  useEffect(() => {
    const paint = (v: number) => {
      arc.current?.setAttribute('stroke-dashoffset', String(C * (1 - v / 100)));
      if (label.current) label.current.textContent = `${v.toFixed(1)}%`;
    };
    if (reduced) { paint(value); return; }
    const o = { v: 0 };
    const t = gsap.to(o, { v: value, duration: 1.2, ease: 'expo.out', onUpdate: () => paint(o.v) });
    return () => { t.kill(); };
  }, [value, reduced, C]);
  return <span className={s.ring} data-tone={tone}>
    <svg viewBox='0 0 24 24' aria-hidden='true'><circle cx='12' cy='12' r='9' /><circle ref={arc} cx='12' cy='12' r='9' strokeDasharray={C} strokeDashoffset={C} /></svg>
    <b ref={label} aria-label={`${value}%`}>0.0%</b>
  </span>;
}

const pad = (n: number, w = 2) => String(n).padStart(w, '0');

export default function AnalysisConsole({ mode, setMode, reduced, running, setRunning }: {
  mode: number; setMode: (i: number) => void; reduced: boolean; running: boolean; setRunning: (v: boolean) => void;
}) {
  const m = modes[mode];
  const [stage, setStage] = useState(reduced ? 5 : 0);   // 0..5, 5 = done
  const [logCount, setLogCount] = useState(reduced ? 6 : 1);
  const [run, setRun] = useState(0);
  const done = stage >= 5;

  const root = useRef<HTMLDivElement>(null);
  const r = {
    scan: useRef<HTMLDivElement>(null), revOuter: useRef<HTMLDivElement>(null), revInner: useRef<HTMLDivElement>(null),
    splitOuter: useRef<HTMLDivElement>(null), splitInner: useRef<HTMLDivElement>(null), divider: useRef<HTMLDivElement>(null),
    bar: useRef<HTMLElement>(null), pct: useRef<HTMLElement>(null), buffer: useRef<HTMLElement>(null),
    playhead: useRef<HTMLElement>(null), tc: useRef<HTMLElement>(null), frame: useRef<HTMLElement>(null),
  };
  const live = useRef({ running, reduced, start: 0, elapsed: 0, seconds: m.seconds, p: reduced ? 1 : 0, stage: 0, log: 1, clock: 18, lastFrame: -1, split: 50, splitV: 0, target: 50, visible: true });
  live.current.running = running; live.current.reduced = reduced; live.current.seconds = m.seconds;

  // a new run on every mode switch or "Run again"
  useEffect(() => {
    const L = live.current;
    L.elapsed = 0; L.p = reduced ? 1 : 0; L.stage = reduced ? 5 : 0; L.log = reduced ? 6 : 1;
    setStage(L.stage); setLogCount(L.log);
  }, [mode, run, reduced]);

  useEffect(() => {
    const L = live.current;
    let raf = 0, last = performance.now();
    // write a transform only when it changes: an unchanged write still invalidates style
    const memo = new WeakMap<HTMLElement, string>();
    const set = (el: HTMLElement | null, v: string) => { if (el && memo.get(el) !== v) { memo.set(el, v); el.style.transform = v; } };

    const frame = (now: number) => {
      const dt = Math.min(.05, (now - last) / 1000); last = now;
      const moving = L.running && !L.reduced && L.visible && isReady(); // nothing runs under the entry loader

      // 1 · the analysis run
      if (L.p < 1 && moving) {
        L.elapsed += dt;
        const u = Math.max(0, L.elapsed - .25) / L.seconds; // short settle before work starts
        L.p = work(u);
        const st = u >= 1 ? 5 : stageOf(L.p);
        if (st !== L.stage) { L.stage = st; setStage(st); }
        const lg = Math.min(6, 1 + Math.floor(L.p * 5.2));
        if (lg !== L.log) { L.log = lg; setLogCount(lg); }
        if (u >= 1) L.p = 1;
      }
      const p = L.p, rev = p >= 1 ? 1 : p;
      const q = (x: number) => Math.round(x * 1e4) / 100; // percent, 0.01 steps
      set(r.scan.current, `translate3d(0, ${q(rev)}%, 0)`);
      set(r.revOuter.current, `translate3d(0, ${q(rev - 1)}%, 0)`);
      set(r.revInner.current, `translate3d(0, ${q(1 - rev)}%, 0)`);
      set(r.bar.current, `scaleX(${q(p) / 100})`);
      set(r.buffer.current, `scaleX(${q(p) / 100})`);
      if (r.pct.current) { const t = `${Math.round(p * 100)}%`; if (r.pct.current.textContent !== t) r.pct.current.textContent = t; }

      // 2 · divider: critically damped spring toward the pointer (no overshoot, no lag felt)
      const k = 420, c = 2 * Math.sqrt(k);
      const a = -k * (L.split - L.target) - c * L.splitV;
      L.splitV += a * dt; L.split += L.splitV * dt;
      if (Math.abs(L.split - L.target) < .01 && Math.abs(L.splitV) < .01) { L.split = L.target; L.splitV = 0; }
      const sp = Math.round(L.split * 100) / 100;
      set(r.splitOuter.current, `translate3d(${sp}%, 0, 0)`);
      set(r.splitInner.current, `translate3d(${-sp}%, 0, 0)`);
      set(r.divider.current, `translate3d(${sp}%, 0, 0)`);

      // 3 · the clip keeps playing: playhead, frame number, timecode (text only when the frame changes)
      if (moving) L.clock = (L.clock + dt) % DURATION;
      set(r.playhead.current, `translate3d(${q(L.clock / DURATION)}%, 0, 0)`);
      const f = Math.floor(L.clock * FPS);
      if (f !== L.lastFrame) {
        L.lastFrame = f;
        if (r.frame.current) r.frame.current.textContent = `F ${pad(f, 4)}`;
        if (r.tc.current) r.tc.current.textContent = `00:${pad(Math.floor(L.clock))}.${pad(Math.floor((f % FPS) / FPS * 100))}`;
      }
      raf = requestAnimationFrame(frame);
    };

    const io = new IntersectionObserver(([e]) => { L.visible = e.isIntersecting && document.visibilityState === 'visible'; }, { rootMargin: '80px' });
    if (root.current) io.observe(root.current);
    const vis = () => { L.visible = document.visibilityState === 'visible'; last = performance.now(); };
    document.addEventListener('visibilitychange', vis);
    raf = requestAnimationFrame(frame);
    return () => { cancelAnimationFrame(raf); io.disconnect(); document.removeEventListener('visibilitychange', vis); };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const onSplit = useCallback((v: number) => {
    live.current.target = v;
    if (live.current.reduced) { live.current.split = v; live.current.splitV = 0; }
  }, []);

  const tracked = stage >= 3;
  const logs = m.log.slice(0, logCount).slice(-4);
  const logStart = Math.max(0, logCount - 4);

  return <div ref={root} className={s.console} data-console>
    <span className={s.glow} aria-hidden='true' />
    <div className={s.body}>
      <div className={s.rail} role='tablist' aria-label='Analysis mode' data-rail>
        {modes.map((item, i) => <button key={item.name} role='tab' aria-selected={mode === i} onClick={() => setMode(i)} className={mode === i ? s.railOn : ''}><item.icon size={24} strokeWidth={1.6} /><span>{item.name}</span></button>)}
      </div>

      <div className={s.viewer}>
        <div className={s.stage}>
          <Image src={`${IMG}/frame.webp`} alt='Staged interview frame under analysis' fill priority sizes='(max-width: 700px) 86vw, 340px' className={s.img} />
          {/* analysis layer: horizontal split and vertical reveal, each a pair of opposite transforms */}
          <div ref={r.splitOuter} className={s.clip} aria-hidden='true'><div ref={r.splitInner} className={s.clipInner}>
            <div ref={r.revOuter} className={s.clip}><div ref={r.revInner} className={s.clipInner}>
              {[0, 1, 2].map(k => <Image key={k} src={`${IMG}/heat-${k}.webp`} alt='' fill priority={k === 0} sizes='(max-width: 700px) 86vw, 340px' className={`${s.img} ${s.heatLayer} ${k === mode ? s.heatOn : ''}`} />)}
            </div></div>
          </div></div>
          <div className={`${s.track} ${tracked ? s.locked : ''}`} aria-hidden='true'><div className={s.trackInner}><i /><i /><i /><i /></div><span>{tracked ? 'FACE_01 · 0.99' : 'SEARCHING'}</span></div>
          <div className={`${s.roi} ${s.roiJaw} ${done && mode === 0 ? s.roiOn : ''}`} aria-hidden='true'><span>R1 · seam</span></div>
          <div className={`${s.roi} ${s.roiMouth} ${done && mode === 2 ? s.roiOn : ''}`} aria-hidden='true'><span>+140 ms</span></div>
          <div ref={r.scan} className={`${s.scan} ${done ? s.scanOff : ''}`} aria-hidden='true' />
          <div ref={r.divider} className={`${s.dividerTrack} ${done ? s.dividerOn : ''}`} aria-hidden='true'><div className={s.divider}><span /></div></div>
          <input className={s.slider} type='range' min='5' max='95' defaultValue={50} disabled={!done} onInput={e => onSplit(Number((e.target as HTMLInputElement).value))} aria-label='Move the divider between the original and the analysis' />
          <span className={s.hud}><b className={s.rec} />LIVE · {m.branch}</span>
          <span className={s.stamp}><b ref={r.frame}>F 0540</b><b ref={r.tc}>00:18.00</b></span>
        </div>
        <div className={s.timeline} aria-hidden='true'>
          <i ref={r.buffer} className={s.buffer} />
          <i className={`${s.flag} ${done ? s.flagOn : ''}`} data-tone={m.tone} style={{ left: `${m.flag[0]}%`, width: `${m.flag[1] - m.flag[0]}%` }} />
          <i ref={r.playhead} className={s.playhead} />
        </div>
      </div>

      <div className={s.panel}>
        <AnimatePresence mode='wait' initial={false}>
          {!done ? <motion.div key={'scan' + mode + run} className={s.inner} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: .18 }}>
            <h2 className={s.headScan}><LoaderCircle size={18} className={s.spin} />Analyzing interview_clip.mp4<b ref={r.pct}>0%</b></h2>
            <i className={s.bar}><em ref={r.bar} /></i>
            <ol className={s.stages}>{m.stages.map((st, i) => <li key={st} data-state={i < stage ? 'done' : i === stage ? 'run' : 'wait'}><span>{i < stage ? <Check size={13} /> : i === stage ? <LoaderCircle size={13} className={s.spin} /> : null}</span>{st}</li>)}</ol>
            <div className={s.log}>{logs.map((l, i) => <p key={l} className={i === logs.length - 1 ? s.logNew : ''}><b>{`00:0${logStart + i + 1}`}</b>{l}</p>)}</div>
          </motion.div>
            : <motion.div key={'done' + mode + run} className={s.inner} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: .3, ease: [.22, 1, .36, 1] }}>
              <h2 className={s.head} data-tone={m.tone}><TriangleAlert size={20} strokeWidth={1.8} />{m.title}</h2>
              <dl className={s.facts}>
                <div><dt><Crosshair size={16} />Confidence</dt><dd><Ring value={m.confidence} tone={m.tone} reduced={reduced} /></dd></div>
                <div><dt><Layers3 size={16} />Manipulated region</dt><dd>{m.region}</dd></div>
                <div><dt><Tag size={16} />Type</dt><dd>{m.type}</dd></div>
              </dl>
              <div className={s.thumbs}>{[['Original', 'thumb-frame'], ['Heat map', `thumb-heat-${mode}`], ['Region mask', 'thumb-mask']].map(([label, file], i) => <motion.figure key={label} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: .15 + i * .08, duration: .35, ease: [.22, 1, .36, 1] }}>
                <div className={i === 2 ? s.mask : ''} data-mode={mode}><Image src={`${IMG}/${file}.webp`} alt='' fill sizes='110px' className={s.img} /></div><figcaption>{label}</figcaption></motion.figure>)}</div>
            </motion.div>}
        </AnimatePresence>
      </div>
    </div>

    <div className={s.foot}>
      <span className={s.file}>interview_clip.mp4 · 1920×1080 · 30 fps</span>
      <span className={s.note}>Illustrative findings · staged media</span>
      <div className={s.controls}>
        <button type='button' onClick={() => setRun(n => n + 1)} disabled={!done || reduced}><RotateCcw size={13} />Run again</button>
        <button type='button' onClick={() => setRunning(!running)} aria-pressed={!running} disabled={reduced}>{running && !reduced ? <Pause size={13} /> : <Play size={13} />}{reduced ? 'Reduced motion' : running ? 'Pause' : 'Play'}</button>
      </div>
    </div>
  </div>;
}
