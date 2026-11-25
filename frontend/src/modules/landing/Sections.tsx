'use client';

/* The landing page after the hero: contradiction → investigation → limits → action.
   Calm sections stay static; the graph draws itself in once when it first comes into view. */
import { useRef, useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useGSAP } from '@gsap/react';
import { ArrowRight, ArrowUpRight, Check, Minus } from 'lucide-react';
import s from './sections.module.css';

gsap.registerPlugin(ScrollTrigger);

/* ── 02 · the contradiction ──────────────────────────── */
const PATCHES = [
  { src: '/images/exhibit/patch-a.webp', tag: 'A · Source', tone: 'steel', at: 'x 535 · y 534', text: 'Five people beside the information booth.' },
  { src: '/images/exhibit/patch-b.webp', tag: 'B · Copy', tone: 'alert', at: 'x 909 · y 537', text: 'The same five, 374 px to the right. Compressed on their own, then pasted.' },
  { src: '/images/exhibit/patch-diff.webp', tag: 'A − B', tone: 'gold', at: 'mean 8.9 / 255', text: 'Dark means identical. Only the blended edge of the paste differs.' },
] as const;

export function Clue() {
  return <section id='clue' className={s.clue} aria-labelledby='clue-h' data-reveal>
    <header className={s.head}>
      <p className={s.eyebrow} data-reveal-item><i />02 · The contradiction</p>
      <h2 id='clue-h' data-reveal-item>Five people, standing in two places at once.</h2>
      <p className={s.lede} data-reveal-item>Crowds never repeat themselves. When two groups match coat for coat and pose for pose, to the pixel, one of them was copied. These crops come straight from the exhibit above, enlarged five times.</p>
    </header>
    <ol className={s.sheet}>
      {PATCHES.map((p, i) => <li key={p.tag} data-reveal-item>
        <p className={s.sheetMeta}><span className={s[p.tone]}>{p.tag}</span><span>{p.at}</span></p>
        <figure className={`${s.patch} ${s['p' + p.tone]}`}>
          <Image src={p.src} alt={i === 2 ? 'Difference between the two crops: almost black inside, bright only around the edge' : `${p.tag}: five people standing together on the concourse floor`} fill sizes='(max-width: 640px) 33vw, 30vw' />
        </figure>
        <p className={s.sheetText}>{p.text}</p>
      </li>)}
    </ol>
    <p className={s.measure} data-reveal-item><span><b>0.987</b> pixel match between A and B</span><span><b>3.9×</b> the frame’s average error level inside B</span></p>
  </section>;
}

/* ── 03 · the investigation: a finding never leaves its source ── */
const GN = [
  { id: 'c', x: 320, y: 236, r: 30, kind: 'case', tone: '#e9a23b', label: 'Case NX-10483 · 5 files' },
  { id: 'f', x: 470, y: 150, r: 28, kind: 'media', src: '/images/exhibit/frame-760.webp', tone: '#f0604d', label: 'concourse.webp · Exhibit 01' },
  { id: 'a', x: 176, y: 140, r: 22, kind: 'media', src: '/images/evidence/harbor-ships-480.webp', tone: '#7fa6bf', label: 'harbor_broadcast.mp4' },
  { id: 'd', x: 150, y: 330, r: 22, kind: 'media', src: '/images/evidence/rain-street-480.webp', tone: '#8fbf7a', label: 'street_cam_03.mp4' },
  { id: 'e', x: 300, y: 400, r: 22, kind: 'media', src: '/images/evidence/escalator-480.webp', tone: '#8fbf7a', label: 'escalator_cam.mp4' },
  { id: 'b', x: 500, y: 344, r: 22, kind: 'media', src: '/images/evidence/lobby-silhouette-480.webp', tone: '#7fa6bf', label: 'lobby_cam_02.mp4' },
  { id: 'g', x: 590, y: 70, r: 11, kind: 'finding', tone: '#f0604d', label: 'Finding: copied group' },
  { id: 'h', x: 600, y: 226, r: 11, kind: 'finding', tone: '#f0604d', label: 'Finding: second JPEG save' },
  { id: 'k', x: 404, y: 448, r: 12, kind: 'meta', tone: '#7fa6bf', label: 'Encoder: Lavf (FFmpeg)' },
  { id: 'l', x: 60, y: 226, r: 13, kind: 'source', tone: '#7fa6bf', label: 'Uploader @transit_watch' },
] as const;
type EK = 'contains' | 'finding' | 'meta' | 'source';
const GE: [string, string, EK][] = [['c', 'f', 'contains'], ['c', 'a', 'contains'], ['c', 'd', 'contains'], ['c', 'e', 'contains'], ['c', 'b', 'contains'], ['f', 'g', 'finding'], ['f', 'h', 'finding'], ['f', 'k', 'meta'], ['b', 'k', 'meta'], ['l', 'f', 'source'], ['l', 'a', 'source']];
const EDGE: Record<EK, { stroke: string; op: number; dash?: string; label: string }> = {
  contains: { stroke: '#8d877c', op: .35, label: 'Belongs to the case' },
  finding: { stroke: '#f0604d', op: .9, dash: '5 5', label: 'Finding, tied to its frame' },
  meta: { stroke: '#7fa6bf', op: .75, label: 'Shared metadata' },
  source: { stroke: '#7fa6bf', op: .75, dash: '2 4', label: 'Same uploader' },
};
type N = typeof GN[number];
const bend = (a: N, b: N) => { const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2; return `M${a.x} ${a.y} Q${(mx - (b.y - a.y) * .1).toFixed(1)} ${(my + (b.x - a.x) * .1).toFixed(1)} ${b.x} ${b.y}`; };
const by = (id: string) => GN.find(n => n.id === id)!;

