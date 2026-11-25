'use client';

/* Landing scenes below the hero.
   - Dissection: a pinned, scroll-scrubbed scene. One frame is sealed, heat-mapped, split into its neighbouring
     frames, matched against its audio, then fused into a verdict. Scroll position IS the timeline (GSAP scrub),
     so it never runs ahead of the reader; everything moves by transform and opacity only.
   - Statement: words light up as they cross the middle of the screen.
   - GraphShowcase: a living evidence graph; nodes drift on slow sine orbits, pulses run along suspicious links.
   - FinalCta: the closing invitation, with a turning aperture.
   Under prefers-reduced-motion every scene renders its finished state, nothing pinned. */
import { useEffect, useRef, useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useGSAP } from '@gsap/react';
import { ArrowRight, ArrowUpRight, Check, ShieldCheck } from 'lucide-react';
import s from './landing-sections.module.css';

gsap.registerPlugin(ScrollTrigger);

const CHAPTERS = [
  ['Seal the original', 'The file is hashed the moment it arrives. Every later step works on a copy, so the original can always be checked.'],
  ['Where the pixels lie', 'The spatial branch maps texture, lighting and blending. A seam along the jaw lights up where the face was stitched in.'],
  ['When the frames break', 'The temporal branch follows motion from frame to frame. Twelve frames step off the path and back again.'],
  ['Whether the voice fits the face', 'Mouth shapes are matched to the audio, word by word. They trail the sound by 140 milliseconds.'],
  ['One reviewable verdict', 'The branches are fused into plausible ranges, never a single number. Each one links back to the frames that support it.'],
] as const;
const HASH = '9f4e2a6b 8d9c7d0f 6a3b1e9a 2b7d4e5f 8c9d0a1b';
const CARDS = [-2, -1, 0, 1, 2];
const BARS = Array.from({ length: 34 }, (_, i) => 22 + Math.round(Math.abs(Math.sin(i * 1.7) * Math.cos(i * .53)) * 74));