export function Investigation() {
  const root = useRef<HTMLElement>(null);
  const [hover, setHover] = useState<string | null>(null);
  useGSAP(() => {
    const mm = gsap.matchMedia();
    mm.add('(prefers-reduced-motion: no-preference)', () => {
      const tl = gsap.timeline({ scrollTrigger: { trigger: root.current!.querySelector('[data-graph]'), start: 'top 85%', once: true } });
      tl.fromTo('[data-gn]', { opacity: 0, scale: .6, transformOrigin: '50% 50%' }, { opacity: 1, scale: 1, duration: .7, ease: 'back.out(1.6)', stagger: .05 })
        .fromTo('[data-draw]', { strokeDashoffset: 1 }, { strokeDashoffset: 0, duration: .9, ease: 'power2.out', stagger: .05 }, .2)
        .fromTo('[data-fade]', { opacity: 0 }, { opacity: 1, duration: .6, stagger: .05 }, .6);
    });
    return () => mm.revert();
  }, { scope: root });
  const near = hover ? new Set([hover, ...GE.filter(e => e[0] === hover || e[1] === hover).flatMap(e => [e[0], e[1]])]) : null;
  const hn = GN.find(n => n.id === hover);

  return <section ref={root} id='how-it-works' className={s.graphSec} aria-labelledby='graph-h'>
    <div className={s.graphCopy} data-reveal>
      <p className={s.eyebrow} data-reveal-item><i />03 · The investigation</p>
      <h2 id='graph-h' data-reveal-item>Every finding stays tied to its source.</h2>
      <p className={s.lede} data-reveal-item>In the workspace the copied group becomes a finding. It keeps its frame, its region and the file it came from, and it links to anything that shares a source: the same uploader, the same encoder, the same edit. A lead in one file surfaces in the next.</p>
      <ul className={s.keys} data-reveal-item>
        {(['finding', 'meta', 'source'] as EK[]).map(k => <li key={k}><svg width='30' height='6' aria-hidden='true'><line x1='0' y1='3' x2='30' y2='3' stroke={EDGE[k].stroke} strokeWidth='2' strokeDasharray={EDGE[k].dash} /></svg>{EDGE[k].label}</li>)}
      </ul>
      <Link href='/graph' className={s.textCta} data-reveal-item>Open the evidence graph <ArrowRight size={16} /></Link>
    </div>
    <div className={s.graphStage}>
      <p className={s.graphTag}>Illustrative case graph</p>
      <svg data-graph viewBox='0 0 640 480' aria-label='Case graph: the exhibit, four other files, two findings, an encoder and an uploader. Tab through the nodes to read them.'>
        <defs>{GN.filter(n => n.kind === 'media').map(n => <clipPath key={n.id} id={`lg-${n.id}`}><circle cx={n.x} cy={n.y} r={n.r - 2} /></clipPath>)}</defs>
        {GE.map(([a, b, k], i) => {
          const dim = near && !(near.has(a) && near.has(b)), d = EDGE[k].dash;
          return <path key={i} {...(d ? { 'data-fade': '' } : { 'data-draw': '', pathLength: 1, strokeDasharray: 1 })} d={bend(by(a), by(b))} fill='none' stroke={EDGE[k].stroke} strokeOpacity={dim ? .08 : EDGE[k].op} strokeWidth={k === 'contains' ? 1 : 1.6} strokeDasharray={d ?? 1} className={s.edge} />;
        })}
        {GN.map(n => <g key={n.id} data-gn tabIndex={0} role='img' aria-label={n.label} className={s.gNode} onPointerEnter={() => setHover(n.id)} onPointerLeave={() => setHover(null)} onFocus={() => setHover(n.id)} onBlur={() => setHover(null)}>
          <g style={{ opacity: near && !near.has(n.id) ? .25 : 1, transition: 'opacity .2s' }}>
            {n.kind === 'case' && <><circle cx={n.x} cy={n.y} r={n.r} fill='#15110b' stroke={n.tone} strokeWidth='2' /><circle cx={n.x} cy={n.y} r={n.r - 10} fill={n.tone} opacity='.22' /></>}
            {n.kind === 'media' && <><circle cx={n.x} cy={n.y} r={n.r} fill='#050505' stroke={n.tone} strokeWidth='2' /><image href={'src' in n ? n.src : ''} x={n.x - n.r} y={n.y - n.r} width={n.r * 2} height={n.r * 2} preserveAspectRatio='xMidYMid slice' clipPath={`url(#lg-${n.id})`} /></>}
            {n.kind === 'finding' && <rect x={n.x - n.r} y={n.y - n.r} width={n.r * 2} height={n.r * 2} rx='3' transform={`rotate(45 ${n.x} ${n.y})`} fill={n.tone} stroke='#0b0a09' strokeWidth='2' />}
            {n.kind === 'meta' && <rect x={n.x - n.r} y={n.y - n.r} width={n.r * 2} height={n.r * 2} rx='4' fill='#0b0a09' stroke={n.tone} strokeWidth='1.8' />}
            {n.kind === 'source' && <polygon points={Array.from({ length: 6 }, (_, i) => `${(n.x + Math.cos(i * Math.PI / 3) * n.r).toFixed(1)},${(n.y + Math.sin(i * Math.PI / 3) * n.r).toFixed(1)}`).join(' ')} fill='#0b0a09' stroke={n.tone} strokeWidth='1.8' />}
            <circle className={s.focusRing} cx={n.x} cy={n.y} r={n.r + 7} fill='none' stroke='#e9a23b' strokeWidth='1.5' />
          </g>
        </g>)}
      </svg>
      <p className={s.hoverLabel} aria-hidden='true'>{hn?.label ?? 'Hover, tap or tab through the nodes'}</p>
    </div>
  </section>;
}