export function Dissection() {
  const root = useRef<HTMLElement>(null);
  useGSAP(() => {
    const mm = gsap.matchMedia();
    mm.add('(prefers-reduced-motion: no-preference)', () => {
      const q = gsap.utils.selector(root);
      root.current!.dataset.live = '1';
      const tl = gsap.timeline({ defaults: { ease: 'power2.inOut', duration: 1 }, scrollTrigger: { trigger: root.current, start: 'top top', end: '+=420%', scrub: .7, pin: true, anticipatePin: 1 } });
      const ch = q('[data-ch]'), dots = q('[data-dot]');
      gsap.set(ch, { autoAlpha: 0, y: 24 }); gsap.set(ch[0], { autoAlpha: 1, y: 0 });
      const swap = (i: number, at: number) => {
        tl.to(ch[i - 1], { autoAlpha: 0, y: -24, duration: .4 }, at).to(ch[i], { autoAlpha: 1, y: 0, duration: .5 }, at + .25)
          .to(dots[i], { scale: 1, backgroundColor: '#e9a23b', duration: .3 }, at + .25);
      };
      // 0 · seal
      tl.fromTo(q('[data-seal]'), { scaleX: .15 }, { scaleX: 1, duration: .45, ease: 'power3.out' }, 0)
        .fromTo(q('[data-hash] span'), { autoAlpha: .25 }, { autoAlpha: 1, stagger: .04, duration: .15 }, 0)
        .fromTo(q('[data-stamp]'), { scale: 1.3, autoAlpha: 0 }, { scale: 1, autoAlpha: 1, duration: .3, ease: 'back.out(2)' }, .35);
      // 1 · spatial heat wipe + region
      swap(1, 1);
      tl.to(q('[data-sealband]'), { autoAlpha: 0, duration: .3 }, 1)
        .fromTo(q('[data-heat-o]'), { xPercent: -100 }, { xPercent: 0, duration: .9 }, 1.1)
        .fromTo(q('[data-heat-i]'), { xPercent: 100 }, { xPercent: 0, duration: .9 }, 1.1)
        .fromTo(q('[data-region]'), { autoAlpha: 0, scale: 1.5 }, { autoAlpha: 1, scale: 1, duration: .4, ease: 'power3.out' }, 1.75);
      // 2 · temporal: the frame splits into its neighbours
      swap(2, 2.2);
      tl.to(q('[data-region], [data-heat-o]'), { autoAlpha: 0, duration: .3 }, 2.2)
        .to(q('[data-base]'), { autoAlpha: .12, scale: .92, duration: .5 }, 2.25)
        .fromTo(q('[data-card]'), { autoAlpha: 0, xPercent: 0, rotateY: 0, z: 0 }, {
          autoAlpha: 1, duration: .8, ease: 'power3.out', stagger: { each: .03, from: 'center' },
          xPercent: (i: number) => CARDS[i] * 74, rotateY: (i: number) => CARDS[i] * -16, z: (i: number) => -Math.abs(CARDS[i]) * 90,
        }, 2.35)
        .fromTo(q('[data-cut]'), { autoAlpha: 0, y: 8 }, { autoAlpha: 1, y: 0, duration: .3 }, 2.9);
      // 3 · audio-visual
      swap(3, 3.4);
      tl.to(q('[data-card]'), { xPercent: 0, rotateY: 0, z: 0, autoAlpha: 0, duration: .5, stagger: { each: .02, from: 'edges' } }, 3.4)
        .to(q('[data-cut]'), { autoAlpha: 0, duration: .2 }, 3.4)
        .to(q('[data-base]'), { autoAlpha: 1, scale: 1, duration: .5 }, 3.55)
        .fromTo(q('[data-wave]'), { autoAlpha: 0 }, { autoAlpha: 1, duration: .2 }, 3.7)
        .fromTo(q('[data-bar]'), { scaleY: .05 }, { scaleY: 1, duration: .5, stagger: .008, ease: 'power3.out' }, 3.7)
        .fromTo(q('[data-lag]'), { autoAlpha: 0, scaleX: 0 }, { autoAlpha: 1, scaleX: 1, duration: .35 }, 4.1)
        .fromTo(q('[data-mouth]'), { autoAlpha: 0, scale: 1.4 }, { autoAlpha: 1, scale: 1, duration: .35 }, 4.1);
      // 4 · fused verdict
      swap(4, 4.6);
      tl.to(q('[data-wave], [data-mouth]'), { autoAlpha: 0, duration: .3 }, 4.6)
        .to(q('[data-heat-o]'), { autoAlpha: .55, duration: .4 }, 4.7)
        .to(q('[data-region]'), { autoAlpha: 1, duration: .3 }, 4.75)
        .fromTo(q('[data-verdict]'), { autoAlpha: 0, y: 30 }, { autoAlpha: 1, y: 0, duration: .5, ease: 'power3.out' }, 4.8)
        .fromTo(q('[data-range]'), { scaleX: 0 }, { scaleX: 1, duration: .5, stagger: .08, ease: 'power3.out' }, 5)
        .to({}, { duration: .4 });
      return () => { delete root.current?.dataset.live; };
    });
    return () => mm.revert();
  }, { scope: root });

  return <section ref={root} id='how-it-works' className={s.dissect} aria-labelledby='dissect-h'>
    <div className={s.dissectIn}>
      <div className={s.story}>
        <p className={s.eyebrow}><i />The investigation path / 02</p>
        <h2 id='dissect-h'>Watch a fake <br />come apart.</h2>
        <div className={s.chapters}>
          {CHAPTERS.map(([t, d], i) => <article key={t} data-ch className={s.chapter}><span className={s.num}>0{i + 1}</span><h3>{t}</h3><p>{d}</p></article>)}
        </div>
        <div className={s.dots} aria-hidden='true'>{CHAPTERS.map((_, i) => <i key={i} data-dot style={i === 0 ? { transform: 'scale(1)', background: '#e9a23b' } : undefined} />)}</div>
      </div>

      <div className={s.stageWrap} aria-hidden='true'>
        <div className={s.stage}>
          <div className={s.corners}><i /><i /><i /><i /></div>
          <div data-base className={s.base}><Image src='/images/console/frame.webp' alt='' fill sizes='(max-width: 900px) 80vw, 40vw' style={{ objectFit: 'cover' }} /></div>
          <div data-heat-o className={s.heatO}><div data-heat-i className={s.heatI}><Image src='/images/console/heat-0.webp' alt='' fill sizes='(max-width: 900px) 80vw, 40vw' style={{ objectFit: 'cover' }} /></div></div>
          <div data-region className={s.region} style={{ left: '30%', top: '54%', width: '22%', height: '18%' }}><span>Blending seam · 0.91</span></div>
          <div data-mouth className={`${s.region} ${s.mouth}`} style={{ left: '39%', top: '61%', width: '22%', height: '10%', borderColor: '#7fa6bf' }}><span style={{ background: '#7fa6bf', color: '#0b1620' }}>+140 ms</span></div>
          {CARDS.map((c, i) => <div key={c} data-card className={`${s.card} ${c === 0 ? s.cardCut : ''}`} style={{ zIndex: 10 - Math.abs(c) }}>
            <Image src='/images/console/thumb-frame.webp' alt='' fill sizes='160px' style={{ objectFit: 'cover', objectPosition: `${50 + c * 4}% ${30 + Math.abs(c) * 2}%` }} />
            <small>F {String(709 + i * 3).padStart(4, '0')}</small>
          </div>)}
          <p data-cut className={s.cut}>Frames 712 to 724 replaced</p>
          <div data-sealband className={s.sealBand}>
            <i data-seal />
            <p data-hash>{HASH.split(' ').map(h => <span key={h}>{h}</span>)}</p>
            <b data-stamp><ShieldCheck size={15} />SHA-256 sealed</b>
          </div>
          <div data-wave className={s.wave}>
            <p><span>Audio</span><span className={s.bars}>{BARS.map((h, i) => <i key={i} data-bar style={{ height: `${h}%` }} />)}</span></p>
            <p><span>Mouth</span><span className={`${s.bars} ${s.barsLag}`}>{BARS.map((h, i) => <i key={i} data-bar style={{ height: `${BARS[(i + 32) % 34]}%` }} />)}</span></p>
            <em data-lag />
          </div>
          <div data-verdict className={s.verdict}>
            <p className={s.vHead}>Fused assessment</p>
            {[['Localized manipulation', 38, 56, true], ['Authentic', 20, 35, false], ['Inconclusive', 18, 34, false]].map(([l, a, b, lead]) => <div key={l as string} className={`${s.vRow} ${lead ? s.vLead : ''}`}><span>{l}</span><b>{a}–{b}%</b><i><em data-range style={{ left: `${a}%`, width: `${(b as number) - (a as number)}%` }} /></i></div>)}
          </div>
        </div>
      </div>
    </div>
  </section>;
}

export function Statement() {
  const root = useRef<HTMLElement>(null);
  const words = 'A deepfake hides in a handful of frames. NEXTRON finds them, shows you why, and keeps every finding tied to the pixels that prove it.'.split(' ');
  useGSAP(() => {
    const mm = gsap.matchMedia();
    mm.add('(prefers-reduced-motion: no-preference)', () => {
      gsap.fromTo(gsap.utils.toArray<HTMLElement>('[data-w]', root.current), { opacity: .16 }, { opacity: 1, ease: 'none', stagger: .1, scrollTrigger: { trigger: root.current, start: 'top 75%', end: 'bottom 55%', scrub: true } });
    });
    return () => mm.revert();
  }, { scope: root });
  return <section ref={root} className={s.statement} aria-label='What NEXTRON does'>
    <p>{words.map((w, i) => <span key={i} data-w className={w === 'NEXTRON' ? s.brandWord : undefined}>{w} </span>)}</p>
  </section>;
}

/* hand-placed layout (viewBox 640 × 480); each node drifts on its own slow orbit */
const GN = [
  { id: 'c', x: 320, y: 236, r: 30, kind: 'case', tone: '#f0604d', label: 'Corvane interview' },
  { id: 'a', x: 188, y: 150, r: 24, kind: 'media', img: 'interview', tone: '#f0604d', label: 'interview_clip.mp4' },
  { id: 'b', x: 466, y: 138, r: 22, kind: 'media', img: 'lobby-silhouette', tone: '#7fa6bf', label: 'lobby_cam_02.mp4' },
  { id: 'd', x: 150, y: 330, r: 22, kind: 'media', img: 'rain-street', tone: '#8fbf7a', label: 'street_cam_03.mp4' },
  { id: 'e', x: 300, y: 392, r: 22, kind: 'media', img: 'escalator', tone: '#8fbf7a', label: 'escalator_cam.mp4' },
  { id: 'f', x: 500, y: 330, r: 24, kind: 'media', img: 'station-concourse', tone: '#f0604d', label: 'station_concourse.mp4' },
  { id: 'g', x: 96, y: 92, r: 11, kind: 'finding', tone: '#f0604d', label: 'Blending seam' },
  { id: 'h', x: 236, y: 64, r: 11, kind: 'finding', tone: '#f0604d', label: 'Frames replaced' },
  { id: 'i', x: 588, y: 412, r: 11, kind: 'finding', tone: '#f0604d', label: 'Repeated figures' },
  { id: 'j', x: 566, y: 70, r: 11, kind: 'finding', tone: '#7fa6bf', label: 'Eleven seconds missing' },
  { id: 'k', x: 418, y: 432, r: 12, kind: 'meta', tone: '#7fa6bf', label: 'Encoder: FFmpeg' },
  { id: 'l', x: 60, y: 226, r: 13, kind: 'source', tone: '#f0604d', label: '@newsdesk_live' },
] as const;
const GE: [string, string, 'c' | 'p' | 'm' | 'd'][] = [['c', 'a', 'c'], ['c', 'b', 'c'], ['c', 'd', 'c'], ['c', 'e', 'c'], ['a', 'g', 'c'], ['a', 'h', 'c'], ['b', 'j', 'c'], ['f', 'i', 'c'], ['g', 'i', 'p'], ['h', 'g', 'p'], ['a', 'k', 'm'], ['f', 'k', 'm'], ['l', 'a', 'd'], ['l', 'f', 'd'], ['d', 'e', 'd']];
const EDGE: Record<'c' | 'p' | 'm' | 'd', { stroke: string; op: number; dash?: string }> = { c: { stroke: '#8d877c', op: .3 }, p: { stroke: '#f0604d', op: .9, dash: '6 6' }, m: { stroke: '#7fa6bf', op: .7 }, d: { stroke: '#8fbf7a', op: .6 } };