/* ── 04 · the limits ──────────────────────────────────── */
const SHOWN = ['One group of five people was copied within this frame.', 'The copy was compressed on its own before it was pasted.', 'Where the copy sits, and where it came from.'];
const NOT_SHOWN = ['Who made the edit, or why.', 'That the rest of the crowd is genuine. Busy textures glow in an error-level map too, so a glow alone is never called a finding: it needs a match.', 'Anything about a real event. We staged this edit ourselves to show the method.'];

export function Limits() {
  return <section id='research' className={s.limits} aria-labelledby='limits-h' data-reveal>
    <div className={s.limitsHead}>
      <p className={s.eyebrow} data-reveal-item><i />04 · The limits</p>
      <h2 id='limits-h' data-reveal-item>What this proves, and what it doesn’t.</h2>
    </div>
    <div className={s.lists}>
      <div data-reveal-item><h3>Shown by this example</h3><ul>{SHOWN.map(t => <li key={t}><Check size={16} className={s.yes} aria-hidden='true' />{t}</li>)}</ul></div>
      <div data-reveal-item><h3>Not shown</h3><ul>{NOT_SHOWN.map(t => <li key={t}><Minus size={16} className={s.no} aria-hidden='true' />{t}</li>)}</ul></div>
    </div>
    <div className={s.about} data-reveal-item>
      <h3>About this example</h3>
      <p>The photograph is by Nicolai Berntsen (Unsplash License). We copied one group, saved it alone at JPEG quality 28, pasted it 374 px to the right and saved the frame at quality 90. The error-level map is that file re-saved at quality 75 and compared, pixel by pixel. SHA-256 of the image on this page: <code>47c37bc7…38ebfaef6b</code>.</p>
      <p>NEXTRON’s method draws on FaceForensics++, DFDC and Deepfake-Eval-2024. Product benchmarks are not yet published, and when evidence is thin or conflicting the assessment stays inconclusive.</p>
    </div>
  </section>;
}

/* ── 05 · the action ──────────────────────────────────── */
export function FinalCta() {
  return <section className={s.final} aria-labelledby='final-h' data-reveal>
    <svg className={s.iris} viewBox='0 0 200 200' aria-hidden='true'>
      <circle cx='100' cy='100' r='92' fill='none' stroke='#e9a23b' strokeOpacity='.22' />
      <g>{Array.from({ length: 6 }, (_, i) => <path key={i} d='M100 8 L146 92' stroke='#e9a23b' strokeWidth='1.2' strokeOpacity='.4' transform={`rotate(${i * 60} 100 100)`} />)}</g>
      <circle cx='100' cy='100' r='16' fill='none' stroke='#e9a23b' strokeOpacity='.55' />
    </svg>
    <p className={s.eyebrow} data-reveal-item style={{ justifyContent: 'center' }}><i />05 · Your turn</p>
    <h2 id='final-h' data-reveal-item>Find the frame where <br />the story changes.</h2>
    <p className={s.lede} data-reveal-item style={{ marginInline: 'auto', textAlign: 'center' }}>Open the demo workspace: sample cases in the real interface, this exhibit among them. Nothing to install, no account.</p>
    <div className={s.finalActions} data-reveal-item>
      <Link href='/dashboard' className={s.cta}>Open the analyzer <ArrowUpRight size={18} /></Link>
      <Link href='/evidence/EV-0149?finding=F-061' className={s.textCta}>Start with this exhibit <ArrowRight size={16} /></Link>
    </div>
  </section>;
}