export function GraphShowcase() {
  const svg = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<string | null>(null);
  useEffect(() => {
    const el = svg.current!; let raf = 0, on = false, t0 = performance.now();
    const still = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const nodes = GN.map((n, i) => ({ ...n, ax: 6 + (i % 3) * 3, ay: 5 + (i % 4) * 2.5, w: .00028 + (i % 5) * .00005, ph: i * 1.7 }));
    const nEls = nodes.map(n => el.querySelector<SVGGElement>(`[data-n="${n.id}"]`));
    const eEls = GE.map((_, i) => el.querySelector<SVGPathElement>(`[data-e="${i}"]`));
    const at = (n: typeof nodes[number], t: number) => ({ x: n.x + Math.sin(t * n.w + n.ph) * n.ax, y: n.y + Math.cos(t * n.w * 1.3 + n.ph) * n.ay });
    const draw = (t: number) => {
      const p = new Map<string, { x: number; y: number }>(nodes.map(n => [n.id, at(n, t)]));
      nodes.forEach((n, i) => { const q = p.get(n.id)!; nEls[i]?.setAttribute('transform', `translate(${q.x.toFixed(1)} ${q.y.toFixed(1)})`); });
      GE.forEach(([a, b], i) => { const A = p.get(a)!, B = p.get(b)!, mx = (A.x + B.x) / 2, my = (A.y + B.y) / 2; eEls[i]?.setAttribute('d', `M${A.x.toFixed(1)} ${A.y.toFixed(1)} Q${(mx - (B.y - A.y) * .1).toFixed(1)} ${(my + (B.x - A.x) * .1).toFixed(1)} ${B.x.toFixed(1)} ${B.y.toFixed(1)}`); });
    };
    const loop = (now: number) => { draw(now - t0); if (on) raf = requestAnimationFrame(loop); };
    draw(0);
    if (still) return;
    const io = new IntersectionObserver(([e]) => { on = e.isIntersecting; if (on) { cancelAnimationFrame(raf); raf = requestAnimationFrame(loop); } });
    io.observe(el);
    return () => { io.disconnect(); cancelAnimationFrame(raf); };
  }, []);
  const near = hover ? new Set([hover, ...GE.filter(e => e[0] === hover || e[1] === hover).flatMap(e => [e[0], e[1]])]) : null;
  const hn = GN.find(n => n.id === hover);

  return <section className={s.graphSec} aria-labelledby='graph-h'>
    <div className={s.graphCopy} data-reveal>
      <p className={s.eyebrow} data-reveal-item><i />The evidence graph / 03</p>
      <h2 id='graph-h' data-reveal-item>See the case the way <br />the evidence connects.</h2>
      <p className={s.lede} data-reveal-item>Every file, finding and source becomes a node. NEXTRON links the ones that share a manipulation pattern, a clock that lies or a common uploader, so a lead in one case surfaces in another.</p>
      <ul className={s.keys} data-reveal-item>
        <li><i style={{ borderColor: '#f0604d', borderStyle: 'dashed' }} />Shared manipulation pattern</li>
        <li><i style={{ borderColor: '#7fa6bf' }} />Metadata in common</li>
        <li><i style={{ borderColor: '#8fbf7a' }} />Same source</li>
      </ul>
      <Link href='/workspace' className={s.textCta} data-reveal-item>Open the evidence graph <ArrowRight size={16} /></Link>
    </div>
    <div className={s.graphStage}>
      <svg ref={svg} viewBox='0 0 640 480' role='img' aria-label='An evidence graph linking five videos, four findings and a common uploader'>
        <defs>{GN.filter(n => n.kind === 'media').map(n => <clipPath key={n.id} id={`lg-${n.id}`}><circle r={n.r - 2} /></clipPath>)}
          <radialGradient id='lgGlow'><stop offset='0' stopColor='#e9a23b' stopOpacity='.18' /><stop offset='1' stopColor='#e9a23b' stopOpacity='0' /></radialGradient></defs>
        <circle cx='320' cy='240' r='230' fill='url(#lgGlow)' />
        {GE.map(([a, b, k], i) => <path key={i} data-e={i} fill='none' stroke={EDGE[k].stroke} strokeOpacity={near && !(near.has(a) && near.has(b)) ? .08 : EDGE[k].op} strokeWidth={k === 'c' ? 1 : 1.6} strokeDasharray={EDGE[k].dash} className={k === 'p' ? s.flow : undefined} style={{ transition: 'stroke-opacity .2s' }} />)}
        {GN.map(n => <g key={n.id} data-n={n.id} onPointerEnter={() => setHover(n.id)} onPointerLeave={() => setHover(null)} style={{ opacity: near && !near.has(n.id) ? .25 : 1, transition: 'opacity .2s', cursor: 'default' }}>
          {n.kind === 'case' && <><circle r={n.r + 10} fill='none' stroke={n.tone} strokeOpacity='.25' className={s.ping} /><circle r={n.r} fill='#15110b' stroke={n.tone} strokeWidth='2' /><circle r={n.r - 9} fill={n.tone} opacity='.18' /></>}
          {n.kind === 'media' && <><circle r={n.r} fill='#050505' stroke={n.tone} strokeWidth='2' /><image href={`/images/evidence/${'img' in n ? n.img : ''}-480.webp`} x={-n.r} y={-n.r} width={n.r * 2} height={n.r * 2} preserveAspectRatio='xMidYMid slice' clipPath={`url(#lg-${n.id})`} /></>}
          {n.kind === 'finding' && <rect x={-n.r} y={-n.r} width={n.r * 2} height={n.r * 2} rx='3' transform='rotate(45)' fill={n.tone} stroke='#0b0a09' strokeWidth='2' />}
          {n.kind === 'meta' && <rect x={-n.r} y={-n.r} width={n.r * 2} height={n.r * 2} rx='4' fill='#0b0a09' stroke={n.tone} strokeWidth='1.8' />}
          {n.kind === 'source' && <polygon points={Array.from({ length: 6 }, (_, i) => `${(Math.cos(i * Math.PI / 3) * n.r).toFixed(1)},${(Math.sin(i * Math.PI / 3) * n.r).toFixed(1)}`).join(' ')} fill='#0b0a09' stroke={n.tone} strokeWidth='1.8' />}
        </g>)}
      </svg>
      <p className={s.hoverLabel} style={{ opacity: hn ? 1 : 0 }}>{hn?.label ?? ' '}</p>
    </div>
  </section>;
}

export function FinalCta() {
  return <section className={s.final} aria-labelledby='final-h' data-reveal>
    <svg className={s.iris} viewBox='0 0 200 200' aria-hidden='true'>
      <circle cx='100' cy='100' r='92' fill='none' stroke='#e9a23b' strokeOpacity='.25' />
      <g className={s.blades}>{Array.from({ length: 6 }, (_, i) => <path key={i} d='M100 8 L146 92' stroke='#e9a23b' strokeWidth='1.2' strokeOpacity='.5' transform={`rotate(${i * 60} 100 100)`} />)}</g>
      <circle cx='100' cy='100' r='16' fill='none' stroke='#e9a23b' strokeOpacity='.6' />
    </svg>
    <p className={s.eyebrow} data-reveal-item style={{ justifyContent: 'center' }}><i />Start an investigation</p>
    <h2 id='final-h' data-reveal-item>Find the frame where <br />the story changes.</h2>
    <p className={s.lede} data-reveal-item style={{ marginInline: 'auto', textAlign: 'center' }}>Drop a video. NEXTRON seals it, analyzes it in three branches and shows you the evidence, frame by frame.</p>
    <div className={s.finalActions} data-reveal-item>
      <Link href='/workspace' className={s.cta}>Launch analyzer <ArrowUpRight size={18} /></Link>
      <span className={s.assure}><Check size={15} />Your original is never altered</span>
    </div>
  </section>;
}
